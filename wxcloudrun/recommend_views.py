import json
import re
import urllib.error
import urllib.request

import config
from flask import request

from wxcloudrun import app
from wxcloudrun.response import make_err_response, make_succ_response


def _extract_preference(payload):
    preference = payload.get("personalPreference") or {}
    return {
        "is_spicy": preference.get("isSpicy", preference.get("是否吃辣", False)),
        "is_halal": preference.get("isHalal", preference.get("是否清真", False)),
        "is_cutting": preference.get("isCutting", preference.get("是否减脂", False)),
        "staple": preference.get("staple", preference.get("主食偏好", "")),
        "other": preference.get("other", preference.get("其他补充", "")),
    }


def _extract_menu_list(payload):
    menu_list = payload.get("menuList")
    if isinstance(menu_list, list):
        return menu_list

    others = payload.get("othersRegularDishList")
    if isinstance(others, list):
        return others
    if isinstance(others, dict):
        nested = others.get("othersRegularDishList")
        if isinstance(nested, list):
            return nested
    return []


def _is_restaurant_available(dish):
    restaurant = dish.get("restaurant") or {}
    return restaurant.get("available", True) is not False


def _to_price_cent(dish):
    if isinstance(dish.get("priceCent"), int):
        return dish.get("priceCent")
    price = dish.get("price")
    if isinstance(price, (int, float)):
        return int(price * 100)
    return None


def _score_dish(dish, preference):
    score = 0.0
    reasons = []
    dish_name = str(dish.get("name", "")).lower()

    spicy_keywords = ("辣", "spicy", "麻辣", "香辣")
    pork_keywords = ("猪", "pork", "培根", "排骨")
    light_keywords = ("沙拉", "蔬菜", "轻食", "鸡胸", "清蒸", "水煮")
    heavy_keywords = ("炸", "油", "红烧", "锅包", "奶油", "肥牛")

    if preference["is_spicy"]:
        if any(k in dish_name for k in spicy_keywords):
            score += 2
            reasons.append("符合吃辣偏好")
    elif any(k in dish_name for k in spicy_keywords):
        score -= 1
        reasons.append("口味偏辣")

    if preference["is_halal"] and any(k in dish_name for k in pork_keywords):
        score -= 4
        reasons.append("疑似非清真食材")

    if preference["is_cutting"]:
        if any(k in dish_name for k in light_keywords):
            score += 2
            reasons.append("偏轻食更适合减脂")
        if any(k in dish_name for k in heavy_keywords):
            score -= 1
            reasons.append("烹饪方式偏重")

    staple = str(preference["staple"]).lower()
    if staple == "rice" and any(k in dish_name for k in ("饭", "盖浇", "rice")):
        score += 1
        reasons.append("符合米饭偏好")
    if staple == "noodle" and any(k in dish_name for k in ("面", "粉", "noodle")):
        score += 1
        reasons.append("符合面食偏好")

    if "priceMin" in dish or "priceMax" in dish:
        reasons.append("价格信息来自菜品字段")
    price_cent = _to_price_cent(dish)
    if price_cent is not None and price_cent > 0:
        score += 0.1

    if not reasons:
        reasons.append("综合匹配度较高")
    return score, "；".join(reasons)


def _parse_ai_json(content):
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    return json.loads(text)


def _call_ai_recommendation(preference, menu_candidates):
    if not config.OPENAI_API_KEY:
        return {}

    url = "{}/chat/completions".format(config.OPENAI_BASE_URL.rstrip("/"))
    prompt = {
        "preference": preference,
        "menuList": menu_candidates,
        "requirement": "请返回JSON数组，最多3项，每项包含id和reason。",
    }
    payload = {
        "model": config.OPENAI_MODEL,
        "temperature": config.OPENAI_TEMPERATURE,
        "messages": [
            {"role": "system", "content": "你是餐食推荐助手。只输出合法JSON，不要任何解释。"},
            {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
        ],
    }
    req = urllib.request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": "Bearer {}".format(config.OPENAI_API_KEY),
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=config.OPENAI_TIMEOUT_SECONDS) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            content = body["choices"][0]["message"]["content"]
            parsed = _parse_ai_json(content)
            if not isinstance(parsed, list):
                return {}
            ai_reason_map = {}
            for item in parsed[:3]:
                dish_id = str(item.get("id", "")).strip()
                reason = str(item.get("reason", "")).strip()
                if dish_id:
                    ai_reason_map[dish_id] = reason or "AI综合判断推荐"
            return ai_reason_map
    except (urllib.error.URLError, urllib.error.HTTPError, KeyError, ValueError, TypeError):
        return {}


@app.route("/api/recommend", methods=["POST"])
def recommend_dishes():
    payload = request.get_json(silent=True) or {}
    preference = _extract_preference(payload)
    dishes = _extract_menu_list(payload)
    if not dishes:
        return make_err_response("缺少菜单数据，需提供menuList或othersRegularDishList")

    available_dishes = [dish for dish in dishes if _is_restaurant_available(dish)]
    if not available_dishes:
        return make_err_response("暂无可用餐厅菜品")

    scored = []
    for dish in available_dishes:
        score, reason = _score_dish(dish, preference)
        scored.append(
            {
                "id": dish.get("id"),
                "name": dish.get("name"),
                "restaurant": dish.get("restaurant", {}),
                "score": round(score, 4),
                "rule_reason": reason,
            }
        )
    scored.sort(key=lambda x: x["score"], reverse=True)

    top_for_ai = scored[:10]
    ai_reason_map = _call_ai_recommendation(preference, top_for_ai)

    result = []
    for item in scored[:3]:
        dish_id = str(item.get("id", ""))
        result.append(
            {
                "id": item.get("id"),
                "name": item.get("name"),
                "restaurant": item.get("restaurant"),
                "score": item.get("score"),
                "reason": ai_reason_map.get(dish_id, item.get("rule_reason")),
            }
        )
    return make_succ_response(result)
