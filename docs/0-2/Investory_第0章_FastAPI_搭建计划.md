# Investory 第 0 章 FastAPI 搭建计划

## 目标

在第 0 章阶段，为 `Investory` 增加一个最小可运行的 `FastAPI` 服务入口，让当前已经存在的 `agent_core` 任务执行能力可以通过 HTTP 调用。

最终目标不是做完整线上服务，而是做出一个边界清楚、能本地运行、能验收最小任务链路的 Gateway。

## 当前基础

当前仓库已经有这些可复用能力：

- `src/investory/config.py`
  - 已有环境变量配置加载
- `src/investory/agent_core/tasks.py`
  - 已有任务注册表
- `src/investory/agent_core/runtime/task_executor.py`
  - 已有任务执行器
- `src/investory/agent_core/runtime/smoke/task.py`
  - 已有默认 payload 和最小执行链路
- `src/investory/gateway/`
  - 目录已存在，但还没有真正的 HTTP 层实现

这意味着第 0 章的 `FastAPI` 不需要重写 runtime，只需要增加一层薄的 HTTP 适配。

## 第 0 章范围

只做这些：

- 启动 `FastAPI`
- 提供 `GET /health`
- 提供 `POST /tasks`
- 支持最小任务类型路由
- 调用现有 `TaskExecutor`
- 返回统一 JSON 结果
- 保留最小 session 字段

暂时不做这些：

- 用户认证
- 数据库
- SSE
- 后台任务队列
- 长会话状态管理
- 复杂 planner
- 工具调用编排
- 真实云部署

## 设计原则

- `gateway` 只负责 HTTP 协议适配，不写任务业务逻辑。
- `agent_core` 继续作为任务执行内核。
- 第 0 章优先复用现有 `TaskExecutor` 和 `TASKS`。
- 请求 schema、路由映射、session 生成分开存放，不把逻辑塞进 `main.py`。
- 先保证最小链路跑通，再考虑 SSE、异步任务、鉴权和观测。

## 目标接口

### `GET /health`

用途：

- 验证服务是否启动
- 验证配置是否加载成功

建议返回：

```json
{
  "ok": true,
  "app_name": "Investory",
  "app_env": "dev"
}
```

### `POST /tasks`

用途：

- 接收最小任务请求
- 根据 `task_type` 或 `task_name` 找到目标任务
- 调用 `TaskExecutor`
- 返回 `TaskResult`

第 0 章建议先支持两类任务：

- `finance_qa`
- `learning_material_summary`

后续如果要贴课程里的第 0 章命名，可以在 `routing.py` 做一层别名映射，例如：

- `qa` -> `finance_qa`
- `summary` -> `learning_material_summary`

## 建议文件结构

基于当前仓库，建议新增或完善这些文件：

```text
src/investory/
  main.py
  gateway/
    __init__.py
    api.py
    schemas.py
    routing.py
    session.py
  memory/
    __init__.py
```

各文件职责：

- `main.py`
  - 创建 `FastAPI` app
  - 加载配置
  - 挂载路由
- `gateway/api.py`
  - 定义 `/health` 和 `/tasks`
  - 调用 routing / session / executor
- `gateway/schemas.py`
  - 定义请求与响应模型
- `gateway/routing.py`
  - 负责把外部 `task_type` 映射到内部 `TASKS`
- `gateway/session.py`
  - 生成最小 `session_id`
  - 第 0 章先不做真正 session store

## 请求与响应草案

### 请求模型

建议定义：

```json
{
  "task_type": "qa",
  "payload": {
    "material_text": "...",
    "question": "..."
  },
  "session_id": "optional"
}
```

建议规则：

- `task_type` 必填
- `payload` 必填
- `session_id` 可选
- 如果未传 `session_id`，服务端自动生成

### 响应模型

建议保持接近现有 `TaskResult`，并包一层 Gateway 元数据：

```json
{
  "ok": true,
  "task_name": "finance_qa",
  "session_id": "generated-id",
  "result": {},
  "error": null
}
```

失败时：

```json
{
  "ok": false,
  "task_name": "finance_qa",
  "session_id": "generated-id",
  "result": null,
  "error": {
    "error_type": "input_validation_failed",
    "stage": "input_validation",
    "user_safe_message": "..."
  }
}
```

## 实施步骤

### Step 1: 增加 Web 依赖

修改 `pyproject.toml`，增加：

- `fastapi`
- `uvicorn`

目的：

- 让当前项目具备最小 HTTP 服务能力

验收：

- 本地可执行 `uvicorn` 启动命令

### Step 2: 重构 `main.py` 为 FastAPI 入口

把当前仅打印配置的 `main.py` 改成：

- 暴露 `create_app()`
- 创建 `FastAPI` 实例
- 在启动时准备 `logs_dir` 和 `data_dir`
- 注册 gateway 路由

建议形态：

```python
def create_app() -> FastAPI:
    ...

app = create_app()
```

验收：

- `uvicorn investory.main:app --reload` 能启动

### Step 3: 新增 `gateway/schemas.py`

定义：

- `TaskRequest`
- `TaskResponse`
- `HealthResponse`

要求：

- 对外 schema 和内部 `TaskSpec` 解耦
- 不把内部模型直接暴露成 API 契约

验收：

- 请求缺字段时能返回标准 422

### Step 4: 新增 `gateway/routing.py`

实现最小映射逻辑：

- `qa` -> `finance_qa`
- `summary` -> `learning_material_summary`
- 同时允许直接传内部任务名

建议提供函数：

- `resolve_task_name(task_type: str) -> str`
- `resolve_task_spec(task_type: str) -> TaskSpec`

验收：

- 未知任务类型返回明确错误

### Step 5: 新增 `gateway/session.py`

实现最小 session 规则：

- 请求里已有 `session_id` 就沿用
- 没有就生成 UUID

第 0 章先不做：

- transcript 持久化
- profile 关联
- session 恢复

验收：

- 每次请求都能得到 `session_id`

### Step 6: 新增 `gateway/api.py`

实现两个接口：

- `GET /health`
- `POST /tasks`

`POST /tasks` 链路：

1. 校验请求 schema
2. 解析或生成 `session_id`
3. 解析任务类型
4. 调用 `TaskExecutor`
5. 返回统一响应

要求：

- `api.py` 不直接拼 prompt
- `api.py` 不直接处理模型 provider 细节
- `api.py` 不写具体任务逻辑

验收：

- 能通过 HTTP 跑通一次 `finance_qa`

### Step 7: 增加 API 测试

建议新增：

- `tests/test_api.py`

至少覆盖：

- `/health` 返回 200
- `/tasks` 正常执行 `qa`
- `/tasks` 对未知任务返回错误
- `/tasks` 对缺失字段返回 422 或明确错误

验收：

- `pytest` 中新增 API 测试通过

### Step 8: 补最小运行文档

在 README 或 `docs/0-1` 补上本地启动命令：

```powershell
.\.venv\Scripts\python.exe -m uvicorn investory.main:app --reload
```

以及最小请求示例：

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/tasks `
  -ContentType "application/json" `
  -Body '{"task_type":"qa","payload":{"material_text":"ETF is a basket of assets.","question":"What is ETF?"}}'
```

验收：

- 新同学按文档能本地拉起并请求成功

## 推荐实施顺序

建议按下面顺序做，不要反过来：

1. 先加依赖和 `FastAPI` app
2. 再补 schema / routing / session
3. 再接 `TaskExecutor`
4. 再写 API 测试
5. 最后补运行文档

原因：

- 先有服务入口，才能尽快确认架子没搭错
- 先把协议边界定清楚，再接现有 runtime，返工最少

## 第 0 章验收标准

- 服务可启动
- `GET /health` 可用
- `POST /tasks` 可用
- `qa` 能走通到 `finance_qa`
- `summary` 能走通到 `learning_material_summary`
- 请求校验和任务错误能返回稳定 JSON
- 代码边界清楚，`gateway` 不吞掉 `agent_core`

## 风险点

- 当前课程第 0 章的任务命名是 `qa | summary | study_plan`，而现有代码内部任务名是 `finance_qa | learning_material_summary`。这件事必须通过 `routing.py` 显式处理，不能混用。
- 当前 `TaskExecutor` 是同步调用模型，`FastAPI` 第 0 章先保持同步即可，不要过早引入异步和后台队列。
- 当前项目还没有真正的持久化 session store，第 0 章只把 `session_id` 作为协议字段，不要过度承诺会话能力。
- 当前还没有 API 层专用错误模型，如果直接把底层异常抛到 FastAPI，会破坏响应稳定性，需要在 gateway 层统一收口。

## 下一章衔接

完成这份计划后，后续章节可以自然扩展：

- 第 1 章：把更多单次任务接入 API
- 第 2 章：在 routing 后增加 planner / structured decision
- 第 5 章：补 SSE、任务台、会话归属
- 第 6 章：把 gateway、runtime、tools、events 进一步装配成完整 runtime

## 一句话结论

第 0 章的 `FastAPI` 不是新做一套 agent 系统，而是给当前已经存在的 `agent_core` 加一个最小 HTTP Gateway，让 `TaskExecutor` 能从本地 smoke test 进化到可调用服务。
