# Investory HTTP 工具调用逻辑代码定位

## 1. HTTP 工具注册入口

- `web_search` 已实现并进入 Tool Contract：
  - 工具名约束：`src/investory/agent_core/contracts/tool_contract.py:6`
  - 工具调用契约（`query/top_k/provider_hint` 说明）：`src/investory/agent_core/contracts/tool_contract.py:9-17`
- 执行器注册（Tool Registry 等价层）：
  - `run_web_search -> RunWebSearchExecutor`：`src/investory/agent_core/actions/router.py:38-46`

## 2. web_search/http 调用链路（本地工具 -> 网络请求 -> 结构化结果）

- 起点（动作执行器）：
  - `RunWebSearchExecutor.execute`：`src/investory/agent_core/actions/executors.py:108-153`
- 中间（工具实现）：
  - `search_web(...)` 主流程：`src/investory/agent_core/tools/web_search.py:125-204`
  - 统一结果结构：`title/url/snippet/source/provider`：`src/investory/agent_core/tools/web_search.py:94-103`
- 终点（真实 HTTP 请求）：
  - `guarded_get -> urllib.request.urlopen`：`src/investory/agent_core/tools/net_guard.py:69-131`
- 错误收敛：
  - `ToolResult(ok=False, error_type, retryable)`：`src/investory/agent_core/tools/web_search.py:106-122`

## 3. web_search 调用链路（provider 选择与回退）

- provider 候选构建：
  - `_provider_candidates(...)`：`src/investory/agent_core/tools/web_search.py:79-91`
- provider 顺序策略：
  - `provider_hint` 优先，然后 `web_search_provider_order`：`src/investory/agent_core/tools/web_search.py:86-90`
- 回退条件：
  - 请求失败回退：`src/investory/agent_core/tools/web_search.py:150-159`
  - 内容解析失败回退（`parse_error`）：`src/investory/agent_core/tools/web_search.py:174-188`
- 终态：
  - 至少一个 provider 成功：`src/investory/agent_core/tools/web_search.py:196-203`
  - 全部失败：`src/investory/agent_core/tools/web_search.py:193-194`

## 4. gateway 调用链路（任务触发适配）

- `/tasks` API 协议未变：
  - HTTP 入口：`src/investory/gateway/api.py:67-75`
  - 请求模型：`src/investory/gateway/schemas.py:23-35`
- task_type 到 spec 映射新增：
  - `web_search` / `research_lookup` -> `web_search_brief`：`src/investory/gateway/routing.py:15-21`
  - 解析函数：`src/investory/gateway/routing.py:36-51`
- 任务规格新增：
  - `WEB_SEARCH_BRIEF_TASK`：`src/investory/agent_core/tasks.py:38-50`
- 决策流接线：
  - `web_search_brief` 直接路由动作 `run_web_search`：`src/investory/agent_core/runtime/decision_planner.py:11-21`

## 5. 网络安全治理（allowlist/timeout/retry/logging）

- allowlist 与协议门禁（SSRF 边界）：
  - 仅 HTTPS + host allowlist：`src/investory/agent_core/tools/net_guard.py:49-64`
  - 不满足策略直接失败：`src/investory/agent_core/tools/net_guard.py:76-83`
- web_search 专用配置：
  - `web_search_timeout_seconds` / `web_search_allowed_hosts` / `web_search_max_results` / `web_search_provider_order`
  - 定义：`src/investory/config.py:75-78`
  - 环境变量加载：`src/investory/config.py:184-197`
- retry/error 策略：
  - `ERROR_RETRYABLE_POLICY`：`src/investory/agent_core/tools/web_search.py:30-37`
  - 未知错误类型归一化：`src/investory/agent_core/tools/web_search.py:112-121`
- 审计日志：
  - 统一事件 `tool_http_attempt`：`src/investory/agent_core/tools/net_guard.py:29-45`
  - `web_search` 成功/失败/parse_error 均打点：`src/investory/agent_core/tools/web_search.py:151-157`、`161-167`、`175-181`

## 6. 与第 3-1 课知识点映射（新实现）

- Tool Contract：
  - `ToolName` + `ToolCall.params`：`src/investory/agent_core/contracts/tool_contract.py:6-17`
- Tool Registry（等价）：
  - `ActionRouter` 默认映射：`src/investory/agent_core/actions/router.py:38-46`
- Handler：
  - `RunWebSearchExecutor.execute`：`src/investory/agent_core/actions/executors.py:108-153`
  - `search_web`：`src/investory/agent_core/tools/web_search.py:125-204`
- Runtime Guard：
  - `validate_url/guarded_get`：`src/investory/agent_core/tools/net_guard.py:49-131`

## 7. 建议课件最小主链路（新版本）

1. 网关任务入口：`src/investory/gateway/api.py:67-73`
2. task_type 映射到 `web_search_brief`：`src/investory/gateway/routing.py:15-21`
3. 决策流产出 `run_web_search`：`src/investory/agent_core/runtime/decision_planner.py:11-21`
4. ActionRouter 路由到 `RunWebSearchExecutor`：`src/investory/agent_core/actions/router.py:45`
5. `search_web` 走 Guard 发起网络请求并返回结构化结果：`src/investory/agent_core/tools/web_search.py:125-204` + `src/investory/agent_core/tools/net_guard.py:69-131`
