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

## 八、Implementation Steps（可执行版）

下面这版按“先可跑通，再替换真实抓取”组织，建议按顺序执行。

### Step 1：新增 Tool Contract

修改文件：

```text
src/investory/agent_core/contracts/tool_contract.py
```

实现内容：

- 新建 `ToolCall`、`ToolResult` 两个 Pydantic 模型。
- `tool_name` 先只支持 `fetch_instrument_profile`。

完成检查：

- 能在 REPL 或测试中成功实例化 `ToolCall` / `ToolResult`。

### Step 2：实现工具函数（先 Mock）

修改文件：

```text
src/investory/agent_core/tools/instrument_profile.py
```

实现内容：

- 实现 `fetch_instrument_profile(instrument_name_or_code)`。
- 第一版先返回固定 mock 结构（包含 `source_material`、`sources`、`as_of`）。
- 对空字符串和非法输入返回 `ok=False`。

完成检查：

- 新增最小单测验证成功/失败两个分支。

### Step 3：扩展 Action 契约

修改文件：

```text
src/investory/agent_core/contracts/action_contract.py
```

实现内容：

- 在 `ActionName` 增加 `fetch_then_run_instrument_brief`。
- 不改现有 `ActionResult` 结构，保持向后兼容。

完成检查：

- 现有 action 相关测试仍通过。

### Step 4：在 Planner 增加路由规则

修改文件：

```text
src/investory/agent_core/runtime/decision_planner.py
```

实现内容：

- 当 task 为 `instrument_brief`、且仅缺 `source_material` 时：
  - 产出 `TaskDecision(action=\"fetch_then_run_instrument_brief\")`。
  - `params` 带上 `instrument_name_or_code` 和原始 `payload`。
- 其他情况保持原逻辑。

完成检查：

- `tests/test_decision_planner.py` 覆盖此分支并通过。

### Step 5：扩展 Validator

修改文件：

```text
src/investory/agent_core/actions/validator.py
```

实现内容：

- 新 action 校验 `instrument_name_or_code` 必填。
- 缺失时返回/抛出与现有风格一致的校验错误。

完成检查：

- `tests/test_action_validator.py` 新增通过与失败用例。

### Step 6：新增 Executor（核心）

修改文件：

```text
src/investory/agent_core/actions/executors.py
```

实现内容：

1. 调工具 `fetch_instrument_profile`。
2. 若 `ok=True`：
   - 从 `params.payload` 复制原 payload；
   - 回填 `source_material`；
   - 调用 `TaskExecutor.run(spec, payload)`；
   - 用现有 `action_result_from_task_result` 返回结果。
3. 若 `ok=False`：
   - 返回 `status=\"requires_user_input\"`；
   - `user_message` 提示用户粘贴来源材料。

完成检查：

- `tests/test_action_executors.py` 覆盖成功与降级分支。

### Step 7：注册 Router

修改文件：

```text
src/investory/agent_core/actions/router.py
```

实现内容：

- 在 `_default_executors` 增加：
  - `\"fetch_then_run_instrument_brief\": FetchThenRunInstrumentBriefExecutor(...)`

完成检查：

- `tests/test_action_router.py` 校验路由正确。

### Step 8：补齐 DecisionFlow 端到端

修改文件：

```text
tests/test_decision_flow.py
```

实现内容：

- 构造“仅 instrument code 输入”的请求。
- mock 工具成功时，断言最终 `TaskResult.ok is True`。
- mock 工具失败时，断言返回可追问状态（不崩溃）。

完成检查：

- `python -m pytest tests/test_decision_flow.py`

### Step 9：真实公开数据替换（最后做）

修改文件：

```text
src/investory/agent_core/tools/instrument_profile.py
```

实现内容：

- 将 mock 替换为真实抓取/请求逻辑（仅公开来源）。
- 增加超时、解析失败、空结果保护。
- 固定输出结构不变，避免上层改动。

完成检查：

- 回归执行相关测试文件并通过：
  - `tests/test_decision_planner.py`
  - `tests/test_action_validator.py`
  - `tests/test_action_router.py`
  - `tests/test_action_executors.py`
  - `tests/test_decision_flow.py`

## 九、完成定义（DoD）

满足以下条件即算本次实践完成：

- 用户只给 `instrument_name_or_code` 时，不会立即卡在缺字段追问。
- 系统会优先尝试工具补全 `source_material`。
- 工具失败时可安全降级到追问，不影响主流程稳定性。
- 新增 action 与执行路径均有测试覆盖。
