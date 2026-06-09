# 投资文档审查 To-Do 计划与执行日志实施计划

## 目标

让 `/investment-document-review` 和 `/investment-document-review-file` 在服务端日志中清楚展示投资文档审查的 To-Do 计划生成与执行情况，便于 Apifox 手工测试、调试 LLM 行为、定位 chunk 任务失败原因，并为后续审计能力留出结构化基础。

本计划只关注服务端日志可观察性，不改变接口响应结构，不改变 To-Do DAG 执行语义，不把完整文档正文或完整 LLM 输出默认写入 INFO 日志。

## 当前缺口

1. `config.logs_dir` 已存在，但项目还没有统一 Python logging 配置、文件 handler、日志级别配置或结构化日志格式。
2. `generate_review_todo_plan()` 已生成 `TodoExecutionPlan`，但没有记录计划摘要、任务数量、任务 id、任务类型、依赖关系、chunk 数量。
3. `execute_review_todo_plan()` 已拿到 `todo_results`，但没有记录执行开始、执行结束、每个任务状态、失败原因、是否来自 resume。
4. `TodoExecutionRunner` 内部知道 dependency layer、skip、retry、failure policy，但没有事件 hook 或 logger，因此无法看到任务生命周期。
5. `todo_resume_store` 是可选注入，当前主 app 默认未注入持久化实现；即使未来接入，也不等同于人类可读日志。

## 设计原则

1. INFO 日志记录结构、状态、数量、耗时、错误类型，不记录完整 `document_text`、PDF 全文、完整 prompt 或完整 LLM 输出。
2. DEBUG 日志可以记录经过截断和脱敏的 payload/result 摘要，用于本地调试。
3. 每条 To-Do 日志都带 `session_id`，并尽量带 `task_id`、`task_kind`、`document_type`、`request_route`。
4. 日志事件名稳定，方便后续用 grep、Apifox 测试记录或集中日志系统检索。
5. 优先复用 Python 标准 `logging`，暂不引入新依赖。

## 建议日志事件

| 事件名 | 级别 | 触发位置 | 关键字段 |
|---|---|---|---|
| `investment_document_review.todo_plan.generated` | INFO | `generate_review_todo_plan()` 成功生成计划后 | `session_id`, `document_type`, `chunk_count`, `task_count`, `failure_policy`, `summary` |
| `investment_document_review.todo_plan.task` | DEBUG | 计划生成后遍历任务 | `session_id`, `task_id`, `task_kind`, `title`, `depends_on`, `completion_criteria_count` |
| `investment_document_review.todo_execution.started` | INFO | `execute_review_todo_plan()` 调 runner 前 | `session_id`, `task_count`, `resume_task_count`, `failure_policy` |
| `investment_document_review.todo_task.started` | INFO | runner 执行单个 task 前 | `session_id`, `task_id`, `task_kind`, `depends_on`, `attempt` |
| `investment_document_review.todo_task.succeeded` | INFO | task 成功后 | `session_id`, `task_id`, `task_kind`, `duration_ms`, `result_keys` |
| `investment_document_review.todo_task.failed` | WARNING | task 失败后 | `session_id`, `task_id`, `task_kind`, `duration_ms`, `error_type`, `stage` |
| `investment_document_review.todo_task.skipped` | INFO | dependency/fail-fast/retry exhausted skip | `session_id`, `task_id`, `reason`, `dependency_task_id` |
| `investment_document_review.todo_execution.completed` | INFO | runner 返回结果后 | `session_id`, `succeeded_count`, `failed_count`, `skipped_count`, `duration_ms`, `synthesis_produced` |
| `investment_document_review.todo_resume.loaded` | INFO | resume state 加载成功后 | `session_id`, `resumed_result_count`, `attempt_count` |
| `investment_document_review.todo_resume.saved` | INFO | resume state 保存成功后 | `session_id`, `saved_result_count` |

## 实施步骤

### Phase 1: 接入基础日志配置

目标：应用启动后同时输出 console 日志和文件日志。

建议修改：

- 新增 `src/investory/logging_config.py` 或等价模块。
- 在 `AppConfig` 增加 `log_level`，从 `INVESTORY_LOG_LEVEL` 读取，默认 `INFO`。
- 在 `create_app()` 中调用日志配置，使用 `config.logs_dir` 输出到 `logs/investory.log`。

验收标准：

- 启动服务后 `logs/investory.log` 存在。
- console 和文件都能看到应用启动日志。
- 未配置环境变量时默认 INFO。

### Phase 2: Flow 级记录 To-Do plan

目标：计划生成后能看到“生成了什么计划”。

建议修改：

- 在 `document_review_flow.py` 创建 module logger。
- 在 `generate_review_todo_plan()` 返回前记录 plan summary、task count、chunk count、failure policy。
- DEBUG 下逐个记录 task 的 id、kind、title、depends_on、criteria 数量。
- 对 chunk 路径和 LLM plan 路径都使用同一个 helper，例如 `_log_todo_plan_generated()`。

验收标准：

- Case 3 短文本请求能看到 `task_count=3` 左右的计划日志。
- Case 5 长文本请求能看到多个 `extract_chunk_000x` 任务。
- INFO 日志不包含完整文档正文。

### Phase 3: Runner 级记录任务生命周期

目标：执行过程中能看到每个 task 的开始、成功、失败、跳过和重试。

建议修改：

- 给 `TodoExecutionRunner` 增加可选 `event_handler` 或 `logger_context`，避免把投资文档 flow 的字段硬编码进通用 runner。
- 事件至少覆盖 layer start、task start、task result、retry decision、skip。
- `InvestmentDocumentReviewFlow._build_todo_execution_runner()` 注入事件处理器，补充 `session_id`、`document_type` 等上下文字段。

验收标准：

- 单 chunk 请求能看到 extract、analyze、synthesize 三类任务的生命周期日志。
- 多 chunk 请求能看到多个 extract task 并发/分层执行的顺序。
- 失败任务能看到 `error_type` 和 `stage`，但不泄露完整 prompt 或文档正文。

### Phase 4: 执行汇总与 resume 日志

目标：每次请求结束后能快速判断 To-Do 执行是否完整，以及是否复用了 resume state。

建议修改：

- 在 `_load_todo_resume_state()` 成功返回时记录 resume 结果数量与 attempts 数量。
- 在 `_save_todo_resume_state()` 保存后记录保存结果数量。
- 在 `execute_review_todo_plan()` runner 返回后记录成功、失败、跳过数量和是否产生 synthesize 结果。

验收标准：

- 日志能明确回答：本次请求是否从 resume 继续、执行了多少任务、失败了哪些任务、最终是否产生 synthesis。
- 无 resume store 时日志不报错，也不制造噪音。

### Phase 5: 测试与文档更新

目标：保证日志能力稳定，并让 Apifox 测试人员知道看哪里。

建议新增或更新：

- 单元测试：验证 plan 日志 helper 不输出完整 document text。
- 单元测试：验证 runner event handler 在 success、failed、skipped、retry 场景被调用。
- 更新 `docs/2-2/investment_document_review_apifox_test_plan.md`，增加“服务端日志观察点”章节。

建议测试命令：

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_todo_execution_runner.py tests\test_investment_document_review_flow.py
```

## 推荐日志样例

INFO 示例：

```text
investment_document_review.todo_plan.generated session_id=apifox-short-doc-chunk-review document_type=etf_factsheet chunk_count=1 task_count=3 failure_policy=retry_then_fail
investment_document_review.todo_execution.started session_id=apifox-short-doc-chunk-review task_count=3 resume_task_count=0
investment_document_review.todo_task.started session_id=apifox-short-doc-chunk-review task_id=extract_chunk_0001 task_kind=investment_document_extract attempt=1
investment_document_review.todo_task.succeeded session_id=apifox-short-doc-chunk-review task_id=extract_chunk_0001 duration_ms=1280 result_keys=extracted_facts,risk_findings,information_gaps
investment_document_review.todo_execution.completed session_id=apifox-short-doc-chunk-review succeeded_count=3 failed_count=0 skipped_count=0 synthesis_produced=true duration_ms=3840
```

WARNING 示例：

```text
investment_document_review.todo_task.failed session_id=apifox-multi-chunk-review task_id=extract_chunk_0002 task_kind=investment_document_extract duration_ms=2100 error_type=todo_task_execution_failed stage=llm_execution
```

## 风险与边界

1. 不应在 INFO 日志中记录原始 PDF 文本、完整 prompt、完整 LLM result、API key 或用户上传文件内容。
2. 如果把日志加在 runner 内部，注意 runner 是通用组件，不应依赖投资文档审查专用字段。
3. 并发执行会导致日志顺序不严格等同于 plan 顺序，应用 `task_id` 和 `session_id` 关联。
4. 若后续启用文件日志轮转，需要控制日志文件大小，避免长文档调试时写爆磁盘。
5. 若未来日志进入集中系统，事件字段应尽量保持稳定，避免频繁改名影响检索。

## 建议优先级

1. 先做 Phase 1 + Phase 2：最快让 Apifox 调试时看到生成的 To-Do plan。
2. 再做 Phase 3：补齐每个 task 的执行生命周期。
3. 最后做 Phase 4 + Phase 5：增强 resume 可见性和测试保障。

