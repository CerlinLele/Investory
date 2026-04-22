# Investory 第 0 章：模块图 + 目录结构 + 第一版骨架职责

这版是 `Investory` 在**第 0 章**应有的样子：先有骨架，能启动，能跑最小链路，但不追求功能完整。

## 模块图

```text
[ Web / CLI / API Client ]
           |
           v
+------------------------+
| gateway                |
| - HTTP API             |
| - session / route      |
| - request validation   |
+-----------+------------+
            |
            v
+------------------------+
| runtime                |
| - task entry           |
| - context assembly     |
| - model call wrapper   |
| - event emit           |
+-----+-----------+------+
      |           |
      |           +------------------+
      v                              v
+-------------+               +----------------+
| skills       |              | tools          |
| - skill load |              | - registry     |
| - references |              | - mock data    |
| - templates  |              | - future MCP   |
+-------------+               +----------------+
      |
      v
+------------------------+
| memory                 |
| - session store        |
| - profile placeholder  |
| - task logs            |
+------------------------+

            +------------------------+
            | safety                 |
            | - policy guard         |
            | - disclaimer rules     |
            +------------------------+

            +------------------------+
            | eval                   |
            | - sample cases         |
            | - smoke checks         |
            +------------------------+
```

## 目录结构

```text
investory/
  app/
    main.py
    config.py

    gateway/
      api.py
      schemas.py
      session.py
      routing.py

    runtime/
      engine.py
      context.py
      model_client.py
      events.py

    planner/
      planner.py
      contracts.py

    skills/
      registry.py
      loader.py
      assets/
        finance_qa.md
        summary_template.md

    tools/
      registry.py
      mock_fund_tool.py
      mock_news_tool.py

    memory/
      store.py
      profile_store.py
      task_log.py

    safety/
      policy.py
      disclaimer.py

    eval/
      smoke.py
      cases/
        basic_qa.json
        summary.json

    core/
      logging.py
      exceptions.py
      utils.py

  docs/
  tests/
    test_api.py
    test_runtime.py
  data/
    sessions/
    eval/
  logs/
  .env.example
  requirements.txt
  README.md
```

## 第一版骨架职责

第 0 章只做这些，别超范围。

- `app/main.py`
  - 启动 `FastAPI`
  - 挂载健康检查和最小任务接口
- `app/config.py`
  - 统一读取模型、日志、数据目录、开关配置
- `gateway/api.py`
  - 提供 `POST /tasks`、`GET /health`
  - 只负责入参校验和调用 runtime，不写业务逻辑
- `gateway/schemas.py`
  - 定义请求/响应 schema
  - 先固定 `task_type` 为 `qa | summary | study_plan`
- `gateway/session.py`
  - 生成 `session_id`
  - 关联最小会话上下文
- `gateway/routing.py`
  - 把请求映射到任务类型
  - 现在可以先用简单规则，不上复杂 planner
- `runtime/engine.py`
  - 第 0 章核心
  - 串起 `input -> context -> safety -> model -> result -> log`
- `runtime/context.py`
  - 组装 system prompt、session 信息、风险提示
- `runtime/model_client.py`
  - 封装模型调用
  - 先只保留一个统一接口 `generate()`
- `runtime/events.py`
  - 先实现最小事件结构
  - 即使暂时不用 SSE，也先定义 `task_started/task_finished/task_failed`
- `planner/*`
  - 第 0 章先占位
  - 后面第 2 章再真正接入结构化决策
- `skills/registry.py` + `loader.py`
  - 第 0 章只支持静态 reference skill
  - 比如“理财概念解释规范”“风险提示模板”
- `tools/registry.py`
  - 先定义注册方式
  - 第 0 章可只接 mock 工具，别急着接真实行情
- `memory/store.py`
  - 保存最小 session transcript
- `memory/profile_store.py`
  - 先占位，后续存学习偏好/风险偏好
- `memory/task_log.py`
  - 记录每次任务输入输出，方便调试
- `safety/policy.py`
  - 拒绝直接荐股、择时、仓位建议
- `safety/disclaimer.py`
  - 自动补“学习用途，不构成投资建议”
- `eval/smoke.py`
  - 做最小冒烟检查
  - 至少验证 3 类任务都能返回
- `core/logging.py`
  - 统一日志格式
- `core/exceptions.py`
  - 统一错误类型，别让 API 和 runtime 各抛各的

## 第 0 章验收标准

- 服务能启动
- `POST /tasks` 能完成一次最小问答
- session 和日志能落盘
- 输出自动带风险提示
- 模块边界清楚，没把逻辑全塞进 `main.py` 或 `api.py`
