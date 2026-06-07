# LangGraph 运行 To-Do DAG 可行性说明

## 结论

LangGraph 可以运行这种“主流程固定 + 中间按计划动态执行子任务”的图。

但对 Investory 当前实现来说，第一版不建议把每个 `extract` / `analyze` To-Do 动态编译成 LangGraph 子图。更稳妥的架构是：

```text
LangGraph 负责主流程：
policy gate
-> classify document type
-> build review framework
-> generate todo plan
-> execute todo plan
-> synthesize / build final result

TodoExecutionRunner 负责 plan 内部动态依赖执行：
validate plan
-> dependency layers
-> bounded concurrency
-> retry / fail_fast / best_effort / skipped
-> ordered results
```

也就是说，LangGraph 作为外层 workflow，`TodoExecutionRunner` 作为内层 DAG 调度器。

## 为什么可以运行

LangGraph 本身适合表达这些能力：

- 固定节点之间的顺序执行。
- 条件路由，例如 policy gate 后走 missing、refusal 或 complete。
- 动态 fan-out，例如根据当前 state 把多个 payload 分发给同一个节点。
- checkpoint / resume，用于中断后恢复图状态。

所以如果目标只是“根据 plan 动态跑多个子任务”，LangGraph 能做。

## 为什么第一版不建议全放进 LangGraph

当前 Investory 的 To-Do 场景不只是 fan-out，而是完整的任务调度问题：

- `depends_on` 依赖关系。
- DAG 合法性校验。
- 拓扑分层执行。
- 同层并发控制。
- retry 策略。
- 上游失败后下游 skipped。
- executor 结果合法性检查。
- 最终结果按原始 plan 顺序返回。

这些能力当前已经由项目里的 `TodoExecutionRunner`、`ensure_valid_todo_plan()` 和 dependency layer 工具覆盖。把它们重新搬进 LangGraph，会增加实现和测试复杂度。

## 当前已经具备的执行语义

当前实现里，这几个概念已经存在，但它们不是同一层概念：

- `retry_then_fail`
- `fail_fast`
- `best_effort`
- `skipped`

其中前 3 个是 `TodoExecutionPlan.failure_policy` 的可选值，定义在 `TodoFailurePolicy` 中：

```text
fail_fast
best_effort
retry_then_fail
```

`skipped` 则不是 failure policy，而是 `TodoTaskStatus` 的一种执行结果状态。

更具体地说：

- `retry_then_fail`：任务失败后重试，默认最多额外重试 2 次；如果仍失败，则返回 `failed`。
- `fail_fast`：某一层出现 `failed` 后，不再继续后续可执行任务；后续未执行任务会被标记为 `skipped`。
- `best_effort`：即使某个任务失败，只要其他任务依赖满足，仍继续执行其余任务。
- `skipped`：任务没有真正执行成功，且被系统主动跳过。

当前 `skipped` 主要有两种来源：

- 依赖任务未成功，下游任务自动 `skipped`。
- `fail_fast` 已经触发，后续任务自动 `skipped`。

所以更准确的术语应该是：

```text
当前 runner 已支持：
- retry_then_fail / fail_fast / best_effort 三种失败策略
- skipped 结果语义
```

这也是为什么当前问题更像“任务调度器能力是否完整”，而不只是“LangGraph 能不能 fan-out”。

## LangGraph 原生能力与当前 runner 语义对照

LangGraph 原生提供的是图执行、状态流转、动态分发、节点重试、中断恢复和 checkpoint 这类底层能力。Investory 当前 `TodoExecutionRunner` 提供的是面向 To-Do plan 的业务级调度语义。

两者不是完全同一层东西：

| 能力 | LangGraph 原生情况 | 当前 TodoExecutionRunner 情况 | 结论 |
|---|---|---|---|
| 节点顺序执行 | 支持 | 支持按依赖层执行 | 两者都能表达 |
| 条件路由 | 支持 `add_conditional_edges` | 不负责主流程路由 | 主流程适合放 LangGraph |
| 动态 fan-out | 支持 `Send` | 支持同层任务并发执行 | 两者都能做，但抽象层不同 |
| checkpoint / resume | 支持图状态 checkpoint | 当前 runner 还未完整持久化 resume | 若要子任务级恢复，可后续增强 |
| retry | 支持节点级 `RetryPolicy` | 支持 `retry_then_fail` failure policy | 两者都有，但语义和配置入口不同 |
| skip / skipped | 没有统一的业务级 `skip policy` | 有 `TodoTaskStatus.SKIPPED` 结果状态 | 当前 skipped 是 runner 业务语义 |
| fail_fast | 没有直接同名内建 policy | 有 `TodoFailurePolicy.FAIL_FAST` | 当前 fail_fast 是 runner 业务语义 |
| best_effort | 没有直接同名内建 policy | 有 `TodoFailurePolicy.BEST_EFFORT` | 当前 best_effort 是 runner 业务语义 |
| DAG 合法性校验 | 不内建 To-Do plan 校验 | 有 `ensure_valid_todo_plan()` | 继续复用 runner 更合适 |
| 依赖失败后下游 skipped | 需要自行设计 | 已内建 | 继续复用 runner 更省心 |
| 按原始 plan 顺序返回结果 | 需要自行聚合 | 已内建 | 当前 runner 更贴合业务返回 |

因此，准确判断是：

```text
LangGraph 原生支持：
- 图节点执行
- 条件路由
- 动态 Send fan-out
- checkpoint / resume
- 节点级 retry

Investory runner 当前支持：
- To-Do plan 校验
- depends_on DAG 分层
- bounded concurrency
- retry_then_fail / fail_fast / best_effort
- dependency failed -> skipped
- ordered task results
```

如果把 To-Do 子任务全部迁移到 LangGraph 层，需要重新实现或重新映射这些 runner 语义，尤其是 `fail_fast`、`best_effort`、依赖失败后的 `skipped`、以及最终按 plan 顺序聚合结果。

## 当前代码状态

当前 `document_review_flow.py` 已经有这些方法：

```text
generate_review_todo_plan()
execute_review_todo_plan()
_execute_review_todo_task()
```

`InvestmentDocumentReviewState` 也已经包含：

```text
todo_plan
todo_results
```

但 `_build_graph()` 目前仍然把主流程接到 single-pass 节点：

```text
build_review_framework
-> run_single_pass_review
-> build_final_result
```

所以目前代码还没有真正切到 v1 To-Do DAG 流程。

## 推荐切换方式

第一版建议把 graph wiring 改成：

```text
evaluate_policy_gate
-> classify_document_type
-> build_review_framework
-> generate_review_todo_plan
-> execute_review_todo_plan
-> build_final_result
```

如果 synthesis 是独立节点，则更清晰的是：

```text
evaluate_policy_gate
-> classify_document_type
-> build_review_framework
-> generate_review_todo_plan
-> execute_review_todo_plan
-> synthesize_review_result
-> build_final_result
```

如果 plan 里包含 `investment_document_synthesize` 任务，也可以先让 `execute_review_todo_plan()` 产出最终 synthesis 结果，再交给 `build_final_result()` 包装 gateway 响应。

## LangGraph Send 适合什么时候用

后续可以考虑把子任务迁移到 LangGraph `Send` / checkpoint 的情况包括：

- 希望 LangGraph trace 里看到每个 extract / analyze 子任务。
- 需要子任务级别的 checkpoint 和 resume。
- 需要 streaming 展示每个子任务进度。
- 子任务依赖关系比较简单，主要是大量同构并发任务。
- 愿意把 `retry_then_fail`、`skipped`、`fail_fast`、`best_effort` 等现有执行语义重新设计到 LangGraph 层。

当前阶段的核心需求是可靠执行 To-Do 依赖计划，而不是让 LangGraph 可视化每个子任务节点。因此第一版继续使用 `TodoExecutionRunner` 更合适。

## 一句话判断

LangGraph 能运行这种图；但在 Investory 当前架构里，最合理的第一版是：

```text
LangGraph 管主流程，TodoExecutionRunner 管 To-Do DAG。
```
