# Investory 第 1-1 课文档目录

本目录记录第 1-1 阶段围绕“基于 LangChain 的最小任务执行器”的设计、配置、prompt、错误处理和示例材料。

## 阅读顺序

1. [最小任务执行器设计](01-runtime/investory-langchain-最小任务执行器设计.md)
   - 主设计文档，说明 `agent_core/runtime` 的边界、目录结构、实现步骤和验收方向。
2. [单次请求任务示例](05-examples/investory-单次请求任务示例.md)
   - 解释为什么 Investory 第一版适合从单次请求任务开始。
3. [LLM Provider 含义说明](02-provider-config/llm-provider-含义说明.md)
   - 说明 provider 和 model 的区别，以及 OpenAI / Anthropic / Google GenAI 的接入边界。
4. [模型参数取舍备忘](02-provider-config/investory-模型参数取舍备忘.md)
   - 记录当前阶段保留哪些模型参数、暂缓哪些参数，以及原因。
5. [System Prompt 与 User Prompt 设计](03-prompting/System Prompt 与 User Prompt 设计.md)
   - 说明 system prompt、user prompt、prompt injection 和结构化输出校验的设计原则。
6. [LLM 调用失败时的错误收束](04-error-retry/LLM调用失败时的错误收束.md)
   - 总结模型调用失败时的错误分类、重试、fallback、降级和观测原则。
7. [显式重试策略设计](04-error-retry/investory-显式重试策略设计.md)
   - 记录当前已落地的 Investory runtime retry loop 设计。

## 目录分组

```text
docs/1-1/
  README.md
  01-runtime/
    investory-langchain-最小任务执行器设计.md
  02-provider-config/
    llm-provider-含义说明.md
    investory-模型参数取舍备忘.md
  03-prompting/
    System Prompt 与 User Prompt 设计.md
  04-error-retry/
    LLM调用失败时的错误收束.md
    investory-显式重试策略设计.md
  05-examples/
    investory-单次请求任务示例.md
```

## 维护规则

- 主流程设计放在 `01-runtime/`。
- provider、模型名、环境变量和模型参数取舍放在 `02-provider-config/`。
- prompt 设计和 prompt 安全相关内容放在 `03-prompting/`。
- provider 错误、重试、降级和错误收束放在 `04-error-retry/`。
- 业务任务示例、MVP 示例和课程类说明放在 `05-examples/`。
- 如果文档内容已经被代码实现替代，保留设计背景，但在文档中明确“当前实现边界”。
