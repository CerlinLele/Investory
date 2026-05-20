# Investory 显式重试策略设计

## 背景

调整前，最小任务执行器把 `INVESTORY_LLM_MAX_RETRIES` 读入 `AppConfig.llm_max_retries` 后，在 `model_factory.py` 中作为 `max_retries` 传给 LangChain provider wrapper。

这意味着一次模型调用进入 provider SDK 后，provider SDK 会先根据自己的规则决定是否自动重试。等异常最终冒回 Investory 时，`TaskExecutor` 才会调用 `normalize_task_error()` 生成 `TaskError.retryable`。

因此当前实际顺序是：

```text
TaskExecutor.run()
-> RequestRunner.run()
-> structured_model.invoke(messages)
-> LangChain / provider SDK 内部按 max_retries 自动重试
-> 如果最终仍失败，异常抛出
-> TaskExecutor 捕获异常
-> normalize_task_error(...)
-> 生成 retryable=True/False
```

这里的问题是：Investory 自己的 `retryable` 判断发生在 provider 自动重试之后。也就是说，当前不是 Investory 先看错误码再决定是否重试，而是 provider SDK 先按内部策略重试。

## 目标

把重试控制权收回到 Investory runtime：

```text
TaskExecutor.run()
-> RequestRunner.run()
   -> 第 1 次 invoke
   -> 捕获异常
   -> 提取 status_code / 异常类型
   -> 判断是否 retryable
   -> 未超过 max_retries 才重试
   -> 超过后抛出带 retry_count 的异常
-> TaskExecutor 归一化 TaskError
```

核心目标：

1. Provider SDK 自身重试关闭，避免双重重试。
2. Investory 自己先请求一次，失败后再看错误类型。
3. 只对短暂故障重试。
4. 所有重试都有最大次数。
5. 最终错误要带 `retry_count`，便于日志、排查和后续观测。

## 配置语义

`INVESTORY_LLM_MAX_RETRIES=2` 的含义定义为：

```text
初始请求 1 次 + 最多重试 2 次 = 最多 3 次 invoke
```

配置仍保留在：

```env
INVESTORY_LLM_MAX_RETRIES=2
```

但语义从“传给 provider SDK 的自动重试次数”改为“Investory runtime 自己控制的最大重试次数”。

## 重试分类

### 可以重试

这些错误通常代表短暂失败：

- `408` request timeout
- `409` lock timeout / conflict timeout
- `429` rate limit
- `5xx` provider unavailable / upstream error
- `TimeoutError`
- 网络连接类异常

### 不应该重试

这些错误通常不是短暂失败，盲目重试只会浪费成本：

- `400` bad request
- `401 / 403` authentication / permission error
- `404` model not found / endpoint not found
- `422` schema or request parameter problem
- `ImportError`
- `ValueError`
- `input_validation`
- `prompt_build`

### 结构化输出失败

`output_validation` / `structured_output_failed` 不应该放进普通 HTTP/status retry loop。

原因是它不是纯 provider 网络错误，而是模型输出没有满足结构化契约。它可以考虑一次独立的有限重试，但必须和 `429 / 5xx / timeout` 这类 provider transient retry 分开。

建议第一版策略：

- 普通模型调用错误：由 `INVESTORY_LLM_MAX_RETRIES` 控制，例如 `2` 表示初始调用之外最多再重试 2 次。
- 结构化输出失败：单独允许最多 `1` 次重试，先不暴露成 env 配置。
- 结构化输出重试不使用 provider retry policy，不参与 `is_retryable_model_error()`。
- 重试仍失败后返回：

```text
error_type=structured_output_failed
retryable=True
```

这表示上层理论上仍可做 repair call、人工复核或更复杂的修复流程。

## Implementation Steps

### Step 1: 关闭 provider SDK 自动重试

修改 `src/investory/agent_core/runtime/model_factory.py`。

当前逻辑：

```python
def _common_model_kwargs(config: AppConfig) -> dict[str, Any]:
    return {
        "temperature": config.llm_temperature,
        "max_retries": config.llm_max_retries,
    }
```

改为：

```python
def _common_model_kwargs(config: AppConfig) -> dict[str, Any]:
    return {
        "temperature": config.llm_temperature,
        "max_retries": 0,
    }
```

这样 LangChain/OpenAI SDK 不会先替 Investory 重试。`config.llm_max_retries` 只给 Investory 自己的 retry loop 使用。

### Step 2: 新增 retry policy

新增文件：

```text
src/investory/agent_core/runtime/retry_policy.py
```

建议职责：

```python
def extract_status_code(exc: Exception) -> int | None:
    ...

def is_retryable_model_error(exc: Exception) -> bool:
    ...

def calculate_retry_delay(retry_count: int) -> float:
    ...
```

第一版策略：

```python
RETRYABLE_STATUS_CODES = {408, 409, 429}

def is_retryable_model_error(exc: Exception) -> bool:
    status_code = extract_status_code(exc)
    if status_code in RETRYABLE_STATUS_CODES:
        return True
    if status_code is not None and status_code >= 500:
        return True
    if isinstance(exc, TimeoutError):
        return True
    if "timeout" in str(exc).lower():
        return True
    return False
```

delay 第一版可以用指数退避：

```python
def calculate_retry_delay(retry_count: int) -> float:
    return min(0.5 * (2 ** retry_count), 8.0)
```

后续再加 jitter 和总 deadline。

### Step 3: 在 RequestRunner 实现显式 retry loop

修改 `src/investory/agent_core/runtime/request_runner.py`。

目标结构：

```python
from time import sleep

from langchain_core.messages import BaseMessage
from pydantic import BaseModel

from investory.agent_core.runtime.model_factory import create_chat_model
from investory.agent_core.runtime.retry_policy import (
    calculate_retry_delay,
    is_retryable_model_error,
)
from investory.config import load_config


class ModelCallError(Exception):
    def __init__(self, original: Exception, retry_count: int) -> None:
        super().__init__(str(original))
        self.original = original
        self.retry_count = retry_count
        self.status_code = getattr(original, "status_code", None)
        self.response = getattr(original, "response", None)


class RequestRunner:
    def __init__(self, model=None, max_retries: int | None = None) -> None:
        self.config = load_config()
        self.model = model or create_chat_model(self.config)
        self.max_retries = (
            self.config.llm_max_retries if max_retries is None else max_retries
        )

    def run(
        self,
        messages: list[BaseMessage],
        output_model: type[BaseModel],
    ) -> BaseModel:
        structured_model = self.model.with_structured_output(output_model)
        retry_count = 0

        while True:
            try:
                return structured_model.invoke(messages)
            except Exception as exc:
                if retry_count >= self.max_retries:
                    raise ModelCallError(exc, retry_count) from exc

                if not is_retryable_model_error(exc):
                    raise ModelCallError(exc, retry_count) from exc

                sleep(calculate_retry_delay(retry_count))
                retry_count += 1
```

说明：

- 第一次请求失败时，`retry_count` 仍为 `0`。
- 每发生一次实际重试，`retry_count` 增加。
- 达到上限后抛出 `ModelCallError`。
- 不可重试错误立即抛出 `ModelCallError`，不会等待和重试。

### Step 4: TaskExecutor 读取 retry_count

修改 `src/investory/agent_core/runtime/task_executor.py`。

目标是捕获 `ModelCallError`，把 `retry_count` 传入 `normalize_task_error()`：

```python
from investory.agent_core.runtime.request_runner import ModelCallError, RequestRunner
```

调用部分改为：

```python
try:
    parsed = self.runner.run(messages, spec.output_model)
except ValidationError as exc:
    return TaskResult(
        ok=False,
        task_name=spec.name,
        error=normalize_task_error(exc, stage="output_validation"),
    )
except ModelCallError as exc:
    return TaskResult(
        ok=False,
        task_name=spec.name,
        error=normalize_task_error(
            exc.original,
            stage="model_call",
            retry_count=exc.retry_count,
        ),
    )
except Exception as exc:
    return TaskResult(
        ok=False,
        task_name=spec.name,
        error=normalize_task_error(exc, stage="model_call"),
    )
```

### Step 5: 结构化输出失败的有限重试

结构化输出失败要单独处理，不复用 `ModelCallError`。

建议在 `src/investory/agent_core/runtime/request_runner.py` 新增：

```python
class StructuredOutputError(Exception):
    def __init__(self, original: ValidationError, retry_count: int) -> None:
        super().__init__(str(original))
        self.original = original
        self.retry_count = retry_count
```

然后让 `RequestRunner` 接收一个独立参数：

```python
class RequestRunner:
    def __init__(
        self,
        model=None,
        max_retries: int | None = None,
        structured_output_max_retries: int = 1,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        ...
        self.structured_output_max_retries = structured_output_max_retries
```

`run()` 里维护两个独立计数：

```python
model_retry_count = 0
structured_output_retry_count = 0

while True:
    try:
        return structured_model.invoke(messages)
    except ValidationError as exc:
        if structured_output_retry_count >= self.structured_output_max_retries:
            raise StructuredOutputError(
                exc,
                structured_output_retry_count,
            ) from exc

        structured_output_retry_count += 1
        continue
    except Exception as exc:
        if model_retry_count >= self.max_retries:
            raise ModelCallError(exc, model_retry_count) from exc

        if not is_retryable_model_error(exc):
            raise ModelCallError(exc, model_retry_count) from exc

        self.sleep_fn(calculate_retry_delay(model_retry_count))
        model_retry_count += 1
```

说明：

- `structured_output_max_retries=1` 表示初始结构化调用失败后，再尝试 1 次。
- 结构化输出重试可以先不 sleep，因为它不是限流或服务端短暂不可用。
- 如果后续能拿到原始模型文本，可以把第二次调用升级为 repair call；第一版先只做同 prompt 的一次有限重试。
- 这类失败最终仍归一化为 `output_validation` 阶段，而不是 `model_call` 阶段。

`TaskExecutor` 需要额外捕获 `StructuredOutputError`：

```python
from investory.agent_core.runtime.request_runner import (
    ModelCallError,
    RequestRunner,
    StructuredOutputError,
)

...

except StructuredOutputError as exc:
    return TaskResult(
        ok=False,
        task_name=spec.name,
        error=normalize_task_error(
            exc.original,
            stage="output_validation",
            retry_count=exc.retry_count,
        ),
    )
except ValidationError as exc:
    return TaskResult(
        ok=False,
        task_name=spec.name,
        error=normalize_task_error(exc, stage="output_validation"),
    )
```

`ValidationError` 兜底分支保留，方便测试 fake runner 或未来其他 structured output 实现直接抛出 Pydantic 错误。

### Step 6: 统一 status code 提取逻辑

当前 `contracts/result_types.py` 里已有 `_extract_status_code()`。

为了避免重复，同时保持目录分层方向正确，status code 提取逻辑应该保留在 `contracts` 侧：

- `contracts/result_types.py` 是通用错误契约，可以提供公共 `extract_status_code()`。
- `runtime/retry_policy.py` 是运行时策略，应该复用 `contracts` 里的提取函数。
- 不要让 `contracts/result_types.py` 反向 import `runtime/retry_policy.py`。

最终结构：

```text
src/investory/agent_core/contracts/result_types.py
  extract_status_code()
  normalize_task_error()
```

```text
src/investory/agent_core/runtime/retry_policy.py
  from investory.agent_core.contracts.result_types import extract_status_code
  is_retryable_model_error()
  calculate_retry_delay()
```

这样依赖方向保持为：

```text
runtime -> contracts
```

而不是：

```text
contracts -> runtime
```

### Step 7: 更新测试

更新 `tests/test_model_factory.py`：

- 确认传给 OpenAI/Anthropic/Google provider 的 `max_retries` 是 `0`。
- 确认 `AppConfig.llm_max_retries` 仍然可以读取环境变量。

新增或更新 `tests/test_request_runner.py`：

- 第一次成功：不重试。
- `429` 第一次失败、第二次成功。
- `503` 第一次失败、第二次成功。
- `503` 按最大次数重试后仍失败，抛出 `ModelCallError`，且 `retry_count` 正确。
- `401` 不重试，直接抛出 `ModelCallError(retry_count=0)`。
- `400` 不重试。
- `TimeoutError` 会重试。
- `ValidationError` 第一次失败、第二次成功时返回成功结果。
- `ValidationError` 达到 `structured_output_max_retries` 后抛出 `StructuredOutputError`，且 `retry_count` 正确。
- `structured_output_max_retries=0` 时，结构化输出失败不重试。

更新 `tests/test_task_executor.py`：

- `ModelCallError` 传入后，最终 `TaskResult.error.retry_count` 等于实际重试次数。
- `429` 最终失败时仍归一化为 `rate_limited` 且 `retryable=True`。
- `401` 最终失败时归一化为 `provider_auth_error` 且 `retryable=False`。
- `StructuredOutputError` 传入后，最终 `TaskResult.error.error_type=structured_output_failed`，`stage=output_validation`，并保留结构化输出重试次数。

新增 `tests/test_retry_policy.py`：

- status code 从 `exc.status_code` 提取。
- status code 从 `exc.response.status_code` 提取。
- `408 / 409 / 429 / 5xx` 可重试。
- `400 / 401 / 403 / 404 / 422` 不可重试。
- timeout message 可重试。

### Step 8: 更新文档和 env 注释

更新 `.env.example`：

```env
# Investory-controlled model-call retries after inspecting provider errors.
# 2 means one initial call plus up to two retries.
INVESTORY_LLM_MAX_RETRIES=2
```

更新相关设计文档：

- `docs/1-1/investory-langchain-最小任务执行器设计.md`
- `docs/1-1/investory-模型参数取舍备忘.md`
- `docs/1-1/LLM调用失败时的错误收束.md`
- `docs/1-1/investory-显式重试策略设计.md`

重点说明：

- provider SDK retry 关闭。
- Investory runtime 根据错误类型做有限重试。
- `retryable` 是错误收束结果，不等于一定已经发生重试。
- `retry_count` 记录 Investory runtime 实际执行的重试次数。
- 结构化输出失败使用独立的 `structured_output_max_retries=1`，不和 provider HTTP/status retry 共用配置。

## 第一版不做的事

第一版不做这些扩展：

- 不做 fallback provider。
- 不做 streaming retry。
- 不做 structured output repair call；第一版只做同 prompt 的一次有限重试。
- 不做总 deadline。
- 不做成本预算控制。
- 不做复杂 observability event。

这些可以在最小任务执行器跑通后逐步加入。

## 验收标准

1. Provider SDK 的 `max_retries` 被固定为 `0`。
2. `RequestRunner` 至少先执行一次模型调用。
3. 只有 retry policy 判定可重试时才重试。
4. 重试次数不超过 `INVESTORY_LLM_MAX_RETRIES`。
5. 不可重试错误不会重试。
6. 结构化输出失败最多独立重试 1 次，且不使用 provider retry policy。
7. 最终失败时 `TaskError.retry_count` 能反映对应阶段实际执行的重试次数。
8. 现有 `TaskResult` 成功/失败结构保持不变。
9. 单元测试覆盖 retry policy、request runner 和 task executor 的关键路径。

## 一句话结论

Investory 应该关闭 provider SDK 自动重试，在 `RequestRunner` 里把 provider transient retry 和 structured output retry 分开处理；`TaskExecutor` 只负责把最终失败收束成统一的 `TaskError`。
