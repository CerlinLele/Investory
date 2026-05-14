# Investory 第 3-1 课最小工具落地实现清单（fetch_instrument_profile）

## 一、目标与范围

本次只落地一个最小可用工具：

```text
fetch_instrument_profile
```

目标：

- 在 `instrument_brief` 场景中，当用户只提供 `instrument_name_or_code` 时，系统可先自动补全 `source_material`，再执行现有任务模型。

本次明确不做：

- 实盘交易、下单、调仓。
- 账户资产数据读取。
- 需要登录或付费的数据源接入。

## 二、最小接口设计（Tool Interface）

建议新增模块：

```text
src/investory/agent_core/tools/instrument_profile.py
```

### 1) 工具函数签名

```python
fetch_instrument_profile(instrument_name_or_code: str) -> InstrumentProfileToolResult
```

### 2) 行为约束

- 输入为空或无效代码时返回失败（可重试为 `False`）。
- 优先抓取公开来源（官网、交易所、公开 factsheet）。
- 返回结构化摘要，不返回原始 HTML。

## 三、最小契约设计（Contract）

建议新增契约文件：

```text
src/investory/agent_core/contracts/tool_contract.py
```

### 1) ToolCall

```python
class ToolCall(BaseModel):
    tool_name: Literal["fetch_instrument_profile"]
    params: dict[str, Any]
    request_id: str | None = None
```

### 2) ToolResult

```python
class ToolResult(BaseModel):
    tool_name: str
    ok: bool
    data: dict[str, Any] | None = None
    error_type: str | None = None
    error_message: str | None = None
    retryable: bool = False
```

### 3) fetch_instrument_profile 返回 data 建议结构

```python
{
  "instrument_name_or_code": "VTI",
  "source_material": "...供模型消费的纯文本摘要...",
  "sources": [
    "https://...",
    "https://..."
  ],
  "as_of": "2026-05-15"
}
```

说明：

- `source_material` 是给 `instrument_brief` 直接复用的关键字段。
- `sources` 与 `as_of` 用于可追溯与时间标注。

## 四、最小路由接入（Routing / Flow）

目标是“少改主干、可快速验证”。

### 1) 决策层（DecisionPlanner）

文件：

```text
src/investory/agent_core/runtime/decision_planner.py
```

新增一条规则：

- 当 `spec.name == "instrument_brief"`
- 且 `instrument_name_or_code` 已提供
- 且仅缺少 `source_material`

则决策为：

```text
action = "fetch_then_run_instrument_brief"
```

### 2) ActionName 扩展

文件：

```text
src/investory/agent_core/contracts/action_contract.py
```

在 `ActionName` 中新增：

```text
"fetch_then_run_instrument_brief"
```

### 3) ActionValidator 扩展

文件：

```text
src/investory/agent_core/actions/validator.py
```

校验要点：

- `params` 必须包含 `instrument_name_or_code`。
- 可选携带 `payload`（用于保留用户原始输入）。

### 4) ActionExecutor 扩展

文件：

```text
src/investory/agent_core/actions/executors.py
```

新增执行器：

```text
FetchThenRunInstrumentBriefExecutor
```

执行步骤：

1. 调用 `fetch_instrument_profile`。
2. 成功：将 `source_material` 回填到 payload。
3. 调用现有 `TaskExecutor.run(spec, payload)`。
4. 失败：返回 `requires_user_input`，沿用 ask_missing_fields 风格提示用户补充材料。

### 5) ActionRouter 注册

文件：

```text
src/investory/agent_core/actions/router.py
```

把新 action 映射到新 executor。

## 五、最小错误与降级策略

必须有两级降级：

1. 工具调用失败（网络/解析失败）：

- 不直接失败整条请求。
- 转为 `requires_user_input`，提示用户粘贴材料。

2. 工具调用成功但内容质量不足：

- 可继续执行 `instrument_brief`。
- 在结果中通过现有 `uncertainty` 字段提示资料不足。

## 六、最小测试清单（Testing）

## 1) Planner 测试

文件建议：

```text
tests/test_decision_planner.py
```

新增用例：

- `instrument_brief` 缺 `source_material` 但有代码 -> 产出 `fetch_then_run_instrument_brief`。
- 两个字段都缺 -> 仍然 `ask_missing_fields`。

## 2) Validator 测试

文件建议：

```text
tests/test_action_validator.py
```

新增用例：

- 新 action 缺少 `instrument_name_or_code` -> 校验失败。
- 参数完整 -> 校验通过并生成 `ActionCall`。

## 3) Router 测试

文件建议：

```text
tests/test_action_router.py
```

新增用例：

- 新 action 能正确路由到 `FetchThenRunInstrumentBriefExecutor`。

## 4) Executor 测试

文件建议：

```text
tests/test_action_executors.py
```

新增用例：

- 工具成功 -> 回填 `source_material` -> `run_task_model` 成功返回。
- 工具失败 -> 返回 `requires_user_input` + 用户可读提示。

## 5) 端到端流程测试

文件建议：

```text
tests/test_decision_flow.py
```

新增用例：

- 输入仅有 `instrument_name_or_code`，最终能得到 `instrument_brief` 结果。
- 工具异常时，流程返回可追问状态而不是崩溃。

## 七、最小实施顺序（建议按天拆分）

1. 先加 `tool_contract.py` 与 `instrument_profile.py`（可先 mock 数据）。
2. 扩展 `ActionName + planner + validator`。
3. 实现新 executor 并注册 router。
4. 补齐单测（planner/validator/router/executor/flow）。
5. 最后再把 mock 替换成真实公开站点抓取。

## 八、完成定义（DoD）

满足以下条件即算本次实践完成：

- 用户只给 `instrument_name_or_code` 时，不会立即卡在缺字段追问。
- 系统会优先尝试工具补全 `source_material`。
- 工具失败时可安全降级到追问，不影响主流程稳定性。
- 新增 action 与执行路径均有测试覆盖。
