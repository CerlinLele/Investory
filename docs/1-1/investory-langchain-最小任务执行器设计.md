# Investory 第 1-1 课：基于 LangChain 的最小任务执行器

这版设计参考 `investory-最小任务执行器目录建议.md`，采用 `agent_core/runtime` 作为最小任务执行器的位置。

结论先放前面：

> Investory 可以使用 LangChain，但不要把 Investory 做成一个 LangChain 项目。更合适的做法是：Investory 自己定义任务、prompt、结果结构和执行边界；LangChain 只作为 `agent_core/runtime` 里的模型调用实现层。

当前阶段最适合使用 LangChain 的三个能力：

- `init_chat_model`
  统一创建 chat model。
- `ChatPromptTemplate`
  统一组装 system prompt、任务 prompt 和输入 payload。
- `with_structured_output`
  让模型输出符合 Pydantic schema 的结构化结果。

当前阶段不要一上来使用完整 LangChain agent、LangGraph、多工具循环或复杂 memory。你现在要做的是“最小任务执行器”，不是完整 agent 系统。

## 为什么放在 agent_core/runtime

`agent_core/` 表示 Investory 的 agent 核心能力，包括任务定义、prompt、结果结构和执行入口。

`agent_core/runtime/` 表示 agent core 内部真正把一次任务跑起来的运行层。它不是 Python 解释器运行环境，也不是单纯的模型 API 封装，而是负责：

- 接收 `TaskSpec` 和 payload
- 使用 `input_model` 校验 payload
- 加载并组装 prompt
- 调用 LangChain model wrapper
- 获取结构化输出
- 把成功结果或错误统一收口

所以这一层的职责关系是：

```text
TaskSpec + payload
-> task_executor
-> input_model validation
-> prompt_loader
-> request_runner
-> LangChain chat model
-> structured result
```

这里的关键点是：

- Investory 拥有任务边界。
- Investory 拥有 prompt 文件。
- Investory 拥有结果结构。
- LangChain 只是 runtime 里的实现细节。

## 推荐目录

```text
src/investory/
  config.py
  main.py
  gateway/
  memory/
  eval/
  agent_core/
    __init__.py
    task_spec.py
    result_types.py
    schemas.py
    runtime/
      __init__.py
      model_factory.py
      request_runner.py
      task_executor.py
      prompt_loader.py
    prompts/
      base/
        system.md
        common_rules.md
      tasks/
        meeting_minutes.md
        policy_qa.md
```

注意目录名建议使用 `agent_core`，不要使用 `agent-core`。Python package 目录不能稳定地用连字符做 import 路径。

## 文件职责

- `agent_core/task_spec.py`
  定义任务元数据，例如任务名、prompt 名、输出 schema。
- `agent_core/result_types.py`
  定义统一返回结构，例如 `TaskResult`、`TaskError`。
- `agent_core/schemas.py`
  放 Pydantic 输入和输出模型，例如 `PolicyQAInput`、`PolicyQAResult`、`MeetingMinutesInput`、`MeetingMinutesResult`。
- `agent_core/runtime/model_factory.py`
  只负责创建 LangChain chat model。
- `agent_core/runtime/request_runner.py`
  只负责“给定 messages + output schema，调用模型并拿回结构化结果”。
- `agent_core/runtime/task_executor.py`
  只负责“给定 TaskSpec + payload，校验输入，加载 prompt，调用 runner，做错误收口”。
- `agent_core/runtime/prompt_loader.py`
  只负责从 `agent_core/prompts/` 读取 `.md` prompt 文件。
- `agent_core/prompts/base/`
  保存共享系统提示和通用规则。
- `agent_core/prompts/tasks/`
  保存每个任务自己的 prompt 模板。

## 依赖建议

如果第一版只接 OpenAI，可以先安装：

```bash
pip install langchain langchain-openai pydantic
```

如果要预留三家主流 LLM provider，可以安装：

```bash
pip install langchain langchain-openai langchain-anthropic langchain-google-genai pydantic
```

后续写入 `pyproject.toml` 时，可以放到项目依赖里：

```toml
dependencies = [
    "langchain>=0.3",
    "langchain-openai>=0.2",
    "langchain-anthropic>=0.2",
    "langchain-google-genai>=2.0",
    "pydantic>=2",
]
```

版本号后面可以根据实际安装环境再锁定。第 1-1 课真正运行时建议先启用一家 provider，其他 provider 只保留配置占位。

## Implementation Steps

### Step 1：先定默认 provider

第一版建议默认用 OpenAI：

```env
INVESTORY_LLM_PROVIDER=openai
INVESTORY_DEFAULT_MODEL=gpt-5.4-mini
```

这样最小执行器先只验证一条主链路：

```text
TaskSpec + payload
-> task_executor
-> input_model validation
-> prompt_loader
-> request_runner
-> OpenAI model
-> structured result
```

等 `policy_qa` 和 `meeting_minutes` 跑通后，再打开 Anthropic 或 Gemini 做效果对照。

### Step 2：配置 provider 列表

不要把 API key 写进代码或 Git 仓库。配置文件只保存环境变量名，真实 key 放在本地 `.env` 或部署平台 secret manager。

推荐先支持这几类：

| provider | 用途 | package | default model | base url | api key env |
|---|---|---|---|---|---|
| `openai` | 默认主链路 | `langchain-openai` | `gpt-5.4-mini` | `https://api.openai.com/v1` | `OPENAI_API_KEY` |
| `anthropic` | 长文本、总结对照 | `langchain-anthropic` | `claude-sonnet-4-20250514` | `https://api.anthropic.com` | `ANTHROPIC_API_KEY` |
| `google_genai` | Gemini 原生接入 | `langchain-google-genai` | `gemini-2.5-flash` | `https://generativelanguage.googleapis.com` | `GOOGLE_API_KEY` |

说明：

- `google_genai` 是 LangChain 的 Gemini 原生集成，第一版先用原生接入即可。
- OpenAI、Anthropic、Google Gemini 三家已经足够覆盖第 1-1 课的开发、对照和 smoke test。
- model 名称会随 provider 迭代，生产环境应该固定到明确模型 ID，并用 eval 对比后再升级。

### Step 3：本地 `.env` 示例

本地新建 `.env`，只填写你要启用的 provider。第一版只填 OpenAI 也可以。

```env
# Investory active LLM
INVESTORY_LLM_PROVIDER=openai
INVESTORY_DEFAULT_MODEL=gpt-5.4-mini
INVESTORY_LLM_TEMPERATURE=0
INVESTORY_LLM_MAX_RETRIES=2

# OpenAI
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-your-openai-key

# Anthropic
ANTHROPIC_BASE_URL=https://api.anthropic.com
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key

# Google Gemini native
GOOGLE_BASE_URL=https://generativelanguage.googleapis.com
GOOGLE_API_KEY=your-google-api-key
```

不要提交 `.env`。仓库里只提交 `.env.example`。

### Step 4：配置文件结构

`config.example.yaml` 可以用这种结构：

```yaml
models:
  active_provider: openai
  default_model: gpt-5.4-mini
  temperature: 0
  max_retries: 2
  providers:
    openai:
      model: gpt-5.4-mini
      base_url_env: OPENAI_BASE_URL
      api_key_env: OPENAI_API_KEY
    anthropic:
      model: claude-sonnet-4-20250514
      base_url_env: ANTHROPIC_BASE_URL
      api_key_env: ANTHROPIC_API_KEY
    google_genai:
      model: gemini-2.5-flash
      base_url_env: GOOGLE_BASE_URL
      api_key_env: GOOGLE_API_KEY
```

当前项目的 `config.py` 先只从环境变量读配置也可以，不急着实现 YAML loader。第 1-1 课建议保持简单。

### Step 5：按最小实现顺序落代码

前四步只解决“用哪个 provider、从哪里读配置”。从这一步开始进入正式实现。

不要在多个章节重复展开同一段代码。下面的“最小实现步骤与代码骨架”就是第 1-1 课的实现准绳：按顺序创建文件、跑 provider smoke test，再跑任务 smoke test。

### Step 6：先做 provider smoke test

在真正跑 `TaskExecutor` 前，先验证这条链路：

```text
load_config
-> model_factory
-> LangChain provider wrapper
-> model.invoke
```

验收标准：

1. 能读取正确 provider。
2. 能读取正确 model。
3. 能读取 base url。
4. 能读取 api key。
5. 能完成一次最小调用。
6. 错误时能明确看到是缺 key、base url 错误、模型名错误，还是 provider 包未安装。

### Step 7：再做任务 smoke test

provider smoke test 通过后，再验证完整最小执行器链路：

```text
TaskSpec + payload
-> task_executor
-> input_model validation
-> prompt_loader
-> request_runner
-> model.with_structured_output
-> TaskResult
```

第 1-1 课只需要先跑通 `policy_qa` 和 `meeting_minutes`，不要在这一步引入工具调用、LangGraph、复杂 registry 或长期 memory。

## 最小实现步骤与代码骨架

这一节按正式实现顺序组织。每一步只说明目的和对应代码，避免和上面的设计说明重复。

### Step 1：扩展 `config.py`

目的：统一读取 provider、model、base url、api key、temperature 和 retry 配置。

```python
from dataclasses import dataclass
from os import getenv
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]

PROVIDER_ENV = {
    "openai": {
        "base_url": "OPENAI_BASE_URL",
        "api_key": "OPENAI_API_KEY",
    },
    "anthropic": {
        "base_url": "ANTHROPIC_BASE_URL",
        "api_key": "ANTHROPIC_API_KEY",
    },
    "google_genai": {
        "base_url": "GOOGLE_BASE_URL",
        "api_key": "GOOGLE_API_KEY",
    },
}


@dataclass(slots=True)
class AppConfig:
    app_name: str = "Investory"
    app_env: str = "dev"
    logs_dir: Path = PROJECT_ROOT / "logs"
    data_dir: Path = PROJECT_ROOT / "data"
    llm_provider: str = "openai"
    default_model: str = "gpt-5.4-mini"
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_temperature: float = 0
    llm_max_retries: int = 2
    mock_tools_enabled: bool = True


def load_config() -> AppConfig:
    provider = getenv("INVESTORY_LLM_PROVIDER", "openai")
    provider_env = PROVIDER_ENV.get(provider, PROVIDER_ENV["openai"])

    return AppConfig(
        llm_provider=provider,
        default_model=getenv("INVESTORY_DEFAULT_MODEL", "gpt-5.4-mini"),
        llm_base_url=getenv(provider_env["base_url"]),
        llm_api_key=getenv(provider_env["api_key"]),
        llm_temperature=float(getenv("INVESTORY_LLM_TEMPERATURE", "0")),
        llm_max_retries=int(getenv("INVESTORY_LLM_MAX_RETRIES", "2")),
    )
```

这里用显式 `PROVIDER_ENV`，目的是避免 `google_genai` 自动拼接成 `GOOGLE_GENAI_API_KEY` 这类不符合实际习惯的环境变量名。

### Step 2：实现 `agent_core/runtime/model_factory.py`

目的：根据 `load_config()` 创建 LangChain chat model，并把 provider 差异隔离在 runtime。

```python
from langchain.chat_models import init_chat_model
from langchain_openai import ChatOpenAI

from investory.config import load_config


def create_chat_model():
    config = load_config()

    common = {
        "temperature": config.llm_temperature,
        "max_retries": config.llm_max_retries,
    }

    if config.llm_provider == "openai":
        return ChatOpenAI(
            model=config.default_model,
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
            **common,
        )

    if config.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic

        return ChatAnthropic(
            model=config.default_model,
            api_key=config.llm_api_key,
            base_url=config.llm_base_url,
            **common,
        )

    if config.llm_provider == "google_genai":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=config.default_model,
            google_api_key=config.llm_api_key,
            **common,
        )

    return init_chat_model(config.default_model, **common)
```

实现时要以实际安装版本的 LangChain provider 参数名为准。不同 provider 的 `base_url` 参数名可能不同，所以 `model_factory.py` 是最适合集中处理差异的地方。

### Step 3：新增 `agent_core/runtime/provider_smoke.py`

目的：先验证配置和模型接入，不让任务执行器问题和 provider 接入问题混在一起。

```python
from investory.agent_core.runtime.model_factory import create_chat_model


def main() -> None:
    model = create_chat_model()
    response = model.invoke("用一句话回答：Investory 是什么？")
    print(response.content)


if __name__ == "__main__":
    main()
```

这个脚本只用于本地 smoke test，不承担任务执行器职责。它的验收标准和 Implementation Steps 的 Step 6 保持一致：能完成一次最小模型调用，并且错误信息能定位到缺 key、base url 错误、模型名错误或 provider 包未安装。

### Step 4：新增 `agent_core/task_spec.py`

目的：定义一个任务的最小元数据。正式实现里同时规定 `input_model` 和 `output_model`，让任务输入和模型输出都有明确契约。

```python
from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(slots=True)
class TaskSpec:
    name: str
    prompt_name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
```

### Step 5：新增 `agent_core/result_types.py`

目的：统一任务成功和失败时的返回形状。

这里的 `TaskError` 不应该只是把 Python 异常包装成 `type/message`。它要把失败收束成上层可以判断的结构：发生在哪个阶段、属于哪类错误、能否重试、能否安全展示给用户、是否带有 provider/model/status code 等排查信息。

```python
from typing import Literal

from pydantic import BaseModel


TaskErrorType = Literal[
    "input_validation_failed",
    "prompt_load_failed",
    "model_config_error",
    "provider_auth_error",
    "rate_limited",
    "provider_unavailable",
    "timeout",
    "structured_output_failed",
    "unknown_error",
]

TaskStage = Literal[
    "input_validation",
    "prompt_build",
    "model_call",
    "output_validation",
]


class TaskError(BaseModel):
    error_type: TaskErrorType
    stage: TaskStage
    user_safe_message: str
    retryable: bool = False

    request_id: str | None = None
    provider: str | None = None
    model: str | None = None
    status_code: int | None = None
    retry_count: int = 0
    fallback_used: bool = False

    debug_message: str | None = None


class TaskResult(BaseModel):
    ok: bool
    task_name: str
    result: dict | None = None
    error: TaskError | None = None


def _extract_status_code(exc: Exception) -> int | None:
    status_code = getattr(exc, "status_code", None)
    if isinstance(status_code, int):
        return status_code

    response = getattr(exc, "response", None)
    response_status = getattr(response, "status_code", None)
    if isinstance(response_status, int):
        return response_status

    return None


def normalize_task_error(
    exc: Exception,
    *,
    stage: TaskStage,
    provider: str | None = None,
    model: str | None = None,
    request_id: str | None = None,
    retry_count: int = 0,
    fallback_used: bool = False,
) -> TaskError:
    status_code = _extract_status_code(exc)
    raw_message = str(exc)
    normalized_message = raw_message.lower()

    if stage == "input_validation":
        return TaskError(
            error_type="input_validation_failed",
            stage=stage,
            user_safe_message="输入不符合任务要求，请检查后重试。",
            retryable=False,
            request_id=request_id,
            provider=provider,
            model=model,
            status_code=status_code,
            retry_count=retry_count,
            fallback_used=fallback_used,
            debug_message=raw_message,
        )

    if stage == "prompt_build":
        return TaskError(
            error_type="prompt_load_failed",
            stage=stage,
            user_safe_message="任务配置暂时不可用，请稍后再试。",
            retryable=False,
            request_id=request_id,
            provider=provider,
            model=model,
            status_code=status_code,
            retry_count=retry_count,
            fallback_used=fallback_used,
            debug_message=raw_message,
        )

    if stage == "output_validation":
        return TaskError(
            error_type="structured_output_failed",
            stage=stage,
            user_safe_message="AI 返回结果格式不符合要求，请稍后重试。",
            retryable=True,
            request_id=request_id,
            provider=provider,
            model=model,
            status_code=status_code,
            retry_count=retry_count,
            fallback_used=fallback_used,
            debug_message=raw_message,
        )

    if status_code in {401, 403}:
        error_type: TaskErrorType = "provider_auth_error"
        user_safe_message = "AI 服务配置不可用，请联系维护者检查权限。"
        retryable = False
    elif status_code == 429:
        error_type = "rate_limited"
        user_safe_message = "AI 服务暂时繁忙，请稍后重试。"
        retryable = True
    elif status_code is not None and status_code >= 500:
        error_type = "provider_unavailable"
        user_safe_message = "AI 服务暂时不可用，请稍后重试。"
        retryable = True
    elif isinstance(exc, TimeoutError) or "timeout" in normalized_message:
        error_type = "timeout"
        user_safe_message = "AI 服务响应超时，请稍后重试。"
        retryable = True
    elif isinstance(exc, (ImportError, ValueError)):
        error_type = "model_config_error"
        user_safe_message = "AI 服务配置不可用，请联系维护者检查配置。"
        retryable = False
    else:
        error_type = "unknown_error"
        user_safe_message = "任务执行失败，请稍后重试。"
        retryable = False

    return TaskError(
        error_type=error_type,
        stage=stage,
        user_safe_message=user_safe_message,
        retryable=retryable,
        request_id=request_id,
        provider=provider,
        model=model,
        status_code=status_code,
        retry_count=retry_count,
        fallback_used=fallback_used,
        debug_message=raw_message,
    )
```

字段取舍：

- `error_type` 是稳定的业务错误类型，不直接暴露 `type(exc).__name__`。
- `stage` 表示失败发生在输入校验、prompt 构造、模型调用还是输出校验。
- `retryable` 表示上层是否可以做有限重试；它不是无限重试许可。
- `user_safe_message` 可以返回给用户；`debug_message` 只用于日志或本地调试。
- `provider/model/status_code/retry_count/fallback_used` 用于可观测性和后续 fallback，但第一版可以先不填满。

### Step 6：新增 `agent_core/schemas.py`

目的：定义 `policy_qa` 和 `meeting_minutes` 的输入 schema 与结构化输出 schema。

```python
from pydantic import BaseModel, Field


class PolicyQAInput(BaseModel):
    policy_text: str = Field(description="制度、规则或说明文本")
    question: str = Field(description="需要根据制度文本回答的问题")


class PolicyQAResult(BaseModel):
    answer: str = Field(description="简明结论")
    evidence: list[str] = Field(description="依据要点")
    uncertainty: str = Field(description="不确定性说明")


class MeetingMinutesInput(BaseModel):
    transcript: str = Field(description="会议记录、转写文本或会议原始内容")


class MeetingTodo(BaseModel):
    title: str = Field(description="待办标题")
    owner: str = Field(description="负责人；未知时写'未指定'")
    deadline: str = Field(description="截止时间；未知时写'未指定'")


class MeetingMinutesResult(BaseModel):
    summary: str = Field(description="会议摘要")
    todos: list[MeetingTodo] = Field(description="待办事项")
    risks: list[str] = Field(description="风险或阻塞点")
```

### Step 7：新增 `agent_core/runtime/prompt_loader.py`

目的：从 `agent_core/prompts/` 读取 `.md` prompt 文件。

```python
from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt_text(*parts: str) -> str:
    return PROMPTS_DIR.joinpath(*parts).read_text(encoding="utf-8")
```

这里 `prompt_loader.py` 位于 `agent_core/runtime/`，所以 `parents[1]` 指向 `agent_core/`。

### Step 8：新增 `agent_core/runtime/request_runner.py`

目的：执行一次 `messages + output schema` 的结构化模型调用。

```python
from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from investory.agent_core.runtime.model_factory import create_chat_model


class RequestRunner:
    def __init__(self, model=None) -> None:
        self.model = model or create_chat_model()

    def run(
        self,
        messages: list[BaseMessage],
        output_model: type[BaseModel],
    ) -> BaseModel:
        structured_model = self.model.with_structured_output(output_model)
        return structured_model.invoke(messages)
```

### Step 9：新增 `agent_core/runtime/task_executor.py`

目的：串起 `TaskSpec`、输入校验、prompt、runner 和错误收口。

```python
import json

from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError

from investory.agent_core.result_types import TaskResult, normalize_task_error
from investory.agent_core.runtime.prompt_loader import load_prompt_text
from investory.agent_core.runtime.request_runner import RequestRunner
from investory.agent_core.task_spec import TaskSpec


class TaskExecutor:
    def __init__(self, runner: RequestRunner | None = None) -> None:
        self.runner = runner or RequestRunner()

    def build_messages(self, spec: TaskSpec, payload: dict):
        system_prompt = load_prompt_text("base", "system.md")
        common_rules = load_prompt_text("base", "common_rules.md")
        task_prompt = load_prompt_text("tasks", f"{spec.prompt_name}.md")

        prompt = ChatPromptTemplate(
            [
                ("system", system_prompt),
                ("human", task_prompt),
            ]
        )

        return prompt.invoke(
            {
                "common_rules": common_rules,
                "input_json": json.dumps(payload, ensure_ascii=False, indent=2),
            }
        ).messages

    def run(self, spec: TaskSpec, payload: dict) -> TaskResult:
        try:
            validated_input = spec.input_model.model_validate(payload)
        except ValidationError as exc:
            return TaskResult(
                ok=False,
                task_name=spec.name,
                error=normalize_task_error(exc, stage="input_validation"),
            )

        try:
            messages = self.build_messages(spec, validated_input.model_dump())
        except Exception as exc:
            return TaskResult(
                ok=False,
                task_name=spec.name,
                error=normalize_task_error(exc, stage="prompt_build"),
            )

        try:
            parsed = self.runner.run(messages, spec.output_model)
        except ValidationError as exc:
            return TaskResult(
                ok=False,
                task_name=spec.name,
                error=normalize_task_error(exc, stage="output_validation"),
            )
        except Exception as exc:
            return TaskResult(
                ok=False,
                task_name=spec.name,
                error=normalize_task_error(exc, stage="model_call"),
            )

        return TaskResult(
            ok=True,
            task_name=spec.name,
            result=parsed.model_dump(),
        )
```

如果后续 `RequestRunner` 能拿到当前 provider、model、request id、retry count，就应该把这些元数据传给 `normalize_task_error()`：

```python
error=normalize_task_error(
    exc,
    stage="model_call",
    provider=config.llm_provider,
    model=config.default_model,
    request_id=request_id,
    retry_count=retry_count,
)
```

`task_executor.py` 是最小执行器本体。它可以知道任务、输入 schema、prompt、runner 和错误收口，但不应该直接知道模型 provider 的具体调用细节。它的职责是把失败标记到正确阶段，并交给 `normalize_task_error()` 归一化。

第一版错误处理策略：

- 输入校验失败：`input_validation_failed`，不重试。
- prompt 文件缺失或构造失败：`prompt_load_failed`，不重试，提示任务配置不可用。
- 模型调用失败：根据 status code 或异常内容归一化为鉴权、限流、服务不可用、超时或未知错误。
- 结构化输出校验失败：`structured_output_failed`，允许上层做一次有限重试或修复。
- 不返回原始异常堆栈、API key、完整 prompt 或未脱敏业务数据给用户。

### Step 10：新增 prompt 文件

目的：给最小执行器提供可加载的 `.md` prompt，先只放两个共享 prompt 和两个任务 prompt。

#### `agent_core/prompts/base/system.md`

```md
你是一个严格按要求执行任务的投资学习助手。

你的输出仅用于学习、理解、整理和复盘，不构成投资建议。
```

#### `agent_core/prompts/base/common_rules.md`

```md
1. 只能根据输入数据作答，不要补造事实。
2. 信息不足时必须明确说明不确定性。
3. 对投资、理财、基金、证券相关内容，必须保持学习辅助定位。
4. 不直接给出买入、卖出、择时、仓位建议。
5. 必须输出符合指定 schema 的结构化结果。
```

#### `agent_core/prompts/tasks/policy_qa.md`

```md
请根据提供的制度文本回答问题。

执行要求：
{common_rules}

输入数据（JSON）：
{input_json}
```

#### `agent_core/prompts/tasks/meeting_minutes.md`

```md
请根据输入内容整理会议纪要。

执行要求：
{common_rules}

你需要提取：
1. 会议摘要
2. 待办事项
3. 风险或阻塞点

输入数据（JSON）：
{input_json}
```

### Step 11：新增 `agent_core/tasks.py`

目的：用一个简单模块注册第 1-1 课要跑通的两个任务。

```text
src/investory/agent_core/tasks.py
```

```python
from investory.agent_core.schemas import (
    MeetingMinutesInput,
    MeetingMinutesResult,
    PolicyQAInput,
    PolicyQAResult,
)
from investory.agent_core.task_spec import TaskSpec


POLICY_QA_TASK = TaskSpec(
    name="policy_qa",
    prompt_name="policy_qa",
    input_model=PolicyQAInput,
    output_model=PolicyQAResult,
)

MEETING_MINUTES_TASK = TaskSpec(
    name="meeting_minutes",
    prompt_name="meeting_minutes",
    input_model=MeetingMinutesInput,
    output_model=MeetingMinutesResult,
)

TASKS = {
    POLICY_QA_TASK.name: POLICY_QA_TASK,
    MEETING_MINUTES_TASK.name: MEETING_MINUTES_TASK,
}
```

不要一开始做复杂 registry。两个任务跑通后，再根据重复模式决定是否抽象。

### Step 12：跑任务 smoke test

目的：验证完整链路能先校验 payload，再从 `TaskSpec + payload` 返回结构化 `TaskResult`。

```python
from investory.agent_core.runtime.task_executor import TaskExecutor
from investory.agent_core.tasks import POLICY_QA_TASK


executor = TaskExecutor()

result = executor.run(
    POLICY_QA_TASK,
    {
        "policy_text": "赎回申请通常在交易日提交，具体到账时间以基金公司规则为准。",
        "question": "基金赎回多久到账？",
    },
)

print(result.model_dump())
```

## 为什么这套适合 Investory

- 目录边界和 `investory-最小任务执行器目录建议.md` 保持一致。
- `agent_core` 保存 Investory 自己的任务核心，不把项目结构交给 LangChain。
- `runtime` 表示一次任务真正跑起来的执行层，语义清楚。
- prompt 放在 `.md` 文件里，后续调优、评测和版本对照更方便。
- LangChain 只负责模型接入、prompt 组装和结构化输出，替换成本较低。
- 后续可以自然升级到 tools、workflow、LangGraph 或 OpenAI Agents SDK，但现在不用提前引入复杂度。

## 当前阶段不建议做的事

现在先不要直接做这些：

- 新建顶层 `agents/` 大目录
- 新建顶层 `llm/` 大目录
- 把 prompt 写成 Python 大字符串常量
- 做复杂 prompt fragments
- 做多级 prompt 继承
- 做通用 prompt registry
- 一上来使用 LangChain agent
- 一上来使用 LangGraph
- 一上来混入工具调用循环

第 1-1 课最重要的是：

1. 先有一个清楚的 `agent_core/runtime/task_executor.py`
2. 先有一个清楚的 `agent_core/prompts/`
3. 先把 `policy_qa` 和 `meeting_minutes` 跑通
4. 统一结构化结果和错误收口

## 一句话结论

Investory 可以用 LangChain，但最合适的方式不是“把 Investory 做成 LangChain 项目”，而是“让 LangChain 成为 `agent_core/runtime` 里的薄实现层”。

## 参考资料

- LangChain Overview: https://docs.langchain.com/oss/python/langchain/overview
- LangChain Install: https://docs.langchain.com/oss/python/langchain/install
- LangChain Structured Output: https://docs.langchain.com/oss/python/langchain/structured-output
- LangChain Models: https://docs.langchain.com/oss/python/langchain/models
- `init_chat_model`: https://reference.langchain.com/python/langchain/chat_models/base/init_chat_model
- `ChatPromptTemplate`: https://reference.langchain.com/python/langchain-core/prompts/chat/ChatPromptTemplate
