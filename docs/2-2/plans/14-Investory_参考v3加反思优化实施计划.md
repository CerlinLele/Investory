# Investory 参考 v3 加反思优化实施计划

## 背景

参考目录：

```text
C:\Users\hy120\Downloads\zhihullm\agent\lecture\08. 实战——智能文档审查助手\scripts\v3_加反思优化
```

该参考项目是在“文档类型路由 + To-Do 任务拆解 + 依赖图执行 + 风险审批”的基础上，新增了一层报告反思优化：

```text
route_subflow
  -> plan_gen_subflow
  -> dependency graph execution
  -> approval_flow
  -> reflection_flow
```

其中 `reflection_flow` 的核心流程是：

```text
generate_draft
  -> evaluate
  -> revise
  -> evaluate
  -> pass / max_rounds
```

Investory 当前已经有更工程化的投资文档审查链路：

```text
policy gate
  -> classify document type
  -> build review framework
  -> generate todo plan / single-pass review
  -> execute todo plan
  -> assess review risk
  -> final result / pending approval result
```

因此，本计划不建议照搬 Agently / TriggerFlow 实现，而是借鉴 v3 的“报告生成后，用显式标准做有限轮次自检与修订”的流程思想，并接入 Investory 现有 LangGraph、TaskSpec、Pydantic 和 To-Do runner 体系。

## 当前 Investory 已经具备的基础

Investory 已经覆盖 v3 示例中的大部分主链路能力：

- 文档类型路由：`InvestmentDocumentReviewLLMRouter`
- 审查框架选择：`get_review_framework()`
- To-Do plan 生成：`investment_document_review_plan`
- extract / analyze / synthesize 拆分：独立 TaskSpec、prompt 和 Pydantic 模型
- DAG 执行：`TodoExecutionRunner`
- 失败、跳过、重试：`TodoTaskStatus`、`TodoFailurePolicy`
- 长文档处理：chunk extract fan-out、dimension analyze、full document synthesize
- 风险审批：`investment_document_risk_assessment`
- pending approval 输出：`build_pending_approval_result()`
- 结构化测试覆盖：flow、router、rules、todo runner、task models

这些部分不需要重新实现。v3 对 Investory 的新增价值主要集中在最终报告质量控制。

## 最值得借鉴的设计点

### 1. 报告反思优化作为后置质量闸门

v3 的 `reflection_flow` 把最终报告当成一个可验收产物，而不是直接把第一次生成结果返回。

Investory 可以在审查结果生成后、风险评估前增加一个节点：

```text
execute_review_todo_plan / run_single_pass_review
  -> reflect_review_output
  -> assess_review_risk
```

这样风险评估读取的是经过质量检查的结构化审查结果，而不是未经自检的初稿。

### 2. 显式 criteria，而不是泛泛让模型“检查一下”

v3 使用 `REPORT_CRITERIA` 明确报告验收标准。Investory 应将其改造成投资文档审查专用 criteria，例如：

- 审查结果只基于输入文档、To-Do plan、To-Do results 和 deterministic review summary。
- `extracted_facts` 必须来自成功的 extract / analyze / synthesize 结果。
- `risk_findings` 必须有支持证据，不能给出买入、卖出、持有、择时、仓位或收益预测建议。
- 失败或跳过的任务必须体现在 `information_gaps` 或 `boundary_notes` 中。
- `summary` 应简洁、审计友好，并说明关键风险和限制。
- 输出必须保持 `InvestmentDocumentReviewResult` 的结构，不改变外部 API 语义。

### 3. 有限轮次，避免无限自我修正

v3 的 `max_rounds` 是必要安全阀。Investory 第一版建议：

```text
default max_rounds = 1
upper bound max_rounds = 2
```

第一版可以只做“一次 evaluate，一次可选 revise”，避免延迟和成本过高。

### 4. 自评结果要可观测

反思结果不应该只覆盖最终报告，还应留下结构化 metadata，便于后续调试和 prompt 迭代：

- `passed`
- `score`
- `issues`
- `suggestions`
- `safety_flags`
- `rounds`

这些字段可先存在 flow state 中，后续再决定是否暴露到 API response 或日志。

### 5. 审查框架配置可以后续外置

v3 的 `review_framework.yaml` 支持按文档类型配置 `extract_focus` 和 `analyze_focus`。Investory 当前将审查框架写在 `DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE` 中，短期可保持现状。

后续如果需要业务方频繁调整 ETF factsheet、fund prospectus、product brochure 等审查关注点，可以再迁移到：

```text
config/review_frameworks.yaml
```

该迁移与 reflection 不强绑定，不建议放入第一版。

## 不建议照搬的部分

### 1. 不引入 Agently / TriggerFlow

Investory 已经使用 LangGraph 和自研 runtime。引入 Agently 会造成双编排系统并存，增加维护成本。

推荐继续使用：

- `StateGraph`
- `TaskExecutor`
- `RequestRunner`
- `TaskSpec`
- Pydantic input / output models

### 2. 不用 reflection 替代 policy gate

投资建议、实时数据能力、缺字段和低置信度分类仍应由前置规则处理。

Reflection 只负责输出质量，不负责把违规请求“先生成再修正”。

### 3. 不自动修复 To-Do plan 依赖

v3 的 plan validator 会剔除不存在的依赖。Investory 当前 `ensure_valid_todo_plan()` 会显式失败，这更适合生产。

保持当前策略：坏 plan 应暴露为错误，而不是静默修正。

## 推荐目标架构

新增反思任务后，投资文档审查 flow 变为：

```text
START
  -> evaluate_policy_gate
  -> classify_document_type
  -> build_review_framework
  -> generate_review_todo_plan / run_single_pass_review
  -> execute_review_todo_plan
  -> reflect_review_output
  -> assess_review_risk
  -> build_final_result / build_pending_approval_result
  -> END
```

单次短文档路径：

```text
run_single_pass_review
  -> reflect_review_output
  -> assess_review_risk
```

长文档 To-Do 路径：

```text
generate_review_todo_plan
  -> execute_review_todo_plan
  -> reflect_review_output
  -> assess_review_risk
```

如果 `output.ok == false`，reflection 节点直接跳过，保留原错误结果。

## 建议新增或修改的代码位置

### 1. 新增 task model

文件：

```text
src/investory/agent_core/task_models/investment_document_review_reflection.py
```

建议模型：

```python
class InvestmentDocumentReviewReflectionInput(BaseModel):
    document_type: InvestmentDocumentType
    route_confidence: float
    review_goal: str | None = None
    review_result: InvestmentDocumentReviewResult
    todo_plan: TodoExecutionPlan | None = None
    todo_results: list[TodoTaskResult] = Field(default_factory=list)
    review_summary: InvestmentDocumentReviewTodoSummary | None = None
    criteria: list[str]
    max_rounds: int = Field(default=1, ge=0, le=2)


class InvestmentDocumentReviewReflectionCritique(BaseModel):
    passed: bool
    score: float = Field(ge=0.0, le=1.0)
    issues: list[str]
    suggestions: list[str]
    safety_flags: list[str] = Field(default_factory=list)


class InvestmentDocumentReviewReflectionResult(BaseModel):
    review_result: InvestmentDocumentReviewResult
    passed: bool
    score: float
    issues: list[str]
    suggestions: list[str]
    safety_flags: list[str]
    rounds: int
```

后续可以将 `safety_flags` 提升为 `str, Enum`，例如：

```python
class InvestmentDocumentReviewReflectionSafetyFlag(str, Enum):
    INVESTMENT_ADVICE_RISK = "investment_advice_risk"
    UNSUPPORTED_FACT_RISK = "unsupported_fact_risk"
    INCOMPLETE_TASK_DISCLOSURE = "incomplete_task_disclosure"
```

### 2. 新增 prompt

文件：

```text
src/investory/agent_core/prompts/tasks/investment_document_review_reflection.md
```

职责：

- 评估当前 `InvestmentDocumentReviewResult`
- 必要时修订该结构化结果
- 不新增输入外事实
- 不改变 output schema
- 不给投资建议
- 把失败、跳过、缺失证据反映到 `information_gaps` 或 `boundary_notes`

第一版为了简单，可以让一个 LLM task 同时完成 critique 和可选 revise：

```text
Input: review_result + criteria + supporting context
Output: reflection_result with revised review_result
```

这样避免新增两个 task。

### 3. 注册 TaskSpec

文件：

```text
src/investory/agent_core/tasks.py
```

新增常量和 TaskSpec：

```python
INVESTMENT_DOCUMENT_REVIEW_REFLECTION_NAME = "investment_document_review_reflection"

INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_REVIEW_REFLECTION_NAME,
    prompt_name=INVESTMENT_DOCUMENT_REVIEW_REFLECTION_NAME,
    input_model=InvestmentDocumentReviewReflectionInput,
    output_model=InvestmentDocumentReviewReflectionResult,
)
```

并加入 `TASKS`。

### 4. 扩展 flow state

文件：

```text
src/investory/agent_core/contracts/investment_document_review_state.py
```

建议新增：

```python
reflection_result: dict[str, Any] | None = None
reflection_passed: bool | None = None
reflection_rounds: int | None = None
```

第一版先不暴露到最终 API 也可以，但应保留在 state 里方便日志和测试。

### 5. 扩展 LangGraph 节点

文件：

```text
src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py
```

新增 enum 节点：

```python
REFLECT_REVIEW_OUTPUT = "reflect_review_output"
```

新增 graph node：

```python
graph.add_node(
    InvestmentDocumentReviewNode.REFLECT_REVIEW_OUTPUT.value,
    self.reflect_review_output,
)
```

调整边：

```text
EXECUTE_REVIEW_TODO_PLAN -> REFLECT_REVIEW_OUTPUT -> ASSESS_REVIEW_RISK
RUN_SINGLE_PASS_REVIEW -> REFLECT_REVIEW_OUTPUT -> ASSESS_REVIEW_RISK
```

新增方法：

```python
def reflect_review_output(self, state: InvestmentDocumentReviewState) -> dict[str, Any]:
    if state.output is None or not state.output.ok:
        return {}

    payload = self._build_review_reflection_payload(state=state)
    result = self.executor.run(INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK, payload)
    if not result.ok:
        return {"output": result}

    reflection = InvestmentDocumentReviewReflectionResult.model_validate(result.result)
    return {
        "output": TaskResult(
            ok=True,
            task_name=state.output.task_name,
            result=reflection.review_result.model_dump(mode="json"),
        ),
        "reflection_result": reflection.model_dump(mode="json"),
        "reflection_passed": reflection.passed,
        "reflection_rounds": reflection.rounds,
    }
```

### 6. 构造 reflection payload

同文件新增 helper：

```python
def _build_review_reflection_payload(
    self,
    *,
    state: InvestmentDocumentReviewState,
) -> dict[str, Any]:
    ...
```

To-Do 路径应复用现有 `_build_review_todo_summary()`，给 reflection 提供 deterministic summary。

single-pass 路径可以只传 `review_result`、`document_type`、`route_confidence` 和 `review_goal`。

### 7. 增加日志

建议新增日志：

```text
investment_document_review.reflection.started
investment_document_review.reflection.completed
investment_document_review.reflection.failed
```

日志字段：

- `session_id`
- `passed`
- `score`
- `rounds`
- `issue_count`
- `safety_flag_count`

## 建议测试范围

### 1. Task registration 测试

目标：

- `resolve_task_spec()` 能找到 `investment_document_review_reflection`
- prompt 文件存在
- input/output model 可导入

### 2. Reflection model 测试

目标：

- `score` 限制在 0 到 1
- `max_rounds` 限制在 0 到 2
- 输出必须包含结构化 `review_result`

### 3. Flow wiring 测试

目标：

- single-pass 路径在 risk assessment 前调用 reflection
- To-Do 路径在 synthesize 后调用 reflection
- `output.ok == false` 时跳过 reflection

### 4. Reflection 成功测试

目标：

- mock reflection task 返回修订后的 review result
- 后续 risk assessment 使用修订后的结果
- final result 中 `review` 为修订后版本

### 5. Reflection 失败测试

目标：

- reflection task 失败时，flow 返回对应 TaskResult error
- 不继续 risk assessment

### 6. Pending approval 兼容测试

目标：

- reflection 后若 risk assessment 仍为 high，输出 `pending_human_approval`
- `review`、`risk_assessment`、`approval` 字段仍按现有 contract 返回

### 7. 非投资建议边界测试

目标：

- reflection 不会把报告改写成 buy / sell / hold / allocation / timing 建议
- 若原报告有越界表达，reflection 应将其改为学习型、风险提示型表达

## 分阶段实施计划

### Step 1：新增 reflection task 合同

目标：

- 增加 Pydantic input / output model
- 增加 prompt
- 注册 TaskSpec

验收：

- task registry 测试通过
- model validation 测试通过

建议工作日志：

```text
docs/2-2/worklog/14-investment_document_review_reflection_execution_worklog.md
```

### Step 2：接入 LangGraph flow

目标：

- 新增 `reflect_review_output` 节点
- 调整 single-pass 和 To-Do 路径
- 增加 payload builder

验收：

- flow wiring 测试通过
- existing investment document review 测试不回退

### Step 3：补充日志和 state 可观测字段

目标：

- state 记录 reflection metadata
- 日志记录 reflection outcome

验收：

- 日志事件测试或 mock handler 测试通过

### Step 4：补充端到端行为测试

目标：

- 验证修订后的 review 被 risk assessment 使用
- 验证 high risk 仍走 pending approval
- 验证 reflection 失败时不吞错

验收：

- `tests/test_investment_document_review_flow.py`
- `tests/test_investment_document_review_task_model.py`
- 相关 gateway API 测试按需更新

### Step 5：视情况外置 review framework

目标：

- 将 `DOCUMENT_REVIEW_FRAMEWORK_BY_TYPE` 迁移到 YAML
- 保留 typed enum document type 映射
- 增加配置加载测试

说明：

该步骤不是 reflection MVP 的必要条件，建议单独执行，避免一次改动过大。

## 风险与控制

| 风险 | 表现 | 控制方式 |
|---|---|---|
| 延迟增加 | 每次审查多一次 LLM 调用 | 第一版 `max_rounds=1`，只对 document review 开启 |
| 成本增加 | 长文档审查成本更高 | 使用 deterministic summary，避免把全文再次传入 reflection |
| 自评不可靠 | 模型给自己放水 | criteria 具体化，测试覆盖典型失败样例 |
| 改写引入新事实 | revised review 包含输入外事实 | prompt 明确禁止，criteria 检查 unsupported fact risk |
| 合规边界后置化 | 依赖 reflection 修复违规输出 | policy gate 保持前置，reflection 只做质量闸门 |
| API contract 变化 | final result 字段不兼容 | 保持 `InvestmentDocumentReviewResult` 作为 review 输出结构 |
| 状态膨胀 | final response 暴露过多 metadata | 第一版只在 state / logs 记录 reflection metadata |

## 推荐 MVP 范围

第一版只做：

- 新增 `investment_document_review_reflection` task
- 只接入投资文档审查 flow
- 只允许最多一轮修订
- 不外置 review framework
- 不改变 gateway response contract
- 不新增人工审批 resume 逻辑

第一版完成后的目标链路：

```text
document review result
  -> reflection quality gate
  -> revised structured review result
  -> risk assessment
  -> final / pending approval
```

## 暂不纳入本计划的事项

- 不实现人工审批恢复接口
- 不引入 Agently / TriggerFlow
- 不替换现有 To-Do runner
- 不让 reflection 修改 To-Do plan
- 不将 reflection 用于入口路由
- 不对所有 QA / summary / brief 任务默认启用 reflection

## 结论

v3 对 Investory 最有价值的参考点，是将最终报告从“一次生成结果”升级为“可验收、可修订、可观测的结构化产物”。

Investory 当前已经拥有比参考项目更适合生产的基础设施，因此推荐采用窄范围接入：

```text
先把 reflection 做成投资文档审查 final review 的质量闸门，
再根据效果决定是否扩展到 learning summary、instrument brief 或 finance QA。
```

这条路径改动集中、收益明确，也符合当前仓库的 typed constants、Pydantic contract、LangGraph flow 和测试优先的工程风格。
