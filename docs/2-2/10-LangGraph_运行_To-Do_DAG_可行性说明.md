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
-> retry / skip / fail
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
- 愿意把 retry、skip、fail_fast、best_effort 等策略重新设计到 LangGraph 层。

当前阶段的核心需求是可靠执行 To-Do 依赖计划，而不是让 LangGraph 可视化每个子任务节点。因此第一版继续使用 `TodoExecutionRunner` 更合适。

## 一句话判断

LangGraph 能运行这种图；但在 Investory 当前架构里，最合理的第一版是：

```text
LangGraph 管主流程，TodoExecutionRunner 管 To-Do DAG。
```

