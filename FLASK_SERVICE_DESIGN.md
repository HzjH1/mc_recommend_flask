# Flask 服务接口与数据库设计

该设计参考 `mc_recommend` 的接口风格、数据模型约束和 AI 配置策略，并在当前 Flask 项目中落地。

## 接口分层

- 通用演示接口
  - `GET /api/count`
  - `POST /api/count`
- 实时推荐接口
  - `POST /api/recommend`
- V1 用户与自动点餐接口
  - `PUT /api/v1/users/<user_id>/preferences`
  - `PUT /api/v1/users/<user_id>/auto-order-config`
  - `GET /api/v1/users/<user_id>/recommendations/daily`
  - `POST /api/v1/users/<user_id>/orders`
  - `POST /api/v1/internal/jobs/auto-order/run`
  - `GET /api/v1/internal/jobs/auto-order/<job_id>`

## 响应协议

- 旧版接口保持：
  - 成功：`{"code": 0, "data": ...}`
  - 失败：`{"code": -1, "errorMsg": "..."}`
- V1 接口统一：
  - `{"code": 0, "message": "ok", "requestId": "trace-xxx", "data": {...}}`

## 核心数据库表

- `Counters`
- `user_account`
- `user_meican_account`
- `user_preference`
- `auto_order_config`
- `corp_address`
- `menu_snapshot`
- `menu_item`
- `recommendation_batch`
- `recommendation_result`
- `order_record`
- `auto_order_job`
- `auto_order_job_item`

已在 `wxcloudrun/model.py` 中完成 SQLAlchemy 模型定义，包含关键唯一约束：

- `uk_namespace_date_slot`：`menu_snapshot(namespace, date, meal_slot)`
- `uk_batch_user_rank`：`recommendation_result(batch_id, user_id, rank_no)`
- `uk_user_date_meal`：`order_record(user_id, date, meal_slot)`
- `idempotency_key` 唯一：`order_record.idempotency_key`
- `uk_job_date_slot_trigger`：`auto_order_job(date, meal_slot, trigger_type)`
- `uk_job_user`：`auto_order_job_item(job_id, user_id)`

## AI 大模型配置

通过环境变量读取，统一在 `config.py`：

- `OPENAI_API_KEY`
- `OPENAI_BASE_URL`（默认 `https://api.openai.com/v1`）
- `OPENAI_MODEL`（默认 `gpt-4o-mini`）
- `OPENAI_TIMEOUT_SECONDS`（默认 `15`）
- `OPENAI_TEMPERATURE`（默认 `0.2`）

`/api/recommend` 支持：

- 规则打分（兜底）
- 调用 OpenAI 兼容 `chat/completions` 返回 Top3 推荐理由
- AI 调用失败自动回退规则结果

## 内部任务配置

通过环境变量控制内部任务：

- `INTERNAL_JOB_TOKEN`
- `AUTO_ORDER_CUTOFF_LUNCH`（默认 `11:00`）
- `AUTO_ORDER_CUTOFF_DINNER`（默认 `17:00`）

当 `INTERNAL_JOB_TOKEN` 非空时，`/api/v1/internal/jobs/*` 需携带请求头：

- `X-Internal-Token: <token>`
