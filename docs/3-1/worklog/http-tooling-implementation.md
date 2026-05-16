# HTTP Tooling Implementation Worklog

## Step E-1 - 扩展 Tool Contract（新增 web_search）
- Timestamp: 2026-05-16 00:37:27 +10:00
- Command/Action:
  - Edited `src/investory/agent_core/contracts/tool_contract.py`.
  - Extended `ToolName` with `web_search`.
  - Added `ToolCall.params` description documenting `query`, `top_k`, `provider_hint` for `web_search`.
- Files touched:
  - `src/investory/agent_core/contracts/tool_contract.py`
- Result:
  - `ToolName` now supports both `fetch_instrument_profile` and `web_search`.
  - Existing `fetch_instrument_profile` contract remains unchanged and backward compatible.
- Evidence anchors:
  - `src/investory/agent_core/contracts/tool_contract.py:6`
  - `src/investory/agent_core/contracts/tool_contract.py:11`

## Step E-2 - 新增 web_search 工具实现
- Timestamp: 2026-05-16 01:16:17 +10:00
- Command/Action:
  - Added `src/investory/agent_core/tools/web_search.py` with `search_web(query, top_k=5, provider_hint=None) -> ToolResult`.
  - Implemented provider fallback order: `provider_hint` first (if supported), then default provider order.
  - Normalized success payload to `title/url/snippet/source/provider` result items.
  - Updated `src/investory/agent_core/tools/__init__.py` export list with `search_web`.
- Files touched:
  - `src/investory/agent_core/tools/web_search.py`
  - `src/investory/agent_core/tools/__init__.py`
- Result:
  - `web_search` now returns `ToolResult(ok=True)` with `data.results` structured list when at least one provider succeeds.
  - Provider failures converge to `ToolResult(ok=False)` with `error_type/retryable` policy.
- Evidence anchors:
  - `src/investory/agent_core/tools/web_search.py:125`
  - `src/investory/agent_core/tools/web_search.py:189`
  - `src/investory/agent_core/tools/__init__.py:1`

## Step E-3 - 接入 Guard 与网络治理
- Timestamp: 2026-05-16 01:32:39 +10:00
- Command/Action:
  - Added web_search config keys in `src/investory/config.py`: timeout, allowed_hosts, max_results, provider_order.
  - Wired `src/investory/agent_core/tools/web_search.py` to use web_search-specific config values.
  - Kept outbound validation via existing `guarded_get` allowlist checks and unified `tool_http_attempt` logging.
  - Added explicit parse-error attempt logging for observability consistency.
- Files touched:
  - `src/investory/config.py`
  - `src/investory/agent_core/tools/web_search.py`
- Result:
  - Non-allowlist targets are blocked by net guard using `web_search_allowed_hosts`.
  - Timeout/network/content-error paths produce stable `error_type/retryable` with observable log events.
- Evidence anchors:
  - `src/investory/config.py:75`
  - `src/investory/config.py:184`
  - `src/investory/agent_core/tools/web_search.py:25`
  - `src/investory/agent_core/tools/web_search.py:175`

## Step E-4 - 执行器与路由接线
- Timestamp: 2026-05-16 01:36:07 +10:00
- Command/Action:
  - Added new action name `run_web_search` to `ActionName` contract.
  - Added validator branch for `run_web_search` params: required `query`, optional positive `top_k`, optional non-empty `provider_hint`.
  - Added `RunWebSearchExecutor` and wired it to call `search_web`.
  - Registered `run_web_search` in default `ActionRouter` mapping.
- Files touched:
  - `src/investory/agent_core/contracts/action_contract.py`
  - `src/investory/agent_core/actions/validator.py`
  - `src/investory/agent_core/actions/executors.py`
  - `src/investory/agent_core/actions/router.py`
- Result:
  - `ActionRouter` can route `run_web_search` to `RunWebSearchExecutor`.
  - Executor output is returned as `ActionResult`, then backfilled to `TaskResult` by existing decision flow.
- Evidence anchors:
  - `src/investory/agent_core/contracts/action_contract.py:13`
  - `src/investory/agent_core/actions/validator.py:94`
  - `src/investory/agent_core/actions/executors.py:108`
  - `src/investory/agent_core/actions/router.py:45`
  - Compile check: `python -m compileall src/investory/agent_core/actions src/investory/agent_core/contracts` (passed).

## Step E-5 - 任务规格与网关触发路径
- Timestamp: 2026-05-16 14:27:00 +10:00
- Command/Action:
  - Added new task model file `web_search_brief.py` with input/output schemas for search payload/results.
  - Registered `WEB_SEARCH_BRIEF_TASK` in `src/investory/agent_core/tasks.py` and included it in TASKS registry.
  - Added gateway task aliases in `src/investory/gateway/routing.py`: `web_search` and `research_lookup` -> `web_search_brief`.
  - Added decision planner branch to route `web_search_brief` requests to `run_web_search` action directly.
- Files touched:
  - `src/investory/agent_core/task_models/web_search_brief.py`
  - `src/investory/agent_core/tasks.py`
  - `src/investory/gateway/routing.py`
  - `src/investory/agent_core/runtime/decision_planner.py`
- Result:
  - `/tasks` can now trigger the web-search tool path via `task_type=web_search` or `task_type=research_lookup` without protocol changes.
  - Unknown task types keep original error handling through `UnknownTaskTypeError`.
- Evidence anchors:
  - `src/investory/agent_core/tasks.py:39`
  - `src/investory/gateway/routing.py:19`
  - `src/investory/agent_core/runtime/decision_planner.py:11`
  - `src/investory/agent_core/task_models/web_search_brief.py:4`
  - Verification: `PYTHONPATH=src` resolve_task_name(web_search/research_lookup/web_search_brief) => `web_search_brief`.

## Step E-6 - 测试与验证
- Timestamp: 2026-05-16 15:47:10 +10:00
- Command/Action:
  - Added web_search tool unit tests in `tests/test_web_search_tool.py` for success, timeout, blocked_host, and provider-all-fail paths.
  - Added action/router/validator/planner/gateway/tasks test coverage updates for `run_web_search` and `web_search_brief` wiring.
  - Updated smoke task defaults with `web_search_brief` payload in `src/investory/agent_core/runtime/smoke/task.py`.
  - Ran targeted pytest set that can execute in current environment.
- Files touched:
  - `tests/test_web_search_tool.py`
  - `tests/test_action_executors.py`
  - `tests/test_action_router.py`
  - `tests/test_action_validator.py`
  - `tests/test_decision_planner.py`
  - `tests/test_gateway_routing.py`
  - `tests/test_tasks.py`
  - `src/investory/agent_core/runtime/smoke/task.py`
- Test result:
  - Passed: `python -m pytest tests/test_web_search_tool.py tests/test_gateway_routing.py tests/test_tasks.py` => `17 passed`.
  - Blocked: action-layer tests (`test_action_executors.py`, `test_action_router.py`, `test_action_validator.py`, `test_decision_planner.py`) failed at collection due to missing dependency `langchain_core` in current environment.
- Evidence anchors:
  - `tests/test_web_search_tool.py:1`
  - `tests/test_action_executors.py:1`
  - `tests/test_gateway_routing.py:1`
  - `tests/test_tasks.py:1`
  - `src/investory/agent_core/runtime/smoke/task.py:26`
  - Command output: `17 passed in 0.15s`.
  - Blocker output: `ModuleNotFoundError: No module named 'langchain_core'`.

## Step F-1 - 更新定位文档
- Timestamp: 2026-05-16 15:59:25 +10:00
- Command/Action:
  - Rewrote `docs/3-1/Investory HTTP 工具调用逻辑代码定位.md` from pre-implementation status to post-implementation status.
  - Replaced old conclusion "未发现 web_search" with implemented web_search chain and concrete anchors.
  - Added provider selection and fallback anchors from `tools/web_search.py`.
  - Updated the "5-point minimal main chain" to include gateway alias -> decision planner -> run_web_search executor -> guarded network path.
- Files touched:
  - `docs/3-1/Investory HTTP 工具调用逻辑代码定位.md`
- Result:
  - Document now reflects actual implementation state and is directly usable for 3-1 lesson explanation.
  - Each major conclusion is backed by `file:line` anchors.
- Evidence anchors:
  - `docs/3-1/Investory HTTP 工具调用逻辑代码定位.md:5`
  - `docs/3-1/Investory HTTP 工具调用逻辑代码定位.md:23`
  - `docs/3-1/Investory HTTP 工具调用逻辑代码定位.md:77`

## Step F-2 - 交付检查清单
- Timestamp: 2026-05-16 16:09:18 +10:00
- Command/Action:
  - Ran delivery completeness review across code/tests/docs/worklog based on implemented steps E-1~F-1.
  - Compiled change-file inventory and risk list for reviewer handoff.
  - Drafted PR description for merge review.
- Files touched:
  - `docs/3-1/delivery-checklist.md`
  - `docs/3-1/PR_DESCRIPTION.md`
  - `docs/3-1/worklog/http-tooling-implementation.md`
- Result:
  - Delivery checklist completed with completeness status, change list, and risk list.
  - PR description draft is ready for direct review usage.
- Evidence anchors:
  - `docs/3-1/delivery-checklist.md:1`
  - `docs/3-1/PR_DESCRIPTION.md:1`

## 术语澄清 - provider 在本项目中的含义
- Timestamp: 2026-05-16 16:20:00 +10:00
- Definition:
  - `provider` 不是通用“搜索引擎”抽象名词，而是 `web_search` 工具内部定义的“候选数据源适配器标识”。
  - 每个 `provider` 对应一组固定行为：如何构造目标 URL、命中哪些 host、以及返回结果中标记的 `provider` 字段值。
  - 当前实现里 provider 候选在 `src/investory/agent_core/tools/web_search.py::_provider_candidates(...)` 中声明（例如 `example_search`、`example_instruments`）。
- Runtime behavior:
  - `provider_hint`：调用方给出的“优先尝试哪个 provider”的提示；仅当该值是已支持 provider 时生效。
  - `web_search_provider_order`：配置中的默认 provider 尝试顺序。
  - 最终顺序规则：`provider_hint`（若有效）优先，其后按 `web_search_provider_order` 依次 fallback。
  - 返回结果里的 `provider_attempt_order` 记录了本次实际尝试顺序，`results[*].provider` 记录每条结果来自哪个 provider。
- Why it exists:
  - 把“搜索入口策略”从业务调用参数里分离出来，便于后续新增 provider 或调优顺序时只改配置/工具层，而不改上层 action/task 协议。
- Evidence anchors:
  - `src/investory/agent_core/tools/web_search.py:79`
  - `src/investory/agent_core/tools/web_search.py:86`
  - `src/investory/agent_core/tools/web_search.py:200`
