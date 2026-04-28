# Investory 模型参数取舍备忘

这份备忘用于记录第 1-1 阶段对模型参数的取舍判断。参考材料是模型参数 Lab 中关于 `temperature`、`top_p`、`max_tokens`、`frequency_penalty`、`presence_penalty`、`seed` 和 `logprobs` 的说明。

当前结论：

> 第 1-1 阶段先不要把所有模型参数都放进 `AppConfig`。只保留最小任务执行器真正需要消费的参数，等 eval、A/B test、分类置信度或输出长度控制成为实际需求时，再逐步扩展。

## 当前阶段需要的参数

第 1-1 阶段的目标是先跑通一条稳定的最小任务执行链路：

```text
TaskSpec
-> prompt_loader
-> task_executor
-> request_runner
-> OpenAI model
-> structured result
```

因此当前只需要这些配置：

```env
INVESTORY_LLM_PROVIDER=openai
INVESTORY_DEFAULT_MODEL=gpt-5.4-mini
INVESTORY_LLM_TEMPERATURE=0
INVESTORY_LLM_MAX_RETRIES=2
```

对应含义：

| 参数 | 当前是否需要 | 原因 |
|---|---:|---|
| `provider` | 需要 | 决定使用 OpenAI、Anthropic 还是 Gemini 等 provider |
| `model` | 需要 | 决定具体调用的模型 ID |
| `temperature` | 需要 | 最小任务执行器优先追求稳定、可评估，默认用 `0` |
| `max_retries` | 需要 | 模型 API 调用失败时提供基础重试能力 |

## 当前阶段暂时不加的参数

| 参数 | 当前是否需要 | 暂缓原因 |
|---|---:|---|
| `max_tokens` | 暂时不加 | 等任务输出长度开始不可控或成本需要约束时再加 |
| `top_p` | 暂时不加 | 第一版优先只调 `temperature`，避免采样参数组合变复杂 |
| `frequency_penalty` | 暂时不加 | 主要用于减少重复表达，当前结构化任务执行器不是核心痛点 |
| `presence_penalty` | 暂时不加 | 主要用于鼓励新话题或创意扩展，当前不需要 |
| `seed` | 后续 eval 阶段再加 | 回归测试、参数实验和 A/B test 时更有价值 |
| `logprobs` | 后续分类置信度场景再加 | 可用于低置信度结果判断，但当前先不做 |

## 后续可以扩展的参数

当 Investory 开始做 eval、A/B test、分类置信度或输出长度控制时，可以逐步补充：

```env
INVESTORY_LLM_MAX_TOKENS=
INVESTORY_LLM_TOP_P=
INVESTORY_LLM_SEED=
```

如果后续出现文案生成、客服回复或投资学习内容改写等更偏生成式的任务，再考虑：

```env
INVESTORY_LLM_FREQUENCY_PENALTY=
INVESTORY_LLM_PRESENCE_PENALTY=
```

如果后续出现分类、标签判断、风险等级判断等需要置信度辅助的任务，再考虑：

```env
INVESTORY_LLM_LOGPROBS=
```

## 参数选择原则

- 分类、抽取、结构化输出：低温度、强约束、优先稳定。
- 客服、邮件、说明：中低温度，兼顾自然表达和可靠性。
- 文案、创意、头脑风暴：较高温度，允许更多变化。
- 生产调参：一次只改一个主要变量，并通过指标验证，不凭感觉上线。
- 回归测试和 eval：固定 prompt、模型、参数和输入，必要时再引入 `seed`。

## 对当前实现的约束

当前 `AppConfig` 不应该一次性塞入所有模型参数。

更合适的演进方式是：

1. 先实现 `llm_provider`、`default_model`、`llm_temperature`、`llm_max_retries`。
2. 在 `model_factory.py` 中真正消费这些参数。
3. 等具体任务暴露出长度、重复、创意或置信度问题后，再增加对应参数。
4. 每增加一个参数，都要明确它被哪个 runtime 组件消费，以及通过什么测试或 eval 验证有效。

一句话结论：

> 当前阶段先保持模型参数小而明确；参数不是越多越专业，而是要等代码和任务真的需要时再接入。
