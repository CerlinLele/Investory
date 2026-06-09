# Investory 单任务执行器 Token 用量追踪与限流实施计划

## 1. 背景

当前单任务执行链路为：

```text
TaskExecutor
-> TaskExecutionPipeline
-> RequestRunner
-> provider model invoke
-> structured result
```

基于现有代码，当前状态可以概括为：

1. `TaskExecutor` 与 `TaskExecutionPipeline` 只负责输入校验、模型调用和结果收束，没有 usage telemetry。
2. `RequestRunner` 已具备显式 retry loop，能处理 `429 / 5xx / timeout` 等瞬时错误。
3. `TaskResult`、`TaskFlowState`、gateway response 中都没有 token usage 字段。
4. 当前的 rate limit 能力属于“被动重试”，不是“主动限流”。
5. 文档层面已有 budget / tool_budget 概念，但尚未落到当前 single task executor。

因此这次实施计划的目标不是重做执行器，而是在不破坏现有最小执行链路的前提下，补齐：

1. 单次任务的 token usage tracing
2. 可观测的 usage 输出
3. 基于 usage 的后续限流基础
4. 最小可用的应用层主动 rate limit

## 2. 目标

这次计划分为两个层级目标。

### 2.1 第一层目标：补 usage tracing

做到：

1. 每次单任务模型调用都能尽量提取 `input_tokens / output_tokens / total_tokens`。
2. usage 数据能进入 runtime state、最终 `TaskResult`，并可被 gateway 返回。
3. usage 提取失败时不影响主任务成功，只降级为“无 usage 数据”。
4. usage 字段结构统一，不把 provider 原始 metadata 直接散落到各层。

### 2.2 第二层目标：补主动 rate limit

做到：

1. 保留现有 `429` 后 retry/backoff。
2. 新增应用层主动限流，避免请求打到 provider 后再被动吃 `429`。
3. 限流第一版先做“单进程本地限流”，不做分布式。
4. TPM 相关控制必须建立在 usage tracing 先稳定的前提上。

## 3. 非目标

第一版明确不做：

1. 不做多机分布式限流。
2. 不做 Redis-based shared quota。
3. 不做按用户、按租户的复杂配额系统。
4. 不做成本计费结算。
5. 不做 streaming token tracing。
6. 不做 provider fallback orchestration。
7. 不做复杂 observability 平台接入，例如 OTEL exporter、外部 metrics backend。

## 4. 设计原则

1. 不改变 `TaskExecutor -> TaskExecutionPipeline -> RequestRunner` 的主链路职责分层。
2. 固定业务字段不用裸字符串散落，新增状态名、策略名、字段名时使用 `str, Enum` 或模块级常量。
3. usage tracing 必须“尽量获取但不阻塞主流程”。
4. 限流策略先做最小闭环，再考虑 TPM、budget、session quota。
5. 现有错误收束结构保持兼容，避免为了 telemetry 改坏 `TaskResult` 的成功/失败语义。

## 5. 目标落点

建议新增或修改的核心文件：

```text
src/investory/agent_core/contracts/result_types.py
src/investory/agent_core/contracts/flow_state.py
src/investory/agent_core/runtime/request_runner.py
src/investory/agent_core/runtime/task_execution_pipeline.py
src/investory/agent_core/runtime/task_executor.py
src/investory/agent_core/runtime/retry_policy.py
src/investory/agent_core/runtime/model_factory.py
src/investory/config.py
src/investory/gateway/schemas.py
src/investory/gateway/api.py
tests/test_request_runner.py
tests/test_task_executor.py
tests/test_gateway_api.py
tests/test_rate_limit.py
```

如果为了隔离职责更清晰，也可以新增：

```text
src/investory/agent_core/contracts/usage_types.py
src/investory/agent_core/runtime/usage_extractor.py
src/investory/agent_core/runtime/rate_limiter.py
```

## 6. 数据结构设计

### 6.1 Usage 契约

建议新增统一 usage 模型，而不是直接把 provider metadata 暴露到 `TaskResult`。

建议结构：

```python
class TokenUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    provider: str | None = None
    model: str | None = None
    source: str | None = None
```

`source` 建议使用固定常量或枚举，例如：

```python
class TokenUsageSource(str, Enum):
    RAW_MESSAGE = "raw_message"
    RESPONSE_METADATA = "response_metadata"
    PROVIDER_USAGE_METADATA = "provider_usage_metadata"
    UNAVAILABLE = "unavailable"
```

### 6.2 TaskResult 扩展

建议给 `TaskResult` 增加可选 telemetry 字段：

```python
class TaskResult(BaseModel):
    ok: bool
    task_name: str
    result: dict | None = None
    error: TaskError | None = None
    usage: TokenUsage | None = None
```

这样不会破坏旧调用方；旧逻辑可以无视 `usage`。

### 6.3 TaskFlowState 扩展

建议给 `TaskFlowState` 增加：

```python
usage: TokenUsage | None = None
rate_limit_decision: str | None = None
```

如果希望避免再次引入裸字符串，`rate_limit_decision` 建议用枚举：

```python
class RateLimitDecision(str, Enum):
    ALLOWED = "allowed"
    DELAYED = "delayed"
    REJECTED = "rejected"
    NOT_APPLIED = "not_applied"
```

## 7. Usage Tracing 实施方案

### Phase 1: 先打通 usage 提取闭环

#### Step 1: 确定 RequestRunner 的返回封装

当前 `RequestRunner.run()` 直接返回 parsed `BaseModel`，这对 structured output 很简洁，但 usage metadata 可能挂在原始 response 上，不一定跟着 parsed model 返回。

因此建议先做一个轻量封装：

```python
class RequestRunResult(BaseModel):
    parsed: BaseModel
    usage: TokenUsage | None = None
```

`RequestRunner.run()` 建议改为返回 `RequestRunResult`，然后由 pipeline 负责把：

1. `parsed.model_dump()` 写入 `state.model_result`
2. `usage` 写入 `state.usage`

如果不想改现有签名太大，也可以新增：

```python
run_with_telemetry(...)
```

然后让 `TaskExecutionPipeline` 切过去，旧接口保留给测试或兼容调用。

#### Step 2: 在 runtime 层增加 usage 提取器

建议新增：

```text
src/investory/agent_core/runtime/usage_extractor.py
```

职责：

1. 从 provider raw message 提取 usage
2. 从 `response_metadata` 提取 usage
3. 从 `usage_metadata` 提取 usage
4. 统一映射到 `TokenUsage`

建议提供单一入口：

```python
def extract_token_usage(raw_response: Any, *, provider: str | None, model: str | None) -> TokenUsage | None:
    ...
```

提取规则建议按优先级走：

1. `raw_response.usage_metadata`
2. `raw_response.response_metadata["token_usage"]`
3. `raw_response.response_metadata["usage"]`
4. provider-specific fallback

如果以上都拿不到，返回：

```python
TokenUsage(source=TokenUsageSource.UNAVAILABLE)
```

或者返回 `None`。二选一即可，但整个项目要保持一致。

#### Step 3: 处理 structured output 与 raw response 的兼容问题

这里是本计划最需要先验证的一点。

因为当前调用方式是：

```python
structured_model = self.model.with_structured_output(output_model)
parsed = structured_model.invoke(messages)
```

需要先做一个小型实现验证，确认 raw response 是否还能被拿到。

建议顺序：

1. 优先尝试 structured output 原生支持的 `include_raw=True` 能力。
2. 如果当前 provider wrapper 不稳定，再退回 callback / metadata 抓取。
3. 如果不同 provider 表现差异太大，第一版先对 OpenAI 路径做稳定支持，其余 provider best effort。

这一阶段要先做验证，不建议直接大面积改动。

#### Step 4: Pipeline 透传 usage

`TaskExecutionPipeline` 的 `invoke_task_model()` 修改为：

1. 从 `RequestRunner` 拿到 `parsed + usage`
2. 写入 `state.model_result`
3. 写入 `state.usage`

`build_task_result()` 修改为：

1. 成功结果带上 `usage`
2. 失败结果如果在模型调用阶段已拿到 usage，也可以一并带上

失败时是否带 usage，建议第一版就支持，因为：

1. provider 可能已经消耗了 prompt tokens
2. 后续做 TPM / cost 分析时，失败请求也有价值

#### Step 5: Gateway 暴露 usage

如果当前 `TaskResponse` 已经直接包 `TaskResult`，只需保持 schema 兼容。

如果 gateway 做了自定义映射，需补：

1. response model 新增 `usage`
2. API 输出测试补 usage 断言

### Phase 2: 增强 usage 可靠性

这一阶段做增强，不在第一提交里强耦合进去。

建议补：

1. provider-specific extraction fixture
2. 缺失 usage 时的 debug logging
3. usage sanity check，例如 `total_tokens >= input_tokens`
4. usage source 标记，便于后续排查 provider 差异

## 8. 主动 Rate Limit 实施方案

### 8.1 当前现状

当前已有能力：

1. `429` 被识别为 retryable
2. 有指数退避
3. `TaskError` 会归一化成 `rate_limited`

当前缺失能力：

1. 请求发出去之前的主动拦截
2. 并发上限控制
3. 请求速率上限控制
4. 基于 token 使用量的 TPM 控制

### 8.2 实施顺序

建议分三阶段，不要一步到位。

#### Phase A: 请求级主动限流

先做最小闭环：

1. 单进程内并发上限
2. 单位时间请求数上限
3. 触发限流时，可选择等待或快速失败

建议新增：

```text
src/investory/agent_core/runtime/rate_limiter.py
```

建议定义策略枚举：

```python
class RateLimitMode(str, Enum):
    DISABLED = "disabled"
    WAIT = "wait"
    FAIL_FAST = "fail_fast"
```

建议配置：

```text
INVESTORY_RATE_LIMIT_MODE=disabled
INVESTORY_MAX_CONCURRENT_LLM_REQUESTS=4
INVESTORY_LLM_REQUESTS_PER_WINDOW=20
INVESTORY_LLM_RATE_LIMIT_WINDOW_SECONDS=60
```

第一版建议使用：

1. `threading.Semaphore` 或等价结构限制并发
2. 进程内 deque timestamps 做滑动窗口 request limit

这套方案简单、可测、足够支撑当前本地单进程服务。

#### Phase B: 基于 usage 的 TPM 软限制

等 usage tracing 稳定后，再接 token-per-minute。

建议配置：

```text
INVESTORY_LLM_TOKENS_PER_WINDOW=40000
INVESTORY_LLM_TOKEN_WINDOW_SECONDS=60
```

这里建议先做软限制：

1. 如果过去窗口内累计 `total_tokens` 超阈值，则延迟新请求
2. 不先做硬拒绝，避免 provider usage 统计误差导致误杀

这个阶段依赖第一阶段的 usage 记录，因此不能倒着做。

#### Phase C: budget / quota 扩展

这是后续演进，不纳入本次最小实现。

未来可扩展：

1. session budget
2. task-type budget
3. daily budget
4. tenant budget

## 9. 运行时接入点

### 9.1 Rate limiter 应放在哪里

建议放在 `RequestRunner` 调用模型之前，而不是 gateway 层。

原因：

1. 单任务执行器之外，后续 flow、todo runner、react loop 也可能复用 `RequestRunner`
2. 限流应尽量贴近真实 LLM 调用点
3. 这样不会漏掉非 HTTP 入口，例如 CLI smoke 或内部 flow 调用

推荐顺序：

```text
RequestRunner.run()
-> acquire local rate limiter
-> invoke model
-> collect usage
-> release / record timestamps / record tokens
```

### 9.2 429 与主动限流的关系

主动限流不是替代 retry，而是前置缓冲层。

最终顺序建议是：

```text
本地 rate limiter
-> provider invoke
-> 如果仍然 429
-> retry policy + backoff
```

也就是说，第一版仍然保留当前 `429` 的错误收束与重试逻辑。

## 10. 测试计划

### 10.1 Usage tracing 测试

建议新增或更新：

```text
tests/test_request_runner.py
tests/test_task_executor.py
tests/test_gateway_api.py
```

覆盖：

1. raw response 含 usage metadata 时，能映射为 `TokenUsage`
2. raw response 不含 usage metadata 时，不影响主结果成功
3. 成功任务返回 `TaskResult.usage`
4. 失败任务如已有 usage，也能被保留
5. gateway response 能透传 usage

### 10.2 主动限流测试

建议新增：

```text
tests/test_rate_limit.py
```

覆盖：

1. `DISABLED` 模式下不拦截
2. 超过并发阈值时 `WAIT` 模式会等待
3. 超过并发阈值时 `FAIL_FAST` 模式会直接失败
4. 超过窗口 request limit 时会延迟或失败
5. usage 计入 token window 后，新请求会被延迟
6. provider 已返回 `429` 时，原有 retry 逻辑仍生效

### 10.3 回归测试

必须回归：

```text
.venv\Scripts\python.exe -m pytest
```

至少确保：

1. 现有 task execution tests 不回归
2. 现有 gateway tests 不回归
3. 现有 retry tests 不回归

## 11. 配置计划

建议在 `AppConfig` 与 `.env.example` 中增加以下配置。

### 第一批必须加

```text
INVESTORY_RATE_LIMIT_MODE=disabled
INVESTORY_MAX_CONCURRENT_LLM_REQUESTS=4
INVESTORY_LLM_REQUESTS_PER_WINDOW=20
INVESTORY_LLM_RATE_LIMIT_WINDOW_SECONDS=60
```

### 第二批 usage 稳定后再加

```text
INVESTORY_LLM_TOKENS_PER_WINDOW=40000
INVESTORY_LLM_TOKEN_WINDOW_SECONDS=60
```

说明：

1. `llm_max_retries` 继续保留，职责不变
2. 新增 rate limit 配置只控制本地主动限流
3. TPM 配置默认可先不启用，等 usage tracing 打通后再接

## 12. 分阶段实施顺序

建议按下面顺序提交，便于 review 和回滚。

### Step 1: usage 契约与状态扩展

修改：

```text
contracts/result_types.py
contracts/flow_state.py
```

目标：

1. 增加 `TokenUsage`
2. 增加 `TaskResult.usage`
3. 增加 `TaskFlowState.usage`

### Step 2: usage extractor 与 runner 验证

新增或修改：

```text
runtime/usage_extractor.py
runtime/request_runner.py
tests/test_request_runner.py
```

目标：

1. 打通 raw response usage 提取
2. 先验证 OpenAI 路径
3. structured output 场景能返回 parsed + usage

### Step 3: pipeline / executor / gateway 透传

修改：

```text
runtime/task_execution_pipeline.py
runtime/task_executor.py
gateway/schemas.py
gateway/api.py
tests/test_task_executor.py
tests/test_gateway_api.py
```

目标：

1. usage 能从 runner 进入最终响应
2. 旧调用不回归

### Step 4: 本地主动限流最小实现

新增或修改：

```text
runtime/rate_limiter.py
runtime/request_runner.py
config.py
.env.example
tests/test_rate_limit.py
```

目标：

1. 支持并发上限
2. 支持请求窗口限流
3. 支持 wait / fail_fast 模式

### Step 5: TPM 软限制

修改：

```text
runtime/rate_limiter.py
runtime/request_runner.py
config.py
tests/test_rate_limit.py
```

目标：

1. 基于 `total_tokens` 做窗口累计
2. 超阈值时延迟而不是直接拒绝

## 13. 验收标准

完成后应满足：

1. 单任务成功响应可选携带 `usage.input_tokens / output_tokens / total_tokens`。
2. usage 提取失败不会让主任务失败。
3. 失败任务如果已拿到 usage，响应中能保留 usage。
4. 现有 `429` retry 逻辑保持可用。
5. 新增主动限流后，请求可在本地被等待或快速失败，而不是只能依赖 provider `429`。
6. 代码中新增的固定状态值、策略值、来源值使用枚举或模块级常量承载。
7. 全量测试通过。

## 14. 风险与注意事项

1. structured output 场景下 raw response 是否稳定可取，是第一风险点，必须先做小范围验证。
2. 不同 provider 的 usage metadata 结构可能不同，第一版不要追求完全统一支持。
3. 主动限流如果直接做 TPM 硬拒绝，容易因为 usage 不准产生误伤，所以应先软限制。
4. rate limiter 若写在 gateway 层，会漏掉非 HTTP 调用路径，因此不建议放在那里。
5. 不要让 telemetry 反向污染主执行逻辑，usage 抓取失败应降级处理。

## 15. 一句话结论

正确的落地顺序应是：

```text
先补单任务 usage tracing，
再在 RequestRunner 层加本地主动限流，
最后再基于稳定 usage 数据扩展 TPM / budget。
```
