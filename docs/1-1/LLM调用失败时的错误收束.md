# LLM 调用失败时的错误收束

参考 `L3 GenAI Overview + Ops` 的学习笔记，LLM 调用失败时，错误收束的核心不是简单 `try/catch`，而是把失败限制在可判断、可重试、可降级、可观测的范围内。

## 1. 先分类错误，不要一律重试

常见错误类型：

- `401 / 403`：API Key 错误、权限不足、账户或模型访问配置问题。通常不要重试，应直接检查配置。
- `429`：限流、额度不足、并发过高。可以做指数退避重试，但必须限制次数。
- `5xx`：供应商服务端异常。可以短重试，失败后进入 fallback。
- `timeout`：网络慢、模型响应慢、请求过大或上下文过长。需要设置总超时和取消机制。
- `JSON parse / schema validation failed`：模型输出不符合结构化契约。可以做一次修复或重试，再进入降级或人工处理。

不要把所有错误都当成“网络抖动”。错误类型不同，处理策略也不同。

## 2. 重试要有边界

重试是为了处理短暂失败，不是为了掩盖系统问题。

建议策略：

- 设置单次请求 timeout，例如 `30s`。
- 设置最大重试次数，例如 `1-3` 次。
- 只对 `429`、短暂 `5xx`、网络抖动、可恢复 timeout 重试。
- 对 `401 / 403`、参数错误、权限错误不要盲目重试。
- 使用指数退避加 jitter，避免大量请求同时重试造成雪崩。
- 记录 `retry_count`。
- 设置总请求 deadline，不要每次重试都重新获得完整时间预算。

错误收束的关键是：每一次失败后，系统都更接近一个确定结果，而不是进入无限重试。

Investory 当前实现边界：provider SDK 自带重试关闭；`RequestRunner` 先发起一次模型调用，失败后根据错误码和异常类型判断是否重试。`INVESTORY_LLM_MAX_RETRIES=2` 表示初始调用之外最多再重试 2 次。`TaskError.retryable` 是最终错误收束后的判断信号，不等于一定已经发生重试；`TaskError.retry_count` 记录 Investory runtime 实际执行的重试次数。

## 3. 区分 retry、fallback、degrade

LLM 调用失败时，可以分三层处理。

### 3.1 Request-level retry

适用于：

- 网络抖动
- 短暂 `429`
- 偶发 `5xx`
- 首 token 前的 timeout

特点：短重试、次数少、成本可控。

### 3.2 Provider-level fallback

当某个 provider 或 model 连续失败、超时率升高、`429 / 5xx` 超过阈值时，可以切换到备用模型或备用供应商。

例如：

- OpenAI 失败时切到 Claude / Bedrock / Gemini。
- 主模型限流时切到同能力池里的备用模型。
- 高延迟模型异常时切到更快但质量略低的模型。

这通常需要：

- `circuit breaker`
- provider health cache
- 半开恢复机制
- 候选模型链：`primary -> secondary -> degraded`

### 3.3 Feature-level degrade

如果模型池整体不可用，就不要继续硬等，而是按业务功能降级。

示例：

- 客服：切到较小模型，但保持 streaming 和基本可用性。
- 文档摘要：转成异步任务，稍后生成。
- 数据分析：返回“分析排队中”，避免用户一直等待。
- 结构化抽取：校验失败后转人工复核。

## 4. Streaming 失败要特别处理

流式输出和普通请求不同。

需要注意：

- 首 token 之前失败：可以重试或切备用模型。
- 已经开始向客户端输出 token：不要中途切 provider，否则语义可能断裂。
- 用户取消连接时，网关要立刻 cancel 上游请求，避免继续消耗 token。
- 客户端读取太慢时，需要背压控制或断流，避免网关内存堆积。

Streaming 可观测性需要记录：

- `time_to_first_token`
- `tokens_per_second`
- stream 中断率
- 用户主动取消率
- 上游取消是否成功

## 5. 统一错误格式

业务代码不应该直接依赖不同供应商的原始错误结构。更好的方式是在 LLM Gateway 或 Provider Adapter 层统一错误格式。

示例：

```json
{
  "error_type": "rate_limited",
  "message": "The AI service is temporarily busy.",
  "retryable": true,
  "request_id": "req_123",
  "fallback_used": false
}
```

建议统一字段：

- `error_type`
- `retryable`
- `request_id`
- `provider`
- `model`
- `status_code`
- `retry_count`
- `fallback_used`
- `user_safe_message`

不要把原始 stack trace、API Key、完整 prompt、供应商内部错误直接返回给前端或用户。

## 6. 日志要可排查，但不能泄露敏感信息

失败时至少记录：

- `request_id`
- `feature`
- `tenant_id`
- `provider`
- `model`
- `latency_ms`
- `status_code`
- `error_type`
- `retry_count`
- `fallback_used`
- `prompt_tokens`
- `completion_tokens`
- `estimated_cost`

但不要记录：

- API Key
- 完整用户隐私
- PII
- 原始文件全文
- 敏感 prompt 内容
- 未脱敏的业务数据

原则：日志要能定位问题，但不能制造新的安全问题。

## 7. 成本也要收束

失败调用也会消耗成本，尤其是重试、fallback 和长上下文请求。

需要限制：

- 最大输入 token
- 最大输出 token
- 最大重试次数
- 单请求最大预算
- 单用户 / 租户预算
- fallback 是否允许切到更贵模型

如果没有成本边界，错误恢复机制本身可能变成成本失控来源。

## 8. 结构化输出失败的处理

对于 JSON、工具调用参数、分类标签等结构化输出，不要只依赖 prompt 里的“请返回 JSON”。

建议流程：

1. 使用 JSON Mode、结构化输出或 tool schema。
2. 对输出做 JSON Schema 校验。
3. 校验失败时进行一次修复或重试。
4. 仍失败则返回明确错误，或转人工处理。
5. 记录失败样例，用于后续 prompt / schema / eval 改进。

这类失败本质上是“契约失败”，不是普通网络失败。

## 9. 用户体验上的错误收束

给用户的反馈应该明确、稳定、可行动。

不要返回：

- 空白页面
- 无限 loading
- 原始异常堆栈
- “未知错误”且没有 request id

应该返回：

- 简短说明
- 是否可以重试
- request id
- 是否已进入异步队列
- 是否需要稍后查看结果

例如：

```text
AI 服务暂时繁忙，系统已自动重试但仍未成功。请稍后再试。Request ID: req_123
```

## 10. 生产检查清单

上线前至少确认：

- API Key 分环境管理，没有暴露到前端。
- 请求有 timeout、cancel 和最大重试次数。
- `401 / 403 / 429 / 5xx / timeout` 有不同处理逻辑。
- `429 / 5xx` 使用 Investory runtime 控制的指数退避重试，provider SDK retry 保持关闭，避免双重重试。
- streaming 首 token 前和首 token 后的失败策略不同。
- 有 fallback 和功能降级方案。
- 日志包含 request id、模型、延迟、token、错误码、重试次数。
- 日志已脱敏。
- 成本、成功率、P95 延迟、限流次数有监控。
- 结构化输出有 schema 校验和失败处理。
- 用户侧不会无限等待或看到原始错误。

## 一句话总结

LLM 调用失败时，先分类，再有限重试，再 fallback，再功能降级；同时保留 request id、日志、成本和安全边界。不要让失败变成无限重试、无日志、无预算、无用户反馈的黑盒。
