# Investory LangGraph 最小编排实现计划

## 目标

基于当前建议 flow，实现一条很薄的 LangGraph 编排链路：

```text
接收用户请求
-> 判断是否缺字段
-> 判断是否属于投资建议请求
-> 如果是学习任务，映射到 qa / summary / brief
-> 调用现有 TaskExecutor
-> 返回 TaskResult
```

这条实现的核心约束是：

- 编排层只负责“判断与分流”
- 现有 `TaskExecutor` 继续作为最小任务执行单元
- 不把 `TaskExecutionPipeline`、`RequestRunner` 拆成新的 graph 节点

## 现状和切入点

当前项目已有稳定的最小执行链路：

```text
TaskSpec
-> TaskExecutor
-> prompt_loader
-> RequestRunner
-> structured result
```

对应代码主要在：

- `src/investory/agent_core/runtime/task_executor.py`
- `src/investory/agent_core/runtime/task_execution_pipeline.py`
- `src/investory/agent_core/runtime/request_runner.py`
- `src/investory/agent_core/tasks.py`

当前 `/tasks` 接口是“已知 task_type 后直接执行”的入口，不适合直接承接这次“先判断，再决定 task”的 flow。

因此建议：

- 保留现有 `/tasks` 不动
- 新增一个 LangGraph 驱动的“学习入口”接口

## 设计原则

### 1. 不重做已有执行链路

LangGraph 只负责入口判断和分支路由。

一旦确定是可执行学习任务，就直接复用现有：

- `resolve_task_spec(...)`
- `TaskExecutor.run(...)`

### 2. 能用本地规则判断的，不先交给 LLM

以下事情优先本地做：

- 缺失字段识别
- `qa` / `summary` / `brief` 的初步映射

LLM 节点只负责一个更窄的问题：

- 这是不是投资建议请求

### 3. 保持对外返回稳定

不管走哪条分支，最终都统一收口成 `TaskResult`，再复用现有 gateway response 转换逻辑。

## 建议 graph 形态

```text
START
-> check_missing_fields
   -> [missing] build_missing_input_result -> END
   -> [complete] decide_policy
-> decide_policy
   -> [advice] build_refusal_result -> END
   -> [learning] resolve_task_spec
-> resolve_task_spec
-> execute_task
-> END
```

说明：

- graph 外先组装初始 state，再调用 `graph.invoke(...)`
- `check_missing_fields`：本地规则判断字段是否足够
- `decide_policy`：LLM 或规则判断是否属于投资建议请求
- `resolve_task_spec`：把候选 task 映射到现有任务定义
- `execute_task`：调用现有 `TaskExecutor`

## 文件级 implementation steps

### Step 1. 定义新的 gateway request schema

目标：给 LangGraph 编排入口单独建一个请求模型，不污染现有 `/tasks` 语义。

建议修改：

- `src/investory/gateway/schemas.py`

新增：

- `LearningEntryRequest`

建议字段：

```python
class LearningEntryRequest(BaseModel):
    payload: dict[str, Any]
    session_id: NonEmptyString | None = None
```

这一层不要强行做 task-specific schema，因为这条 flow 本身就是用来处理字段可能不完整的输入。

响应建议继续复用：

- `TaskResponse`

## Step 2. 定义 LangGraph 专用 state

目标：把“入口判断阶段”的中间结果和下游执行结果放到单独 state 里。

建议新增：

- `src/investory/agent_core/contracts/learning_entry_state.py`

建议字段至少包括：

```python
session_id: str
input_payload: dict[str, Any]
missing_fields: list[str]
candidate_task_type: str | None
decision: str | None
resolved_task_name: str | None
task_payload: dict[str, Any] | None
output: TaskResult | None
error: TaskError | None
```

其中 `decision` 建议限制为固定值：

- `ask_for_missing_input`
- `refuse_and_redirect`
- `execute_learning_task`

## Step 3. 实现本地规则层

目标：先用 deterministic 规则处理最容易、最稳定的判断，减少不必要模型调用。

建议新增：

- `src/investory/agent_core/runtime/flow/learning_entry_rules.py`

建议实现两个 helper：

1. `detect_missing_fields(payload) -> list[str]`
2. `infer_candidate_task_type(payload) -> Literal["qa", "summary", "brief"] | None`

第一版规则可以先写死为：

- 有 `material_text` 且有 `question` -> `qa`
- 有 `material_text` 但没有 `question` -> `summary`
- 有 `instrument_name_or_code` 且有 `source_material` -> `brief`
- 其他情况 -> 返回缺字段或无法判断

这里要注意一点：

- `material_text` only -> `summary` 是一个产品假设
- 如果后面发现用户真实输入更复杂，再补充歧义处理

## Step 4. 定义“投资建议判断”结构化输出

目标：把 LLM 判断范围缩小到一个安全问题，不让它同时做多种决策。

建议新增：

- `src/investory/agent_core/runtime/flow/learning_entry_decision.py`
- `src/investory/agent_core/prompts/flows/learning_entry_decision.md`

建议定义一个结构化输出模型，例如：

```python
class LearningEntryDecision(BaseModel):
    route_action: Literal["refuse_and_redirect", "execute_learning_task"]
    reason: str
```

这个节点只回答：

- 当前请求是否属于投资建议请求

不要让这个节点负责：

- 缺字段判断
- task_type 映射
- 最终响应格式拼装

## Step 5. 实现 LangGraph flow 本体

目标：把建议流程图真正落成 `StateGraph`。

建议新增：

- `src/investory/agent_core/runtime/flow/learning_entry_flow.py`

建议内容：

1. 定义 graph state 类型
2. 在 `LearningEntryFlow.run(...)` 里组装初始 state
3. 实现节点函数
4. 组装 `StateGraph`
5. 编译 graph

建议节点列表：

- `check_missing_fields`
- `decide_policy`
- `resolve_task_spec`
- `execute_task`
- `build_missing_input_result`
- `build_refusal_result`

建议条件边：

- `check_missing_fields`
  - missing -> `build_missing_input_result`
  - complete -> `decide_policy`
- `decide_policy`
  - advice -> `build_refusal_result`
  - learning -> `resolve_task_spec`
- `resolve_task_spec` -> `execute_task`

### 节点职责建议

`LearningEntryFlow.run(...)`

- 初始化 `session_id`
- 初始化 state 默认值
- 保留原始 `payload`
- 调用 `graph.invoke(initial_state)`

`check_missing_fields`

- 调用 `detect_missing_fields(...)`
- 调用 `infer_candidate_task_type(...)`
- 如果缺字段，写入 `decision="ask_for_missing_input"`

`decide_policy`

- 基于候选任务和原始输入做投资建议判断
- 如果是投资建议请求，写入 `decision="refuse_and_redirect"`
- 否则写入 `decision="execute_learning_task"`

`resolve_task_spec`

- 把 `qa` / `summary` / `brief` 映射到现有 alias
- 通过 `resolve_task_spec(...)` 得到 `TaskSpec`

`execute_task`

- 调用现有 `TaskExecutor.run(spec, payload)`
- 把结果写回 `state.output`

`build_missing_input_result`

- 构造一个统一的 `TaskResult`
- `result` 里建议放：
  - `action`
  - `missing_fields`
  - `message`

`build_refusal_result`

- 构造一个统一的 `TaskResult`
- `result` 里建议放：
  - `action`
  - `message`
  - `suggested_learning_direction`

## Step 6. 做一个薄的 flow factory

目标：让 graph 的构造和运行解耦，便于 app 初始化时注入依赖。

建议新增：

- `build_learning_entry_flow(...)`

建议放在：

- `src/investory/agent_core/runtime/flow/learning_entry_flow.py`

或单独放一个：

- `src/investory/agent_core/runtime/flow/factory.py`

建议签名：

```python
def build_learning_entry_flow(
    executor: TaskExecutor | None = None,
    runner: RequestRunner | None = None,
):
    ...
```

注意：

- flow 内部真正执行任务时，应优先复用传入的 `TaskExecutor`
- 不要在节点内部到处临时 new 执行器
- 初始 state 的组装放在 flow 的 `run(...)` 包装层，不额外建 `prepare_request` 节点

## Step 7. 接入 FastAPI

目标：新增一个编排入口，不破坏现有 `/tasks` 契约。

建议修改：

- `src/investory/gateway/api.py`
- `src/investory/main.py`

建议新增 endpoint：

```text
POST /learning-entry
```

建议流程：

1. 在 `create_app()` 时构造 flow，并挂到 `app.state.learning_entry_flow`
2. endpoint 读取 `LearningEntryRequest`
3. 调用 `learning_entry_flow.run(...)` 或等价封装
4. 使用现有 `_to_gateway_response(...)` 转成 `TaskResponse`

现有 `/tasks` 保持不动，用于：

- 已知 `task_type` 的直接调用

新的 `/learning-entry` 用于：

- 未知 task_type，需要先判断再进入任务执行器的调用

## Step 8. 补齐测试

目标：确保 flow 行为和接口行为都可回归。

建议新增测试：

- `tests/test_learning_entry_rules.py`
- `tests/test_learning_entry_flow.py`
- `tests/test_learning_entry_gateway_api.py`

最少覆盖这些 case：

1. `qa` 缺字段

- 输入有 `question`，没有 `material_text`
- 预期返回补充信息提示

2. `brief` 缺字段

- 输入有 `instrument_name_or_code`，没有 `source_material`
- 预期返回补充信息提示

3. 投资建议请求

- 例如“我后天买某基金合适吗？”
- 预期走拒答分支，不调用 `TaskExecutor`

4. 完整 `qa`

- 输入完整 `material_text + question`
- 预期进入 `finance_qa`

5. 完整 `summary`

- 输入只有 `material_text`
- 预期进入 `learning_material_summary`

6. 完整 `brief`

- 输入 `instrument_name_or_code + source_material`
- 预期进入 `instrument_brief`

7. 下游执行错误透传

- `TaskExecutor` 返回 `ok=False`
- flow 应原样收口，不重新包装成另一套错误结构

## Step 9. 补 smoke 和文档

目标：让这条 flow 有最小可验证入口。

建议补：

- 一个 `/learning-entry` 请求示例文档
- 一个最小 smoke 样例

建议文档位置：

- `docs/1-2/` 下新增示例文件

示例输入至少覆盖：

- 缺字段
- 投资建议请求
- QA 学习任务

## 推荐落地顺序

建议按下面顺序实现，避免一开始把范围做散：

1. gateway request schema
2. LangGraph state
3. 本地规则判断
4. decision prompt + structured output
5. LangGraph flow skeleton
6. `execute_task` 接入现有 `TaskExecutor`
7. FastAPI endpoint
8. tests
9. smoke / docs

## 第一阶段验收标准

第一阶段只验收最小闭环，不追求复杂能力：

1. `/tasks` 现有行为不回归
2. `/learning-entry` 可以跑通三类分支：
   - 缺字段
   - 投资建议拒答
   - 可执行学习任务
3. `qa` / `summary` / `brief` 最终仍通过现有 `TaskExecutor` 执行
4. 最终输出统一为 `TaskResult` -> `TaskResponse`
5. graph 中没有重复实现 `TaskExecutionPipeline` 内部步骤

## 不建议本阶段做的事

以下内容建议明确排除，避免最小编排做重：

- 并行分支
- 人工中断与恢复
- 持久化 checkpoint
- 多轮澄清对话状态管理
- 把 `RequestRunner` 或 prompt build 再拆成 graph 节点
- 在一个节点里同时做“安全判断 + task 识别 + 回复生成”

## 一句话结论

这次 LangGraph 实现的正确边界应该是：

```text
用 LangGraph 做入口分流，
用现有 TaskExecutor 做任务执行。
```

如果这个边界守住，整个实现会比较稳，也更贴合当前项目的最小执行模型。
