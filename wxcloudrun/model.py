from datetime import datetime

from wxcloudrun import db


# 计数表
class Counters(db.Model):
    # 设置结构体表格名称
    __tablename__ = 'Counters'

    # 设定结构体对应表格的字段
    id = db.Column(db.Integer, primary_key=True)
    count = db.Column(db.Integer, default=1)
    created_at = db.Column('createdAt', db.TIMESTAMP, nullable=False, default=datetime.now)
    updated_at = db.Column('updatedAt', db.TIMESTAMP, nullable=False, default=datetime.now)


class UserAccount(db.Model):
    __tablename__ = "user_account"

    id = db.Column(db.String(64), primary_key=True)
    phone = db.Column(db.String(32), default="")
    status = db.Column(db.String(16), nullable=False, default="ACTIVE")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class UserMeicanAccount(db.Model):
    __tablename__ = "user_meican_account"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(64), db.ForeignKey("user_account.id"), unique=True, nullable=False)
    namespace = db.Column(db.String(64), nullable=False, default="default")
    access_token = db.Column(db.Text, nullable=True)
    refresh_token = db.Column(db.Text, nullable=True)
    token_expires_at = db.Column(db.DateTime, nullable=True)
    is_bound = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class UserPreference(db.Model):
    __tablename__ = "user_preference"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(64), db.ForeignKey("user_account.id"), unique=True, nullable=False)
    prefers_spicy = db.Column(db.Boolean, nullable=False, default=False)
    is_halal = db.Column(db.Boolean, nullable=False, default=False)
    is_cutting = db.Column(db.Boolean, nullable=False, default=False)
    staple = db.Column(db.String(16), nullable=False, default="")
    taboo = db.Column(db.Text, nullable=False, default="")
    price_min = db.Column(db.Numeric(10, 2), nullable=True)
    price_max = db.Column(db.Numeric(10, 2), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class AutoOrderConfig(db.Model):
    __tablename__ = "auto_order_config"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(64), db.ForeignKey("user_account.id"), unique=True, nullable=False)
    enabled = db.Column(db.Boolean, nullable=False, default=False)
    meal_slots = db.Column(db.String(32), nullable=False, default="")
    strategy = db.Column(db.String(32), nullable=False, default="TOP1")
    default_corp_address_id = db.Column(db.String(128), nullable=False, default="")
    effective_from = db.Column(db.Date, nullable=True)
    effective_to = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class CorpAddress(db.Model):
    __tablename__ = "corp_address"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    namespace = db.Column(db.String(64), nullable=False, default="default")
    address_unique_id = db.Column(db.String(128), nullable=False)
    name = db.Column(db.String(255), nullable=False, default="")
    raw_json = db.Column(db.Text, nullable=True)
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("namespace", "address_unique_id", name="uk_namespace_address"),
    )


class MenuSnapshot(db.Model):
    __tablename__ = "menu_snapshot"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    namespace = db.Column(db.String(64), nullable=False, default="default")
    date = db.Column(db.Date, nullable=False)
    meal_slot = db.Column(db.String(16), nullable=False)
    tab_unique_id = db.Column(db.String(128), nullable=True)
    target_time = db.Column(db.DateTime, nullable=True)
    source = db.Column(db.String(32), nullable=False, default="manual")
    raw_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("namespace", "date", "meal_slot", name="uk_namespace_date_slot"),
    )


class MenuItem(db.Model):
    __tablename__ = "menu_item"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    snapshot_id = db.Column(db.Integer, db.ForeignKey("menu_snapshot.id"), nullable=False, index=True)
    dish_id = db.Column(db.String(64), nullable=False, default="")
    dish_name = db.Column(db.String(255), nullable=False)
    restaurant_id = db.Column(db.String(64), nullable=False, default="")
    restaurant_name = db.Column(db.String(255), nullable=False, default="")
    price_cent = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="AVAILABLE")
    tags_text = db.Column(db.Text, nullable=True)
    raw_json = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class RecommendationBatch(db.Model):
    __tablename__ = "recommendation_batch"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    date = db.Column(db.Date, nullable=False, index=True)
    meal_slot = db.Column(db.String(16), nullable=False, index=True)
    namespace = db.Column(db.String(64), nullable=False, default="default", index=True)
    version = db.Column(db.Integer, nullable=False, default=1)
    status = db.Column(db.String(16), nullable=False, default="READY")
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)


class RecommendationResult(db.Model):
    __tablename__ = "recommendation_result"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("recommendation_batch.id"), nullable=False, index=True)
    user_id = db.Column(db.String(64), db.ForeignKey("user_account.id"), nullable=False, index=True)
    rank_no = db.Column(db.Integer, nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_item.id"), nullable=False)
    score = db.Column(db.Numeric(10, 4), nullable=False, default=0)
    reason = db.Column(db.Text, nullable=False, default="")
    selected_for_order = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("batch_id", "user_id", "rank_no", name="uk_batch_user_rank"),
    )


class OrderRecord(db.Model):
    __tablename__ = "order_record"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(64), db.ForeignKey("user_account.id"), nullable=False)
    date = db.Column(db.Date, nullable=False)
    meal_slot = db.Column(db.String(16), nullable=False)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_item.id"), nullable=False)
    source = db.Column(db.String(16), nullable=False, default="MANUAL")
    status = db.Column(db.String(16), nullable=False, default="CREATED")
    idempotency_key = db.Column(db.String(128), nullable=False, unique=True)
    meican_order_unique_id = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", "meal_slot", name="uk_user_date_meal"),
    )


class AutoOrderJob(db.Model):
    __tablename__ = "auto_order_job"

    id = db.Column(db.String(64), primary_key=True)
    date = db.Column(db.Date, nullable=False, index=True)
    meal_slot = db.Column(db.String(16), nullable=False)
    trigger_type = db.Column(db.String(16), nullable=False, default="SCHEDULE")
    status = db.Column(db.String(16), nullable=False, default="PENDING")
    total_count = db.Column(db.Integer, nullable=False, default=0)
    success_count = db.Column(db.Integer, nullable=False, default=0)
    failed_count = db.Column(db.Integer, nullable=False, default=0)
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("date", "meal_slot", "trigger_type", name="uk_job_date_slot_trigger"),
    )


class AutoOrderJobItem(db.Model):
    __tablename__ = "auto_order_job_item"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    job_id = db.Column(db.String(64), db.ForeignKey("auto_order_job.id"), nullable=False, index=True)
    user_id = db.Column(db.String(64), db.ForeignKey("user_account.id"), nullable=False, index=True)
    menu_item_id = db.Column(db.Integer, db.ForeignKey("menu_item.id"), nullable=True)
    status = db.Column(db.String(16), nullable=False, default="PENDING")
    retry_count = db.Column(db.Integer, nullable=False, default=0)
    fail_code = db.Column(db.String(64), nullable=True)
    fail_message = db.Column(db.Text, nullable=True)
    meican_order_unique_id = db.Column(db.String(128), nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.now)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.now, onupdate=datetime.now)

    __table_args__ = (
        db.UniqueConstraint("job_id", "user_id", name="uk_job_user"),
    )
