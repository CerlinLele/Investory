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

