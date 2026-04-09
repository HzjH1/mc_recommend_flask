import uuid
from datetime import date, datetime, time
from decimal import Decimal

import config
from flask import request
from sqlalchemy.exc import IntegrityError

from wxcloudrun import app, db
from wxcloudrun.model import (
    AutoOrderConfig,
    AutoOrderJob,
    AutoOrderJobItem,
    MenuItem,
    OrderRecord,
    RecommendationBatch,
    RecommendationResult,
    UserAccount,
    UserPreference,
)
from wxcloudrun.response import make_v1_err_response, make_v1_succ_response

ALLOWED_MEAL_SLOTS = {"LUNCH", "DINNER"}
ALLOWED_STAPLE = {"", "rice", "noodle"}


def _request_id():
    return request.headers.get("X-Request-Id") or "trace-{}".format(uuid.uuid4().hex)


def _json_payload():
    payload = request.get_json(silent=True)
    return payload if isinstance(payload, dict) else None


def _parse_date(value):
    return datetime.strptime(value, "%Y-%m-%d").date()


def _to_decimal(value):
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _split_meal_slots(slots_text):
    if not slots_text:
        return set()
    return {x.strip().upper() for x in slots_text.split(",") if x.strip()}


def _get_or_create_user(user_id):
    user = UserAccount.query.get(user_id)
    if user is None:
        user = UserAccount(id=user_id, phone="", status="ACTIVE")
        db.session.add(user)
        db.session.flush()
    return user


def _check_internal_token(rid):
    if not config.INTERNAL_JOB_TOKEN:
        return None
    token = request.headers.get("X-Internal-Token", "")
    if token != config.INTERNAL_JOB_TOKEN:
        return make_v1_err_response(40101, "UNAUTHORIZED_INTERNAL_TOKEN", request_id=rid, http_status=401)
    return None


def _is_past_cutoff(target_date, meal_slot):
    now = datetime.now()
    if target_date != now.date():
        return False
    cutoff_text = config.AUTO_ORDER_CUTOFF_LUNCH if meal_slot == "LUNCH" else config.AUTO_ORDER_CUTOFF_DINNER
    cutoff_time = datetime.strptime(cutoff_text, "%H:%M").time()
    return now.time() > cutoff_time


def _config_effective(cfg, target_date, meal_slot):
    if cfg.effective_from and target_date < cfg.effective_from:
        return False
    if cfg.effective_to and target_date > cfg.effective_to:
        return False
    if meal_slot not in _split_meal_slots(cfg.meal_slots):
        return False
    return True


def _latest_batch(target_date, meal_slot, namespace):
    query = RecommendationBatch.query.filter(
        RecommendationBatch.date == target_date,
        RecommendationBatch.meal_slot == meal_slot,
    )
    if namespace:
        query = query.filter(RecommendationBatch.namespace == namespace)
    return query.order_by(RecommendationBatch.version.desc(), RecommendationBatch.id.desc()).first()


@app.route("/api/v1/users/<string:user_id>/preferences", methods=["PUT"])
def upsert_user_preferences(user_id):
    rid = _request_id()
    payload = _json_payload()
    if payload is None:
        return make_v1_err_response(40001, "INVALID_JSON_BODY", request_id=rid)

    staple = str(payload.get("staple", "")).strip().lower()
    if staple not in ALLOWED_STAPLE:
        return make_v1_err_response(40010, "INVALID_STAPLE", request_id=rid)

    try:
        price_min = _to_decimal(payload.get("priceMin"))
        price_max = _to_decimal(payload.get("priceMax"))
    except Exception:
        return make_v1_err_response(40011, "INVALID_PRICE_RANGE", request_id=rid)
    if price_min is not None and price_max is not None and price_min > price_max:
        return make_v1_err_response(40011, "INVALID_PRICE_RANGE", request_id=rid)

    user = _get_or_create_user(user_id)
    pref = UserPreference.query.filter(UserPreference.user_id == user.id).first()
    if pref is None:
        pref = UserPreference(user_id=user.id)
        db.session.add(pref)

    pref.prefers_spicy = bool(payload.get("prefersSpicy", pref.prefers_spicy))
    pref.is_halal = bool(payload.get("isHalal", pref.is_halal))
    pref.is_cutting = bool(payload.get("isCutting", pref.is_cutting))
    pref.staple = staple
    pref.taboo = str(payload.get("taboo", pref.taboo or ""))
    pref.price_min = price_min
    pref.price_max = price_max

    db.session.commit()
    return make_v1_succ_response({"userId": user.id, "preferenceId": pref.id}, request_id=rid)


@app.route("/api/v1/users/<string:user_id>/auto-order-config", methods=["PUT"])
def upsert_auto_order_config(user_id):
    rid = _request_id()
    payload = _json_payload()
    if payload is None:
        return make_v1_err_response(40001, "INVALID_JSON_BODY", request_id=rid)

    meal_slots = payload.get("mealSlots", [])
    if not isinstance(meal_slots, list):
        return make_v1_err_response(40012, "INVALID_MEAL_SLOTS", request_id=rid)
    normalized_slots = sorted({str(x).upper() for x in meal_slots if str(x).strip()})
    if not set(normalized_slots).issubset(ALLOWED_MEAL_SLOTS):
        return make_v1_err_response(40012, "INVALID_MEAL_SLOTS", request_id=rid)

    try:
        effective_from = _parse_date(payload["effectiveFrom"]) if payload.get("effectiveFrom") else None
        effective_to = _parse_date(payload["effectiveTo"]) if payload.get("effectiveTo") else None
    except ValueError:
        return make_v1_err_response(40013, "INVALID_EFFECTIVE_DATE", request_id=rid)
    if effective_from and effective_to and effective_from > effective_to:
        return make_v1_err_response(40013, "INVALID_EFFECTIVE_DATE", request_id=rid)

    user = _get_or_create_user(user_id)
    cfg = AutoOrderConfig.query.filter(AutoOrderConfig.user_id == user.id).first()
    if cfg is None:
        cfg = AutoOrderConfig(user_id=user.id)
        db.session.add(cfg)

    cfg.enabled = bool(payload.get("enabled", cfg.enabled))
    cfg.meal_slots = ",".join(normalized_slots)
    cfg.strategy = str(payload.get("strategy", cfg.strategy or "TOP1"))
    cfg.default_corp_address_id = str(payload.get("defaultCorpAddressId", cfg.default_corp_address_id or ""))
    cfg.effective_from = effective_from
    cfg.effective_to = effective_to

    db.session.commit()
    return make_v1_succ_response({"userId": user.id, "configId": cfg.id}, request_id=rid)


@app.route("/api/v1/users/<string:user_id>/recommendations/daily", methods=["GET"])
def get_daily_recommendations(user_id):
    rid = _request_id()
    _get_or_create_user(user_id)

    target_date_text = request.args.get("date")
    namespace = request.args.get("namespace", "").strip()
    try:
        target_date = _parse_date(target_date_text) if target_date_text else date.today()
    except ValueError:
        return make_v1_err_response(40013, "INVALID_DATE", request_id=rid)

    data = {"date": target_date.isoformat(), "LUNCH": [], "DINNER": []}
    for meal_slot in ("LUNCH", "DINNER"):
        batch = _latest_batch(target_date, meal_slot, namespace)
        if not batch:
            continue
        rows = RecommendationResult.query.filter(
            RecommendationResult.batch_id == batch.id,
            RecommendationResult.user_id == user_id,
        ).order_by(RecommendationResult.rank_no.asc()).all()
        ordered = (
            OrderRecord.query.filter(
                OrderRecord.user_id == user_id,
                OrderRecord.date == target_date,
                OrderRecord.meal_slot == meal_slot,
            ).first()
            is not None
        )
        items = []
        for row in rows:
            menu_item = MenuItem.query.get(row.menu_item_id)
            items.append(
                {
                    "rankNo": row.rank_no,
                    "menuItemId": row.menu_item_id,
                    "dishName": menu_item.dish_name if menu_item else "",
                    "restaurantName": menu_item.restaurant_name if menu_item else "",
                    "priceCent": menu_item.price_cent if menu_item else None,
                    "score": float(row.score),
                    "reason": row.reason,
                    "ordered": ordered,
                }
            )
        data[meal_slot] = items

    return make_v1_succ_response(data, request_id=rid)


@app.route("/api/v1/users/<string:user_id>/orders", methods=["POST"])
def create_order(user_id):
    rid = _request_id()
    payload = _json_payload()
    if payload is None:
        return make_v1_err_response(40001, "INVALID_JSON_BODY", request_id=rid)

    try:
        target_date = _parse_date(payload.get("date", ""))
    except ValueError:
        return make_v1_err_response(40013, "INVALID_DATE", request_id=rid)
    meal_slot = str(payload.get("mealSlot", "")).upper()
    if meal_slot not in ALLOWED_MEAL_SLOTS:
        return make_v1_err_response(40012, "INVALID_MEAL_SLOT", request_id=rid)

    idempotency_key = str(payload.get("idempotencyKey", "")).strip()
    if not idempotency_key:
        return make_v1_err_response(40002, "MISSING_IDEMPOTENCY_KEY", request_id=rid)

    menu_item_id = payload.get("menuItemId")
    if not isinstance(menu_item_id, int):
        return make_v1_err_response(40003, "INVALID_MENU_ITEM_ID", request_id=rid)

    _get_or_create_user(user_id)

    same_key = OrderRecord.query.filter(OrderRecord.idempotency_key == idempotency_key).first()
    if same_key:
        return make_v1_succ_response(
            {"orderId": same_key.id, "status": same_key.status, "idempotent": True},
            request_id=rid,
        )

    menu_item = MenuItem.query.get(menu_item_id)
    if menu_item is None:
        return make_v1_err_response(40401, "MENU_ITEM_UNAVAILABLE", request_id=rid, http_status=404)

    existing = OrderRecord.query.filter(
        OrderRecord.user_id == user_id,
        OrderRecord.date == target_date,
        OrderRecord.meal_slot == meal_slot,
    ).first()
    if existing:
        return make_v1_err_response(40901, "ORDER_ALREADY_EXISTS", request_id=rid, http_status=409)

    order = OrderRecord(
        user_id=user_id,
        date=target_date,
        meal_slot=meal_slot,
        menu_item_id=menu_item_id,
        source="MANUAL",
        status="CREATED",
        idempotency_key=idempotency_key,
    )
    db.session.add(order)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        dup = OrderRecord.query.filter(OrderRecord.idempotency_key == idempotency_key).first()
        if dup:
            return make_v1_succ_response(
                {"orderId": dup.id, "status": dup.status, "idempotent": True},
                request_id=rid,
            )
        return make_v1_err_response(40901, "ORDER_ALREADY_EXISTS", request_id=rid, http_status=409)

    return make_v1_succ_response({"orderId": order.id, "status": order.status}, request_id=rid)


@app.route("/api/v1/internal/jobs/auto-order/run", methods=["POST"])
def run_auto_order_job():
    rid = _request_id()
    auth_err = _check_internal_token(rid)
    if auth_err:
        return auth_err

    payload = _json_payload()
    if payload is None:
        return make_v1_err_response(40001, "INVALID_JSON_BODY", request_id=rid)

    try:
        target_date = _parse_date(payload.get("date", ""))
    except ValueError:
        return make_v1_err_response(40013, "INVALID_DATE", request_id=rid)

    meal_slot = str(payload.get("mealSlot", "")).upper()
    if meal_slot not in ALLOWED_MEAL_SLOTS:
        return make_v1_err_response(40012, "INVALID_MEAL_SLOT", request_id=rid)

    force = bool(payload.get("force", False))
    namespace = str(payload.get("namespace", "default")).strip() or "default"
    trigger_type = "MANUAL" if force else "SCHEDULE"

    if not force and _is_past_cutoff(target_date, meal_slot):
        return make_v1_err_response(40902, "PAST_AUTO_ORDER_WINDOW", request_id=rid, http_status=409)

    job = AutoOrderJob.query.filter(
        AutoOrderJob.date == target_date,
        AutoOrderJob.meal_slot == meal_slot,
        AutoOrderJob.trigger_type == trigger_type,
    ).first()
    created = False
    if job is None:
        job = AutoOrderJob(
            id="job-{}".format(uuid.uuid4().hex),
            date=target_date,
            meal_slot=meal_slot,
            trigger_type=trigger_type,
            status="PENDING",
            started_at=datetime.combine(date.today(), time.min),
        )
        db.session.add(job)
        created = True
    elif force:
        AutoOrderJobItem.query.filter(AutoOrderJobItem.job_id == job.id).delete()
        job.status = "PENDING"
        job.total_count = 0
        job.success_count = 0
        job.failed_count = 0
        job.retry_count = 0

    configs = AutoOrderConfig.query.filter(AutoOrderConfig.enabled == True).all()
    total_count = 0
    failed_count = 0

    for cfg in configs:
        if not _config_effective(cfg, target_date, meal_slot):
            continue
        total_count += 1
        item = AutoOrderJobItem(job_id=job.id, user_id=cfg.user_id, status="PENDING")
        if not cfg.default_corp_address_id:
            item.status = "FAILED"
            item.fail_code = "NO_DEFAULT_ADDRESS"
            item.fail_message = "auto order config missing defaultCorpAddressId"
            failed_count += 1
            db.session.add(item)
            continue

        batch = _latest_batch(target_date, meal_slot, namespace)
        if not batch:
            item.status = "FAILED"
            item.fail_code = "NO_RECOMMENDATION_BATCH"
            item.fail_message = "no recommendation batch found"
            failed_count += 1
            db.session.add(item)
            continue

        top = RecommendationResult.query.filter(
            RecommendationResult.batch_id == batch.id,
            RecommendationResult.user_id == cfg.user_id,
        ).order_by(RecommendationResult.rank_no.asc()).first()
        if not top:
            item.status = "FAILED"
            item.fail_code = "NO_RECOMMENDATION_ITEM"
            item.fail_message = "no ranked recommendation for user"
            failed_count += 1
            db.session.add(item)
            continue

        item.menu_item_id = top.menu_item_id
        db.session.add(item)

    job.total_count = total_count
    job.failed_count = failed_count
    job.success_count = 0
    job.status = "READY"
    if total_count == 0:
        job.status = "EMPTY"
    job.started_at = datetime.now()
    job.finished_at = datetime.now()
    db.session.commit()

    return make_v1_succ_response(
        {"jobId": job.id, "status": job.status, "created": created},
        request_id=rid,
    )


@app.route("/api/v1/internal/jobs/auto-order/<string:job_id>", methods=["GET"])
def get_auto_order_job(job_id):
    rid = _request_id()
    auth_err = _check_internal_token(rid)
    if auth_err:
        return auth_err

    job = AutoOrderJob.query.get(job_id)
    if not job:
        return make_v1_err_response(40402, "JOB_NOT_FOUND", request_id=rid, http_status=404)

    failed_items = (
        AutoOrderJobItem.query.filter(
            AutoOrderJobItem.job_id == job.id,
            AutoOrderJobItem.status == "FAILED",
        )
        .order_by(AutoOrderJobItem.id.asc())
        .limit(200)
        .all()
    )
    failed_payload = [
        {
            "userId": item.user_id,
            "status": item.status,
            "retryCount": item.retry_count,
            "failCode": item.fail_code,
            "failMessage": item.fail_message,
        }
        for item in failed_items
    ]
    return make_v1_succ_response(
        {
            "jobId": job.id,
            "date": job.date.isoformat(),
            "mealSlot": job.meal_slot,
            "status": job.status,
            "totalCount": job.total_count,
            "successCount": job.success_count,
            "failedCount": job.failed_count,
            "retryCount": job.retry_count,
            "failedItems": failed_payload,
            "startedAt": job.started_at.isoformat() if job.started_at else None,
            "finishedAt": job.finished_at.isoformat() if job.finished_at else None,
        },
        request_id=rid,
    )
