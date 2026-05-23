# Investory 上 Bedrock AgentCore Runtime 计划

> 日期：2026-05-01  
> 目标：把 Investory 当前的本地任务执行项目，演进成可部署到 AWS Bedrock AgentCore Runtime 的 custom runtime agent。

## 一句话结论

Investory 要上 `Bedrock AgentCore Runtime`，当前最合适的路径是：

```text
保留现有 TaskExecutor
-> 增加 AgentCore custom runtime HTTP adapter
-> 打包 linux/arm64 Docker 镜像
-> 推送到 ECR
-> 创建 Bedrock AgentCore Runtime
-> 通过 InvokeAgentRuntime 调用
```

也就是说，不要把现有 `agent_core/runtime` 改成 AWS 产品形状，而是在它外面补一层符合 AgentCore Runtime 契约的适配层。

## 当前仓库状态

当前已经具备：

- FastAPI 应用入口：`src/investory/main.py`
- 健康检查路由：`GET /health`
- 本地任务执行路由：`POST /tasks`
- Gateway schema：`TaskRequest`、`TaskResponse`、`TaskErrorResponse`
- 任务路由解析：`resolve_task_spec`
- 最小 session 处理：请求带 `session_id` 时复用，缺失时生成 UUID
- 业务执行内核：`TaskExecutor`
- 本地测试覆盖：gateway API、schema、routing、session、task executor
- README 中已有本地 `/health` 和 `/tasks` 调用示例

当前还缺：

- AgentCore 要求的 `GET /ping`
- AgentCore 要求的 `POST /invocations`
- AgentCore 专用 request / response schema
- 将 AgentCore 外层 `input` 契约映射到现有 `TaskRequest` 的 adapter
- Dockerfile
- `.dockerignore`
- ARM64 镜像构建流程
- ECR 仓库与镜像推送流程
- AgentCore Runtime 创建脚本或 IaC
- IAM role、Secrets、CloudWatch observability 配置
- 云上 invoke smoke test

当前判断：

- 本地普通 HTTP Gateway 已经进入可用状态。
- 上云计划的下一步不再是补 `/tasks`，而是新增 AgentCore 专用入口。
- `/invocations` 应该复用现有 `/tasks` 的执行链路，不重新实现任务业务逻辑。

## AWS AgentCore Runtime 对 custom runtime 的要求

根据 AWS 官方文档，custom runtime 需要满足这些基础要求：

- 暴露 `POST /invocations`
- 暴露 `GET /ping`
- 以 Docker container 形式打包
- 镜像架构为 `linux/arm64`
- 应用监听 `0.0.0.0:8080`
- 镜像推送到 Amazon ECR
- 通过 `CreateAgentRuntime` 创建 runtime
- 通过 `InvokeAgentRuntime` 调用 runtime

因此，Investory 的云上入口不应该是当前的 `/health`，而应该新增 AgentCore 专用入口：

```text
GET  /ping
POST /invocations
```

`/health` 可以继续保留给本地开发或普通 HTTP 服务使用，但它不是 AgentCore custom runtime 的核心契约。

## 推荐架构

```text
Client / backend
-> AWS SDK InvokeAgentRuntime
-> Bedrock AgentCore Runtime endpoint
-> Investory container
-> FastAPI /invocations
-> AgentCore adapter
-> gateway routing
-> TaskExecutor
-> RequestRunner
-> LLM provider
```

在代码职责上建议保持：

```text
agent_core/runtime/
  只负责任务怎么执行

gateway/
  负责 HTTP 请求、响应、错误映射

agentcore adapter
  负责把 AgentCore /invocations 契约映射成 Investory TaskRequest
```

## 建议的 AgentCore 调用契约

### 请求

AgentCore custom runtime 的外层请求建议保持：

```json
{
  "input": {
    "task_type": "qa",
    "payload": {
      "material_text": "ETF is a basket of assets.",
      "question": "What is an ETF?"
    },
    "session_id": "optional-app-session-id"
  }
}
```

说明：

- `input` 是 AgentCore custom runtime 的外层字段。
- `task_type` 继续复用 Investory 当前 gateway 概念。
- `payload` 保持任务专属输入，不在 HTTP 层硬编码具体任务字段。
- `session_id` 只作为 Investory 应用层追踪字段，不等同于 AgentCore 的 `runtimeSessionId`。

### 响应

建议响应保持：

```json
{
  "output": {
    "ok": true,
    "task_name": "finance_qa",
    "session_id": "optional-app-session-id",
    "result": {
      "answer": "..."
    },
    "error": null
  }
}
```

错误响应也放在 `output.error` 中：

```json
{
  "output": {
    "ok": false,
    "task_name": "finance_qa",
    "session_id": "optional-app-session-id",
    "result": null,
    "error": {
      "error_type": "input_validation_failed",
      "stage": "input_validation",
      "user_safe_message": "The input does not match the task requirements. Please check it and try again.",
      "retryable": false,
      "request_id": null
    }
  }
}
```

## AgentCore session 与 Investory session 的关系

AgentCore Runtime 调用时会有 `runtimeSessionId`。它是云平台层的 session 边界，负责隔离运行环境和复用会话上下文。

Investory 当前的 `session_id` 是应用层字段，只用于请求归属或后续业务记忆，不应该直接假设它等于 AgentCore 的 `runtimeSessionId`。

建议第一阶段这样处理：

- `runtimeSessionId`：由调用方在 `InvokeAgentRuntime` 时传入，用于 AgentCore session isolation。
- `input.session_id`：可选，用于 Investory 自己的业务追踪。
- 如果 `input.session_id` 缺失，Investory 继续生成自己的 UUID。
- 后续如果 AWS 明确把 `runtimeSessionId` 透传到容器 header 或环境中，再决定是否把它映射为 Investory session。

## 分阶段实施计划

### 阶段 1：文档和接口冻结

状态：基本完成，后续只做小幅修订。

目标：

- 明确 `/invocations` 请求/响应契约。
- 明确 `runtimeSessionId` 与 `session_id` 的边界。
- 明确首个部署目标是 Bedrock AgentCore custom runtime，而不是 ECS/App Runner。

产出：

- 本文档。
- 一份最小 invoke 示例。
- 一份实现 checklist。

验收：

- 后续代码实现都按本文档的 payload shape 走。
- 如果 AWS 文档或 SDK 示例要求不同外层字段，再单独修订本文档，不在实现时临时改 shape。

### 阶段 2：补 AgentCore HTTP adapter

状态：未开始。

目标：

- 新增 `GET /ping`。
- 新增 `POST /invocations`。
- 在 `/invocations` 内部复用现有 `/tasks` 执行链路。
- 保持 `TaskExecutor` 不感知 AWS。

建议实现逻辑：

```text
POST /invocations
-> validate AgentCoreInvocationRequest
-> extract input as TaskRequest
-> resolve session_id
-> resolve task spec
-> TaskExecutor.run(spec, payload)
-> convert TaskResult to TaskResponse
-> wrap as {"output": TaskResponse}
```

建议文件拆分：

```text
src/investory/
  gateway/
    api.py
      保留 /health 和 /tasks
    task_adapter.py
      放 TaskRequest -> TaskResponse 的共享执行函数
  agentcore/
    __init__.py
    schemas.py
      定义 AgentCoreInvocationRequest / AgentCoreInvocationResponse
    api.py
      定义 /ping 和 /invocations
```

这样 `/tasks` 和 `/invocations` 都可以调用同一个共享执行函数，避免未来两个 HTTP 入口行为漂移。

错误策略：

- Pydantic 请求格式错误：返回 HTTP 422。
- 未知 task type：与当前 `/tasks` 保持一致，返回 HTTP 400，并带稳定 JSON 错误体。
- 任务执行失败：优先返回 HTTP 200 + `output.ok=false`，让调用方拿到结构化错误。
- 未预期系统错误：返回 HTTP 500，并避免泄露 debug 信息。

### 阶段 3：本地测试

状态：部分完成。普通 gateway API 已覆盖，AgentCore adapter 测试未开始。

目标：

- 不依赖真实 LLM，先用 fake runner 测通 adapter。
- 再用真实模型做一次手工 smoke test。

必须覆盖：

- `GET /ping` 返回健康状态。
- `POST /invocations` 成功执行 `qa`。
- `POST /invocations` 成功执行 `summary`。
- 未知 `task_type` 的响应稳定，并与 `/tasks` 的错误策略一致。
- payload 缺字段时返回稳定错误。
- `session_id` 缺失时自动生成。
- `session_id` 提供时原样复用。
- `/tasks` 和 `/invocations` 对同一个输入返回等价的核心 `TaskResponse`。

### 阶段 4：Docker 化

状态：未开始。

目标：

- 添加根目录 `Dockerfile`。
- 添加根目录 `.dockerignore`。
- 运行端口固定为 `8080`。
- 容器启动命令使用 Uvicorn。
- 镜像平台固定为 `linux/arm64`。

建议镜像启动命令：

```text
python -m uvicorn investory.main:app --host 0.0.0.0 --port 8080
```

注意：

- 不要把 `.env` 打进镜像。
- 不要把本地 `logs/`、`data/`、`.venv/` 打进镜像。
- 如果后续需要云上持久化，优先用 AWS 服务，不依赖容器本地文件长期保存。
- 镜像启动后必须能在容器内响应 `GET /ping`，这是 AgentCore 比 `/health` 更关键的验收点。

### 阶段 5：AWS 资源准备

状态：未开始。

需要准备：

- AWS account
- 目标 region
- ECR repository
- AgentCore Runtime execution role
- Secrets Manager 或 Parameter Store
- CloudWatch logs / observability
- Bedrock 或外部 LLM provider 的访问权限

IAM role 至少要考虑：

- 拉取 ECR 镜像所需权限
- 写 CloudWatch logs 权限
- 如果用 Bedrock 模型，需要 Bedrock invoke 权限
- 如果用 Secrets Manager，需要读取指定 secret 的权限
- 最小权限，不使用过宽的 admin role

### 阶段 6：创建 AgentCore Runtime

状态：未开始。

目标：

- 使用 ECR 镜像创建 AgentCore Runtime。
- 设置 `networkConfiguration`。
- 设置 `lifecycleConfiguration`。
- 记录 `agentRuntimeArn`。
- 使用 `DEFAULT` endpoint 做第一轮调用。

需要提前决定：

- runtime 名称，例如 `investory-agent`
- region，例如 `us-west-2`
- network mode，先用 `PUBLIC` 还是接 VPC
- idle session timeout
- max lifetime
- dev / prod 是否使用不同 endpoint

### 阶段 7：云上调用验证

状态：未开始。

目标：

- 使用 AWS SDK 调用 `InvokeAgentRuntime`。
- 传入稳定的 `runtimeSessionId`。
- 调用 `qa` 任务。
- 调用 `summary` 任务。
- 检查 CloudWatch logs。
- 检查错误响应是否不泄露敏感信息。

最小调用 payload：

```json
{
  "input": {
    "task_type": "qa",
    "payload": {
      "material_text": "ETF is a basket of assets.",
      "question": "What is an ETF?"
    }
  }
}
```

验收标准：

- `InvokeAgentRuntime` 返回 JSON。
- 返回体包含 `output.ok`。
- 成功时包含 `output.result`。
- 失败时包含 `output.error.user_safe_message`。
- CloudWatch 中能看到请求日志。
- 没有 API key、secret、完整 prompt 泄露到日志。

## 首版不做的事情

第一版上 AgentCore Runtime 不建议同时做这些：

- 不引入长期记忆系统。
- 不引入异步长任务。
- 不引入 WebSocket streaming。
- 不引入 MCP server。
- 不重命名 `agent_core/runtime`。
- 不把所有云资源一次性 Terraform 化。

原因是当前最重要的是先跑通：

```text
AgentCore Runtime -> /invocations -> TaskExecutor -> structured response
```

这条链路跑通后，再做 Memory、Gateway、Tools、MCP、observability 深化。

## 风险与待确认点

### 1. Provider 选择

当前默认 provider 是 OpenAI。部署到 AWS AgentCore Runtime 后有两种路线：

- 继续使用 OpenAI API key。
- 切到 Amazon Bedrock 模型。

如果继续用 OpenAI，需要把 `OPENAI_API_KEY` 放入 Secrets Manager 或等价安全配置。

如果切到 Bedrock，需要新增 LangChain Bedrock provider 依赖和配置，这属于单独改造，不应该混在第一版 custom runtime adapter 里。

### 2. Session 状态

AgentCore session 是运行环境隔离，不等于业务长期记忆。Investory 如果要保存学习进度、用户偏好、历史任务，需要另接 DynamoDB、S3 或 AgentCore Memory。

### 3. 日志合规

Investory 面向投资学习场景，日志中不应记录：

- 用户完整财务信息
- API key
- 原始长 prompt
- 未脱敏的第三方响应

### 4. 金融边界

云上版本必须继续强化：

- 学习用途提示
- 不构成投资建议
- 不直接荐股
- 不给确定性收益承诺
- 工具或行情数据必须带时间戳

## 实现 checklist

- [x] 本地 FastAPI 入口可启动。
- [x] 本地 `GET /health` 可用。
- [x] 本地 `POST /tasks` 可用。
- [x] `/tasks` 调用 `TaskExecutor`。
- [x] `/tasks` 支持 `qa` 到 `finance_qa` 的别名映射。
- [x] `/tasks` 支持 `session_id` 自动生成和复用。
- [x] 为 `/tasks` 补 API 测试。
- [x] README 补本地 `/health` 和 `/tasks` 示例。
- [x] 冻结 `/invocations` 请求/响应契约。
- [ ] 新增 AgentCore adapter schema。
- [ ] 新增 `GET /ping`。
- [ ] 新增 `POST /invocations`。
- [ ] `/invocations` 调用 `TaskExecutor`。
- [ ] 为 `/invocations` 补单元测试。
- [ ] 为未知 task type 补测试。
- [ ] 为任务执行失败补测试。
- [ ] 添加 Dockerfile。
- [ ] 添加 `.dockerignore`。
- [ ] 本地用 `uvicorn` 测试 `0.0.0.0:8080`。
- [ ] 本地 build `linux/arm64` 镜像。
- [ ] 本地运行容器测试 `/ping`。
- [ ] 本地运行容器测试 `/invocations`。
- [ ] 创建 ECR repository。
- [ ] 推送 ARM64 镜像到 ECR。
- [ ] 创建 AgentCore Runtime execution role。
- [ ] 配置 secrets。
- [ ] 创建 AgentCore Runtime。
- [ ] 记录 runtime ARN。
- [ ] 使用 `InvokeAgentRuntime` 做云上 smoke test。
- [ ] 检查 CloudWatch logs。
- [ ] 写部署回滚说明。

## 参考资料

- AWS Bedrock AgentCore Runtime overview  
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html
- AWS Bedrock AgentCore Runtime how it works  
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html
- AWS Bedrock AgentCore custom runtime getting started  
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-custom.html
