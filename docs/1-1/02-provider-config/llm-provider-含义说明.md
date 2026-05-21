# LLM Provider 含义说明

在 Investory 里，`LLM provider` 不是模型名本身，而是选择一套 LLM 调用适配器、认证方式、默认 endpoint 和模型命名约定。

简单说：

```text
provider = 怎么调用
model    = 调用哪个具体模型
base_url = 请求发到哪里
api_key  = 用哪把钥匙认证
```

## provider 代表什么

当前 `src/investory/config.py` 里支持三种 provider：

| provider | LangChain 包 | 实例化类 | 默认模型 |
| --- | --- | --- | --- |
| `openai` | `langchain-openai` | `ChatOpenAI` | `gpt-5.4-mini` |
| `anthropic` | `langchain-anthropic` | `ChatAnthropic` | `claude-sonnet-4-20250514` |
| `google_genai` | `langchain-google-genai` | `ChatGoogleGenerativeAI` | `gemini-2.5-flash` |

这些 provider 会决定：

- 需要安装哪个 LangChain provider 包
- 使用哪个 ChatModel 类
- 默认模型名是什么
- 默认 API base URL 是什么
- 从哪个环境变量读取 API key
- 从哪个环境变量读取 base URL

## provider 不等于模型归属

`provider=openai` 并不必然表示只能调用 OpenAI 官方模型。

它更准确的含义是：使用 `ChatOpenAI` 这套 OpenAI 风格的客户端适配器。实际请求发给谁，取决于 `OPENAI_BASE_URL`。

例如：

```env
INVESTORY_LLM_PROVIDER=openai
INVESTORY_DEFAULT_MODEL=some-other-model
OPENAI_BASE_URL=https://some-openai-compatible-endpoint/v1
OPENAI_API_KEY=...
```

只要这个 endpoint 兼容 OpenAI 风格的接口，并且支持 `some-other-model` 这个模型名，工程上就可以通过 `provider=openai` 调用它。

## 澳大利亚使用场景

如果开发者或部署环境主要在澳大利亚，当前这三种 provider 对 Investory 的早期阶段基本够用：

| provider | 覆盖范围 | 适合场景 |
| --- | --- | --- |
| `openai` | OpenAI 官方 API，以及大量 OpenAI-compatible 网关、聚合服务、本地服务 | 默认主力 provider；也可作为通用兼容入口 |
| `anthropic` | Anthropic Claude API | Claude 系列模型、长文档、强推理备选 |
| `google_genai` | Google Gemini API / Google AI Studio | Gemini 系列模型、Google 生态备选 |

从地区可用性看，澳大利亚目前在这三类官方 API 的支持范围内：

- OpenAI API supported countries 包含 Australia: <https://platform.openai.com/docs/supported-countries>
- Anthropic supported regions 包含 Australia: <https://docs.anthropic.com/zh-CN/api/supported-regions>
- Google Gemini API / Google AI Studio available regions 包含 Australia: <https://ai.google.dev/gemini-api/docs/available-regions>

因此现阶段没有必要为了“海外可用性”继续扩展 provider。优先保留这三类，可以降低配置复杂度，同时覆盖主流 LLM 能力。

后续只有在出现明确需求时再考虑新增：

- `openrouter`：需要通过一个 API 切换很多第三方模型时考虑；但很多情况下可以先用 `provider=openai` 加自定义 `OPENAI_BASE_URL` 接入。
- `ollama`：需要本地模型时考虑。
- `vertex_ai`：需要 Google Cloud 企业部署、GCP IAM、区域控制或 Vertex AI 特性时考虑；它和当前 `google_genai` 属于不同接入层。

## 需要注意的边界

虽然 provider 不一定绑定模型归属，但它绑定了调用方式。

例如：

- `provider=openai` 使用 OpenAI 风格参数和 `ChatOpenAI`
- `provider=anthropic` 使用 Anthropic 风格参数和 `ChatAnthropic`
- `provider=google_genai` 使用 Google GenAI 风格参数和 `ChatGoogleGenerativeAI`

所以不能只把 provider 理解成“输出标准”。它更像是“客户端协议适配层”。

如果某个第三方平台提供 OpenAI-compatible API，可以优先考虑用 `provider=openai` 加自定义 `OPENAI_BASE_URL` 接入。如果平台需要 Anthropic 或 Google 原生协议，则应该选择对应 provider。
