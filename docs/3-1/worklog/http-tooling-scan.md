# HTTP Tooling Scan Worklog

- Scan time: 2026-05-15 22:45:27 +10:00
- Branch: feature/3-1-tool-discovery-mcp-collab
- Scanner: Codex
- Scope plan: docs/3-1/Investory HTTP 工具调用实现定位计划.md

## Step A-2 First-round keyword scan (tools)

- Scan time: 2026-05-15 22:49:46 +10:00
- Keywords: web_search|web_fetch|tool|registry|router
- Scope: src/ and docs/
- Raw hit paths (path-level):
  - docs\0-1\Investory_第0章_模块图_目录结构_骨架职责.md
  - docs\0-2\Investory_第0-2课_源码结构思路.md
  - docs\0-2\Investory_第0章_FastAPI_搭建计划.md
  - docs\1-1\investory-langchain-最小任务执行器设计.md
  - docs\1-1\LLM调用失败时的错误收束.md
  - docs\1-2\investory-最小编排流程操作计划.md
  - docs\2-1\Investory_第2-1课_适用场景分析.md
  - docs\2-1\Investory_第2-1课_输入信息不足时追问用户_实施计划.md
  - docs\2-2\Investory_第2-2课_结构化决策链路实施计划.md
  - docs\3-1\Investory HTTP 工具调用实现定位计划.md
  - docs\3-1\Investory_instrument_profile_HTTP工具调用流程分析.html
  - docs\3-1\Investory_instrument_profile_HTTP工具实施计划.md
  - docs\3-1\Investory_第3-1课_tool-calling-trace-log_实施计划.md
  - docs\3-1\Investory_第3-1课_适用场景分析.md
  - docs\3-1\Investory_第3-1课_最小工具落地实现清单.md
  - docs\3-1\worklog\http-tooling-scan.md
  - docs\6-1\Investory_Context_Engineering_方案.md
  - docs\cloud\AWS\Bedrock\AgentCore\Runtime\Investory_Bedrock_AgentCore_Runtime_区别说明.md
  - src\investory\agent_core\actions\__init__.py
  - src\investory\agent_core\actions\executors.py
  - src\investory\agent_core\actions\router.py
  - src\investory\agent_core\contracts\__init__.py
  - src\investory\agent_core\contracts\tool_contract.py
  - src\investory\agent_core\runtime\decision_flow.py
  - src\investory\agent_core\runtime\smoke\README.md
  - src\investory\agent_core\tools\__init__.py
  - src\investory\agent_core\tools\instrument_profile.py
  - src\investory\agent_core\tools\net_guard.py
  - src\investory\config.py
  - src\investory\gateway\__init__.py
  - src\investory\gateway\api.py
  - src\investory\main.py

## Step A-3 Second-round keyword scan (network governance)

- Scan time: 2026-05-15 22:52:10 +10:00
- Keywords: http|ssrf|timeout|proxy|retry|allowlist
- Scope: src/ and docs/
- Candidate paths with evidence and tag (高相关/待确认):
  - [待确认] docs\0-1\Investory_第0章_模块图_目录结构_骨架职责.md :: http
  - [待确认] docs\0-2\Investory_第0章_FastAPI_搭建计划.md :: http
  - [待确认] docs\1-1\investory-langchain-最小任务执行器设计.md :: http,retry,timeout
  - [待确认] docs\1-1\LLM调用失败时的错误收束.md :: retry,timeout
  - [待确认] docs\1-1\System Prompt 与 User Prompt 设计.md :: retry,timeout
  - [待确认] docs\1-2\investory-最小编排流程操作计划.md :: http,timeout
  - [待确认] docs\2-2\Investory_第2-2课_结构化决策链路实施计划.md :: http
  - [待确认] docs\3-1\Investory HTTP 工具调用实现定位计划.md :: allowlist,http,proxy,retry,ssrf,timeout
  - [待确认] docs\3-1\Investory_instrument_profile_HTTP工具调用流程分析.html :: allowlist,http,retry,timeout
  - [待确认] docs\3-1\Investory_instrument_profile_HTTP工具实施计划.md :: allowlist,http,retry,ssrf,timeout
  - [待确认] docs\3-1\Investory_第3-1课_适用场景分析.md :: http
  - [待确认] docs\3-1\Investory_第3-1课_最小工具落地实现清单.md :: http,retry
  - [待确认] docs\3-1\worklog\http-tooling-scan.md :: http
  - [待确认] docs\cloud\AWS\Bedrock\AgentCore\Runtime\Investory_Bedrock_AgentCore_Runtime_区别说明.md :: http
  - [待确认] docs\cloud\Investory_课纲模块_AWS_Azure_对照表.md :: http
  - [高相关] src\investory\agent_core\contracts\result_types.py :: retry,timeout
  - [高相关] src\investory\agent_core\contracts\tool_contract.py :: retry
  - [高相关] src\investory\agent_core\runtime\decision_flow.py :: retry
  - [高相关] src\investory\agent_core\tools\instrument_profile.py :: http,retry,timeout
  - [高相关] src\investory\agent_core\tools\net_guard.py :: http,retry,timeout
  - [高相关] src\investory\config.py :: http,timeout
  - [高相关] src\investory\gateway\api.py :: http,retry
  - [高相关] src\investory\gateway\routing.py :: http
  - [高相关] src\investory\gateway\schemas.py :: http,retry
  - [高相关] src\investory\gateway\session.py :: http

## Step A-4 Merge and deduplicate candidate files v1

- Scan time: 2026-05-15 22:54:42 +10:00
- Input: A-2 raw hit paths + A-3 candidate paths
- Operation: merge + deduplicate + group by tool/export/runtime/security
- Rule: each file appears once with one primary group reason

- Group: tool
  - src\investory\agent_core\tools\__init__.py :: tool module export surface
  - src\investory\agent_core\tools\instrument_profile.py :: concrete web/http tool handler
  - src\investory\agent_core\contracts\tool_contract.py :: tool contract and invocation schema boundary

- Group: export
  - src\investory\main.py :: app bootstrap and outward API exposure entry
  - src\investory\gateway\__init__.py :: gateway module export entry
  - src\investory\gateway\api.py :: external HTTP API boundary and tool-call ingress
  - src\investory\agent_core\actions\__init__.py :: action-layer export aggregation
  - src\investory\agent_core\contracts\__init__.py :: contract export aggregation

- Group: runtime
  - src\investory\agent_core\actions\router.py :: runtime action routing decision point
  - src\investory\agent_core\actions\executors.py :: runtime action execution dispatcher
  - src\investory\agent_core\runtime\decision_flow.py :: model-to-tool decision flow runtime
  - src\investory\gateway\routing.py :: gateway runtime routing path
  - src\investory\gateway\session.py :: request/session runtime state carrier
  - src\investory\agent_core\runtime\smoke\README.md :: runtime smoke path reference doc (trace support)

- Group: security
  - src\investory\agent_core\tools\net_guard.py :: network guard for outbound request constraints
  - src\investory\config.py :: timeout/proxy and network policy config source
  - src\investory\gateway\schemas.py :: request field constraints affecting safe execution
  - src\investory\agent_core\contracts\result_types.py :: timeout/retry related result/error shape

- Candidate files v1 count: 18 (deduplicated)

## Step A-5 Terminology mapping table v1

- Scan time: 2026-05-15 22:57:51 +10:00
- Input: candidate files v1 from Step A-4
- Mapping rule: Investory internal naming -> course term (Contract/Registry/Handler/Guard)

| Investory 内部命名 | 课程术语 | 绑定代码文件 | 映射理由 |
| --- | --- | --- | --- |
| `agent_core/contracts/tool_contract.py` | Contract | `src\investory\agent_core\contracts\tool_contract.py` | 定义工具调用契约与字段边界 |
| `gateway/schemas.py` | Contract | `src\investory\gateway\schemas.py` | 定义网关入参与结构校验边界 |
| `agent_core/tools/__init__.py` | Registry | `src\investory\agent_core\tools\__init__.py` | 工具导出集合，承担可发现入口 |
| `gateway/api.py` | Registry | `src\investory\gateway\api.py` | 将对外请求映射到网关能力入口 |
| `agent_core/tools/instrument_profile.py` | Handler | `src\investory\agent_core\tools\instrument_profile.py` | 实际执行业务工具逻辑并返回结果 |
| `agent_core/actions/executors.py` | Handler | `src\investory\agent_core\actions\executors.py` | 执行分发后的动作/工具调用 |
| `agent_core/tools/net_guard.py` | Guard | `src\investory\agent_core\tools\net_guard.py` | 对外网请求做安全/约束前置控制 |
| `config.py` | Guard | `src\investory\config.py` | 提供 timeout/proxy 等策略配置边界 |

- Coverage check: each mapping row binds at least one source file from candidate files v1.

## Step A-6 Phase A summary (fact-only)

- Summary time: 2026-05-15 23:00:36 +10:00
- 已建立检索工作日志并记录分支/时间/范围计划，见 docs/3-1/worklog/http-tooling-scan.md（开头元信息区）。
- 已完成第一轮工具类关键词检索并记录原始命中路径清单（path-level），见 docs/3-1/worklog/http-tooling-scan.md 的 Step A-2。
- 第一轮命中覆盖 src/ 与 docs/ 两个范围，见 docs/3-1/worklog/http-tooling-scan.md 的 Step A-2 字段 Scope 与 Raw hit paths。
- 已完成第二轮网络治理关键词检索并记录每个候选文件的命中词证据，见 docs/3-1/worklog/http-tooling-scan.md 的 Step A-3。
- 第二轮候选文件已按 高相关/待确认 打标并保留命中词，见 docs/3-1/worklog/http-tooling-scan.md 的 Step A-3 列表项。
- 已将 A-2/A-3 结果合并去重并形成 候选文件 v1，总数记录为 18，见 docs/3-1/worklog/http-tooling-scan.md 的 Step A-4。
- 候选文件 v1 已按 	ool/export/runtime/security 分组且每个文件只出现一次，见 docs/3-1/worklog/http-tooling-scan.md 的 Step A-4 分组块。
- 已建立术语映射表 v1（Investory 命名 -> Contract/Registry/Handler/Guard），且每条映射绑定代码文件，见 docs/3-1/worklog/http-tooling-scan.md 的 Step A-5。
- 阶段 A 的事实记录均集中在同一日志文件并按步骤分段，可按 Step A-2 至 Step A-5 顺序回溯。

## Step B-7 Locate web_search schema definition

- Scan time: 2026-05-15 23:05:47 +10:00
- Scope: src/investory (code only)
- Result: no explicit `web_search` schema or `web_search` tool name found in current codebase.
- Evidence (search): `rg -n -i "web_search|websearch|search" src/investory` only hits generic text and one URL template in instrument tool.
- Current tool contract definition anchor: `src/investory/agent_core/contracts/tool_contract.py:6-12` (`ToolName = Literal["fetch_instrument_profile"]`, `ToolCall`).
- Current tool schema consumption anchor: `src/investory/agent_core/actions/executors.py:74-80` (fetcher defaults to `fetch_instrument_profile`, then executes tool call).
- Related HTTP gateway schema (not web_search-specific): `src/investory/gateway/schemas.py:23-35` (`TaskRequest` generic payload schema).
- Conclusion for Step 7 output: web_search schema definition point = not present; nearest equivalent schema is `fetch_instrument_profile` tool contract.

## Step B-8 Locate web_search execution entry

- Scan time: 2026-05-15 23:08:12 +10:00
- Result: no explicit `web_search` execution entry found in current codebase.
- Equivalent tool-path first hop (registry -> handler): `src/investory/agent_core/actions/router.py:41-43` registers `fetch_then_run_instrument_brief` -> `FetchThenRunInstrumentBriefExecutor`.
- Equivalent handler execution entry: `src/investory/agent_core/actions/executors.py:74` sets `fetcher = fetch_instrument_profile`; `src/investory/agent_core/actions/executors.py:78` performs `tool_result = self.fetcher(...)`.
- Caller side first-hop trigger: `src/investory/agent_core/runtime/decision_flow.py:62-63` routes action and invokes executor execution.
- HTTP gateway caller anchor: `src/investory/gateway/api.py:51-53` constructs `DecisionFlow` and calls `flow.run(...)`.
- Step-8 output form: `web_search` execution entry = not present; current equivalent execution entry is `FetchThenRunInstrumentBriefExecutor.execute` calling `fetch_instrument_profile`.

## Step B-9 Locate web_search provider selection and fallback

- Scan time: 2026-05-15 23:09:53 +10:00
- Result: no explicit `web_search` provider-selection module found in current codebase.
- Equivalent provider selection (source provider list): `src/investory/agent_core/tools/instrument_profile.py:60-65` defines ordered candidate sources as provider list.
- Equivalent selection execution: `src/investory/agent_core/tools/instrument_profile.py:112-119` iterates sources and issues guarded request in order.
- Fallback trigger condition #1: request-level failure (`not result.ok`) -> continue to next source, `src/investory/agent_core/tools/instrument_profile.py:123-132`.
- Fallback trigger condition #2: content parse insufficiency (`len(extracted) < MIN_SOURCE_MATERIAL_CHARS`) -> continue to next source, `src/investory/agent_core/tools/instrument_profile.py:136-150`.
- Fallback exhausted behavior: all sources failed then returns normalized failure result, `src/investory/agent_core/tools/instrument_profile.py:170` + `68-87`.
- Guard/allowlist gate impacting provider eligibility: `src/investory/agent_core/tools/net_guard.py:49-66` + `76-83` (blocked host/non-https -> non-retryable failure).
- Retryability mapping evidence: `src/investory/agent_core/tools/instrument_profile.py:31-38` and `77-87` maps error_type to retryable in final ToolResult.

## Step B-10 Locate web_fetch/http schema and entry

- Scan time: 2026-05-15 23:15:37 +10:00
- Tool schema definition anchor: src/investory/agent_core/contracts/tool_contract.py:9-12 (ToolCall with 	ool_name/params/request_id).
- Tool-name constraint anchor: src/investory/agent_core/contracts/tool_contract.py:6 (ToolName = Literal["fetch_instrument_profile"]).
- HTTP gateway request schema anchor: src/investory/gateway/schemas.py:23-35 (TaskRequest generic payload).
- web_fetch/http entry (executor layer): src/investory/agent_core/actions/executors.py:67-78 (FetchThenRunInstrumentBriefExecutor.execute calls fetcher).
- web_fetch/http concrete tool entry: src/investory/agent_core/tools/instrument_profile.py:100 (etch_instrument_profile).
- Step-10 output: schema and entry located for current equivalent HTTP tool path (no standalone web_fetch symbol).

## Step B-11 Locate real HTTP request trigger point

- Scan time: 2026-05-15 23:16:06 +10:00
- Tool-side request dispatch anchor: src/investory/agent_core/tools/instrument_profile.py:114-119 (guarded_get(...) call).
- HTTP trigger function anchor: src/investory/agent_core/tools/net_guard.py:69-75 (guarded_get signature and inputs).
- Real network call anchor: src/investory/agent_core/tools/net_guard.py:87 (urlopen(request, timeout=timeout)).
- Request construction anchor: src/investory/agent_core/tools/net_guard.py:85 (Request(url, headers={"User-Agent": user_agent})).
- Step-11 output: confirmed actual outbound HTTP occurs in 
et_guard.guarded_get via urllib.request.urlopen.

## Step B-12 Locate result normalization logic

- Scan time: 2026-05-15 23:16:41 +10:00
- Success-path normalization anchor #1: src/investory/agent_core/tools/instrument_profile.py:134-136 (extract + build source material).
- Success-path normalization anchor #2: src/investory/agent_core/tools/instrument_profile.py:159-168 (normalized ToolResult success payload shape).
- Error-path normalization anchor #1: src/investory/agent_core/tools/instrument_profile.py:90-97 (_build_error_result).
- Error-path normalization anchor #2: src/investory/agent_core/tools/instrument_profile.py:68-87 (_build_failure_result consolidates last error).
- Error classification support anchor: src/investory/agent_core/tools/instrument_profile.py:31-38 (ERROR_RETRYABLE_POLICY).
- Step-12 output: at least one success path and one error path normalization point identified.

## Step B-13 Locate gateway/mcp parameter validation and adaptation

- Scan time: 2026-05-15 23:17:30 +10:00
- Result: no explicit MCP gateway adapter found (mcp symbol absent in src/investory).
- Equivalent gateway validation anchor: src/investory/gateway/schemas.py:23-35 (TaskRequest with extra="forbid").
- Equivalent gateway routing/adaptation anchor #1: src/investory/gateway/api.py:49 (esolve_task_spec(task_request.task_type)).
- Equivalent gateway routing/adaptation anchor #2: src/investory/gateway/api.py:51-53 (DecisionFlow execution and gateway response adaptation).
- Equivalent gateway session/permission-context anchor: src/investory/gateway/api.py:48 (esolve_session_id).
- Step-13 output: validation/adaptation/execution nodes covered through gateway schemas + api + runtime path.

## Step B-14 Locate gateway/mcp error normalization

- Scan time: 2026-05-15 23:17:51 +10:00
- Gateway error-shape normalization anchor: src/investory/gateway/api.py:23-30 (_to_gateway_error maps TaskError -> TaskErrorResponse).
- Gateway error envelope anchor: src/investory/gateway/schemas.py:37-47 (TaskErrorResponse fields).
- Runtime error-class normalization anchor: src/investory/agent_core/contracts/result_types.py:91-100 (
ormalize_task_error entry).
- Mapping evidence #1: src/investory/agent_core/contracts/result_types.py:148-160 (401/403 -> provider_auth_error; 429 -> ate_limited; 5xx -> provider_unavailable).
- Mapping evidence #2: src/investory/agent_core/contracts/result_types.py:165-179 (	imeout and fallback unknown_error).
- Step-14 output: at least two distinct error mappings identified and anchored.

## Step B-15 Three-chain sketch v1

- Scan time: 2026-05-15 23:18:08 +10:00
- Search chain (equivalent): src/investory/gateway/api.py:51-53 -> src/investory/agent_core/actions/router.py:41-43 -> src/investory/agent_core/tools/instrument_profile.py:112-119.
- Fetch chain: src/investory/agent_core/actions/executors.py:74-78 -> src/investory/agent_core/tools/instrument_profile.py:100-119 -> src/investory/agent_core/tools/net_guard.py:85-87.
- Gateway chain (mcp-equivalent): src/investory/gateway/api.py:67-73 -> src/investory/gateway/api.py:49-53 -> src/investory/gateway/api.py:33-40.
- Note: explicit web_search and gateway/mcp symbols are not present; chain labels use current equivalent implementation path.

## Step C-16 Locate SSRF pre-checks

- Scan time: 2026-05-15 23:18:32 +10:00
- Control point #1: src/investory/agent_core/tools/net_guard.py:51-56 blocks non-HTTPS URLs (locked_host).
- Control point #2: src/investory/agent_core/tools/net_guard.py:58-64 host allowlist gate (host not in allowed_hosts => blocked).
- Control point #3: src/investory/agent_core/tools/net_guard.py:76-83 validation failure short-circuits before network call.
- Trigger/behavior summary: scheme/host violations return non-retryable guard errors and do not call urlopen.

## Step C-17 Locate redirect and DNS strategy

- Scan time: 2026-05-15 23:18:56 +10:00
- HTTP client implementation anchor: src/investory/agent_core/tools/net_guard.py:85-87 uses urllib.request.urlopen directly.
- Redirect policy finding: no explicit redirect toggle or max-redirect setting found in tool HTTP layer.
- DNS policy finding: no explicit custom DNS resolver strategy found in tool HTTP layer.
- Step-17 output: redirect/DNS behavior is implicit in stdlib defaults; no project-level explicit policy code located.

