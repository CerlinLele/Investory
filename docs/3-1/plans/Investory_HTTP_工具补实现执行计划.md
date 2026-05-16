# Investory：HTTP 工具能力补实现执行计划（Implementation Plan）

## 1. 目标与交付

目标：在现有 Investory 架构中补齐可运行的 `web_search` 能力，并与当前 `fetch_instrument_profile` 工具链路统一到可扩展的 Tool Contract / Registry / Handler / Guard 结构。

交付物：
1. 可运行的 `web_search` 工具实现（含 schema、执行入口、provider 选择与 fallback）。
2. 网关层可触发的最小调用路径（不破坏现有 `/tasks` 协议）。
3. 安全治理覆盖（allowlist/timeout/retry/logging）。
4. 对应测试与 smoke 验证脚本更新。
5. 文档与 worklog 更新。

---

## 2. 范围边界

### In Scope
- `src/investory/agent_core/contracts/`：工具契约扩展。
- `src/investory/agent_core/tools/`：`web_search` 实现与导出。
- `src/investory/agent_core/actions/`：执行器接入。
- `src/investory/agent_core/runtime/`：决策流接线（仅最小必要改动）。
- `src/investory/config.py`：`web_search` 相关配置项。
- `src/investory/gateway/`：请求到任务规格映射的必要适配。

### Out of Scope
- UI 页面与前端交互。
- prompt 大改与策略学习。
- 多租户权限系统重构。
- 外部 MCP 平台接入（本期仅保留 adapter 扩展位）。

---

## 3. 实施阶段

## 阶段 E：代码补实现（核心）

### Step E-1：扩展 Tool Contract（新增 web_search）

Implementation steps:
1. 在 `tool_contract.py` 扩展 `ToolName`，加入 `web_search`。
2. 为 `ToolCall.params` 增加最小字段约束文档（query、top_k、provider_hint 可选）。
3. 保持向后兼容：`fetch_instrument_profile` 不受影响。

验收标准：
- `ToolName` 同时支持 `fetch_instrument_profile` 与 `web_search`。
- 现有调用路径无类型错误。

---

### Step E-2：新增 web_search 工具实现

Implementation steps:
1. 新建 `src/investory/agent_core/tools/web_search.py`。
2. 实现 `search_web(query: str, top_k: int = 5, provider_hint: str | None = None) -> ToolResult`。
3. 采用“provider 列表顺序尝试”策略（如 `provider_hint` -> default provider list）。
4. 对 provider 响应做统一结构化：`title/url/snippet/source/provider`。

验收标准：
- 返回 `ToolResult(ok=True)` 时，`data.results` 为结构化数组。
- provider 失败可收敛到 `ToolResult(ok=False)` 且带 `error_type/retryable`。

---

### Step E-3：接入 Guard 与网络治理

Implementation steps:
1. 复用 `net_guard.py`（或最小扩展）实现 outbound URL 校验。
2. 在 `config.py` 增加 `web_search` 配置：timeout、allowed_hosts、max_results、provider_order。
3. 统一日志事件：`tool_http_attempt` + `tool_name=web_search`。
4. 对超时/网络错误/内容错误设置 retryable 策略。

验收标准：
- 非 allowlist 域名被拦截并可观测。
- timeout 与网络错误分类稳定输出。

---

### Step E-4：执行器与路由接线

Implementation steps:
1. 在 `actions/executors.py` 新增 `RunWebSearchExecutor`。
2. 在 `actions/router.py` 注册新 action（例如 `run_web_search`）。
3. 保证决策流 `DecisionFlow -> ActionRouter -> Executor` 完整可达。

验收标准：
- ActionRouter 能正确路由到 `RunWebSearchExecutor`。
- 执行结果可被 `TaskResult` 回传。

---

### Step E-5：任务规格与网关触发路径

Implementation steps:
1. 在任务规格中增加最小 task（例如 `web_search_brief` 或 `research_lookup`）。
2. 在 `gateway/routing.py` 增加 task_type 到 spec 映射。
3. 保持 `/tasks` API 协议不变，仅扩展可用 task_type。

验收标准：
- 通过 `/tasks` 可触发 web_search 路径。
- 非法 task_type 行为保持原有错误处理。

---

### Step E-6：测试与验证

Implementation steps:
1. 为 `web_search` 工具新增单元测试（成功、timeout、blocked_host、provider 全失败）。
2. 为执行器新增集成测试（router + executor）。
3. 更新 smoke 脚本，增加最小可运行检查。
4. 运行测试并记录结果到 worklog。

验收标准：
- 新增测试通过。
- 不回归现有 `fetch_instrument_profile` 路径。

---

## 阶段 F：文档与交付

### Step F-1：更新定位文档

Implementation steps:
1. 将“未发现 web_search”结论更新为“已实现 web_search + 锚点”。
2. 增补 provider 选择与 fallback 的真实代码锚点。
3. 更新“5 点最小主链路”为新实现版本。

验收标准：
- 每个结论有 `文件:行号`。
- 文档能独立用于第 3-1 课讲解。

### Step F-2：交付检查清单

Implementation steps:
1. 代码、测试、文档、worklog 四项完整性检查。
2. 汇总变更文件清单与风险清单。
3. 形成 PR 描述初稿。

验收标准：
- 可直接进入评审。

---

## 4. 建议提交节奏（每小步一提交）

1. `feat(contract): add web_search tool name and call schema notes`
2. `feat(tools): add web_search tool with provider fallback`
3. `feat(guard): enforce web_search timeout allowlist and logging`
4. `feat(actions): wire run_web_search executor and router mapping`
5. `feat(gateway): expose web_search task route`
6. `test(tools): add web_search success and failure coverage`
7. `docs(3-1): update locating doc with web_search implementation anchors`

---

## 5. 风险与缓解

1. 风险：provider 不稳定导致测试抖动。
- 缓解：单测使用 mock provider，smoke 才走真实网络。

2. 风险：allowlist 过严导致“可用性假失败”。
- 缓解：提供环境变量覆盖并在日志里打印被拦截 host。

3. 风险：新增 action 与既有决策逻辑冲突。
- 缓解：通过 task_type 显式触发，避免改动现有默认任务路径。

---

## 6. 立即执行建议

1. 先执行 E-1 与 E-2（契约 + 工具实现）。
2. 再执行 E-3 与 E-4（治理 + 路由）。
3. 最后执行 E-5/E-6/F-1/F-2（接线验证与文档交付）。
