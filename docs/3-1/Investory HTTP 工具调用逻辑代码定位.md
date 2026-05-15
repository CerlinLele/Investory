# Investory HTTP 工具调用逻辑代码定位

## 1. HTTP 工具注册入口

- 当前仓库未发现显式 `web_search` / `web_fetch` 命名工具注册。
- 当前等价工具注册链路：
  - 工具名约束：`src/investory/agent_core/contracts/tool_contract.py:6`
  - 工具调用契约：`src/investory/agent_core/contracts/tool_contract.py:9-12`
  - Action 到执行器注册：`src/investory/agent_core/actions/router.py:34-43`
  - 具体执行器：`fetch_then_run_instrument_brief -> FetchThenRunInstrumentBriefExecutor`（`src/investory/agent_core/actions/router.py:41-43`）

## 2. web_fetch/http 调用链路（本地工具 -> 网络请求 -> 结构化结果）

- 起点：`src/investory/agent_core/actions/executors.py:76-78`
  - `FetchThenRunInstrumentBriefExecutor.execute` 调用 `self.fetcher(...)`。
- 中间：`src/investory/agent_core/tools/instrument_profile.py:100-119`
  - `fetch_instrument_profile` 构造候选源并调用 `guarded_get`。
- 终点：`src/investory/agent_core/tools/net_guard.py:85-87`
  - 通过 `urllib.request.urlopen` 发起真实 HTTP 请求。
- 结果标准化：
  - 成功：`src/investory/agent_core/tools/instrument_profile.py:159-168`
  - 错误：`src/investory/agent_core/tools/instrument_profile.py:68-87`、`90-97`

## 3. web_search 调用链路（provider 选择与回退）

- 代码中未发现显式 `web_search` 实现。
- 当前等价 provider 选择与 fallback 逻辑位于 `fetch_instrument_profile`：
  - provider 列表（候选源）：`src/investory/agent_core/tools/instrument_profile.py:60-65`
  - 顺序尝试：`src/investory/agent_core/tools/instrument_profile.py:112-119`
  - fallback 条件 1（请求失败）：`src/investory/agent_core/tools/instrument_profile.py:123-132`
  - fallback 条件 2（内容不足）：`src/investory/agent_core/tools/instrument_profile.py:136-150`
  - fallback 终态（全部失败）：`src/investory/agent_core/tools/instrument_profile.py:170`

## 4. gateway/mcp 调用链路（远程工具适配）

- 代码中未发现显式 `mcp` gateway 适配层。
- 当前等价网关调用链路：
  - HTTP 入口：`src/investory/gateway/api.py:67-73`
  - 请求验证模型：`src/investory/gateway/schemas.py:23-35`
  - 任务规格解析：`src/investory/gateway/api.py:49`
  - 决策流执行：`src/investory/gateway/api.py:51-53`
  - 响应适配：`src/investory/gateway/api.py:33-40`

## 5. 网络安全治理（SSRF、超时、代理、权限）

- SSRF / 域名门禁：
  - 仅允许 HTTPS：`src/investory/agent_core/tools/net_guard.py:51-56`
  - Host allowlist：`src/investory/agent_core/tools/net_guard.py:58-64`
  - 失败短路不联网：`src/investory/agent_core/tools/net_guard.py:76-83`
- 超时与重试：
  - 超时配置与注入：`src/investory/config.py:72`、`168-171`、`src/investory/agent_core/tools/instrument_profile.py:116`
  - 错误可重试标记：`src/investory/agent_core/tools/instrument_profile.py:31-38`、`77-87`
- 代理与凭据边界：
  - 工具 HTTP 未发现独立 proxy 字段（`src/investory/config.py`）
  - LLM 凭据来自环境变量：`src/investory/config.py:23,33,41,49,160`
- 审计与可观测：
  - HTTP 尝试日志字段：`src/investory/agent_core/tools/net_guard.py:29-45`
  - 网关错误字段：`src/investory/gateway/schemas.py:42-47`

## 6. 与第 3-1 课知识点映射

- Tool Contract：`tool_contract.py`（`src/investory/agent_core/contracts/tool_contract.py:6-12`）
- Tool Registry（等价）：`ActionRouter` 默认执行器映射（`src/investory/agent_core/actions/router.py:34-43`）
- Handler：`FetchThenRunInstrumentBriefExecutor.execute` + `fetch_instrument_profile`（`src/investory/agent_core/actions/executors.py:76-78`，`src/investory/agent_core/tools/instrument_profile.py:100`）
- Runtime Guard：`validate_url/guarded_get`（`src/investory/agent_core/tools/net_guard.py:49-87`）

## 7. 建议课件最小主链路

- 入口：`gateway/api.py:67-73`
- 决策到执行：`runtime/decision_flow.py:62-63`
- 执行器到工具：`actions/executors.py:74-78`
- 真实联网：`tools/net_guard.py:85-87`
- 安全门禁：`tools/net_guard.py:51-64`

## 8. 补充：为什么 Agent 会“自己判断网址”

- 现实现中，“网址候选”由代码显式提供，而非模型自由拼接：`src/investory/agent_core/tools/instrument_profile.py:60-65`。
- 模型侧主要决定是否触发 `fetch_then_run_instrument_brief` 这类动作；执行后的 URL 访问由工具函数与 guard 代码完成（`actions/router.py:41-43`、`tools/net_guard.py:49-87`）。
- 因此“看起来像 Agent 自己找网址”，实际是“模型触发动作 + 代码内候选源与策略执行”。
