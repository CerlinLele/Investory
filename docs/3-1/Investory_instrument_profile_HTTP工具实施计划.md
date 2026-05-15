# Investory instrument_profile HTTP 工具实施计划（第 3-1 课）

## 1. 目标与当前状态

当前你已经完成了调用主链路接入：

- `DecisionPlanner` 已能在 `instrument_brief` 且仅缺 `source_material` 时走 `fetch_then_run_instrument_brief`
- `ActionValidator` / `ActionRouter` / `FetchThenRunInstrumentBriefExecutor` 已完成对新 action 的支持
- `fetch_instrument_profile` 仍是 mock 实现，尚未接入真实 HTTP 数据源

本计划的目标是：在不改动主干架构的前提下，把 `instrument_profile.py` 从 mock 升级为可治理、可降级、可测试的真实 HTTP 工具。

---

## 2. 实施步骤（每步含讲解）

### Step 1：先冻结工具边界与来源策略

要做什么：

1. 明确只接“公开、无需登录”的资料源。
2. 定义允许域名白名单（allowlist）与协议约束（仅 `https`）。
3. 约束输出为结构化摘要，不返回原始 HTML。

为什么先做：

- 先定边界，再写抓取代码，避免后续因为安全与合规要求返工。
- 这一步对应 OpenClaw 里“先治理后调用”的工程思路。

建议落地：

- 在 `instrument_profile.py` 中先定义：
  - `ALLOWED_HOSTS`
  - `DEFAULT_TIMEOUT_SECONDS`
  - `MAX_SOURCE_MATERIAL_CHARS`

当前落地（已完成）：

1. 已在 `instrument_profile.py` 固化边界常量：
   - `ALLOWED_HOSTS`：来源 host 白名单
   - `DEFAULT_TIMEOUT_SECONDS`：统一超时默认值
   - `MAX_SOURCE_MATERIAL_CHARS`：`source_material` 输出长度上限
2. 输出策略已明确为“结构化摘要字段”，当前工具返回 `ToolResult.data` 仅包含：
   - `instrument_name_or_code`
   - `source_material`
   - `sources`
   - `as_of`
3. 在进入真实抓取前，已通过常量与测试把“来源边界/长度边界”冻结，避免后续改动偏离治理要求。

---

### Step 2：新增 HTTP Guard 层（不要在工具里裸请求）

要做什么：

1. 新建轻量网络治理模块，例如：`src/investory/agent_core/tools/net_guard.py`。
2. 提供 `validate_url(url)`：校验 scheme、host、可选端口。
3. 提供 `guarded_get(url, timeout)`：统一超时、User-Agent、异常归一化。

为什么这样设计：

- 让 `instrument_profile` 专注业务逻辑，网络安全与异常收敛下沉到公共层。
- 后续新增 HTTP 工具可直接复用，不重复造轮子。

当前落地（已完成）：

1. 已新增 `src/investory/agent_core/tools/net_guard.py`，提供：
   - `validate_url(url, allowed_hosts)`：仅允许 `https` + allowlist host。
   - `guarded_get(url, timeout, allowed_hosts, user_agent)`：统一请求头、超时与错误归一化。
2. `guarded_get` 统一错误类型与重试语义：
   - `blocked_host`：不可重试
   - `timeout`：可重试
   - `network_error`：通常可重试（HTTP 5xx 可重试）
   - `not_found`：不可重试
   - `parse_error`：不可重试
3. `instrument_profile.py` 已改为复用 `validate_url` 过滤来源 URL，避免工具侧重复维护 URL 安全逻辑。
4. 已补充 `tests/test_net_guard.py`，覆盖：
   - `https`/allowlist 校验
   - blocked host 短路
   - timeout 归一化
   - network error 归一化

---

### Step 3：把 `fetch_instrument_profile` 改为真实多源尝试

要做什么：

1. 输入标准化：清洗 `instrument_name_or_code`。
2. 基于输入构建候选来源 URL 列表（按优先级）。
3. 顺序尝试抓取，命中即返回。
4. 全失败时返回 `ToolResult(ok=False)`，并带错误分类。

为什么要“多源 + 回退”：

- 单一来源故障率高，容易让用户频繁走降级分支。
- 多源可显著提升成功率，且与课堂“工具调用鲁棒性”主题一致。

当前落地（已完成）：

1. `fetch_instrument_profile` 已从固定 mock 改为“候选来源顺序尝试”：
   - 先标准化输入：`strip + upper`
   - 通过 `_build_candidate_sources(normalized)` 生成优先级来源列表
   - 逐个调用 `guarded_get(...)`，首个成功即返回
2. 成功分支逻辑：
   - 对返回文本做 `strip` 并截断到 `MAX_SOURCE_MATERIAL_CHARS`
   - 文本为空时按 `parse_error` 处理并继续尝试下一个来源
   - 返回 `sources` 为“实际尝试链路”，便于调试与可解释性
3. 全失败分支逻辑：
   - 通过 `_build_failure_result(...)` 统一失败返回
   - 优先透传最后一次失败的 `error_type/error_message/retryable`
   - 若无可用错误上下文，回退为 `not_found`
4. 测试策略已同步切换为“行为契约”：
   - 使用 monkeypatch 模拟 `guarded_get`，不依赖真实网络
   - 覆盖首源成功、回退成功、全失败透传、空输入、长度截断等关键场景

---

### Step 4：增加内容抽取与标准化输出

要做什么：

1. 新增 `_extract_profile_text(raw_text)`：去噪、截断、清理空白。
2. 新增 `_build_source_material(...)`：把零散字段拼成模型可消费摘要。
3. 保持 `ToolResult.data` 结构稳定：
   - `instrument_name_or_code`
   - `source_material`
   - `sources`
   - `as_of`

为什么重要：

- 下游 `instrument_brief` 需要干净、稳定、可控长度的文本输入。
- 结构稳定可减少上层改动和测试波动。

---

### Step 5：建立统一错误模型（error_type + retryable）

要做什么：

建议最小错误类型集合：

- `invalid_input`
- `blocked_host`
- `timeout`
- `network_error`
- `parse_error`
- `not_found`

并明确 `retryable`：

- `timeout/network_error` -> `True`
- `invalid_input/blocked_host` -> `False`

为什么这样做：

- Executor 依赖错误分类来决定“降级追问”还是“直接失败”。
- 后续日志分析、可观测性和测试断言都会更清晰。

---

### Step 6：增强 Executor 成功分支的元数据回填

要做什么：

在 `FetchThenRunInstrumentBriefExecutor` 成功分支，除 `source_material` 外，建议再回填：

- `source_links`
- `source_as_of`

为什么建议做：

- 便于后续在结果中展示“信息来源 + 时间”，提升可解释性。
- 这类字段是可选增强，不破坏现有任务输入契约。

---

### Step 7：升级测试，从“mock 内容断言”转“行为契约断言”

要做什么：

1. 更新 `tests/test_instrument_profile_tool.py`：
   - 成功路径
   - 空输入
   - 超时
   - blocked host
   - 解析失败
2. 在 `tests/test_action_executors.py` 增加工具失败降级断言。
3. 保持 `tests/test_decision_flow.py` 回归通过。

为什么这么测：

- 文本细节会随来源变化，测试应关注行为与契约而非字面内容。
- 能降低未来改动造成的脆弱测试失败。

---

### Step 8：配置化（为生产化预留）

要做什么：

把以下参数配置化（提供默认值）：

- `tool_http_timeout_seconds`
- `tool_allowed_hosts`
- `tool_user_agent`

为什么这一步必要：

- 不同环境网络条件不同，配置化能减少硬编码与重复发布。
- 后续替换数据源时仅调配置即可。

---

### Step 9：加入最小可观测与审计日志

要做什么：

记录结构化日志字段：

- `tool_name`
- 目标 host
- 耗时
- 成功/失败
- `error_type`

并避免记录敏感正文。

为什么这样做：

- HTTP 工具是故障与风险高发点，必须可排障。
- 结构化日志是后续 MCP 扩展前的基础设施。

---

### Step 10：验收（DoD）

完成标准：

1. 用户仅输入 `instrument_name_or_code`（如 `VTI`）时，可自动补全 `source_material` 并完成 `instrument_brief`。
2. 网络异常时流程不崩溃，稳定返回 `requires_user_input`。
3. 关键路径测试覆盖：planner / validator / router / executor / tool / flow。
4. 生产代码无 mock 残留（测试桩除外）。

---

## 3. 推荐执行顺序（最省返工）

1. Step 1 -> Step 2（先立边界与 guard）
2. Step 3 -> Step 5（真实抓取、回退与错误模型）
3. Step 7（测试先补齐）
4. Step 6 -> Step 9（增强项）
5. Step 10（验收）

---

## 4. 与 OpenClaw 参考的映射关系

- OpenClaw `web_fetch` 对应你这里的 `fetch_instrument_profile` 执行主链路。
- OpenClaw `fetch-guard/ssrf` 思想对应你这里的 `net_guard`（allowlist + timeout + 异常归一化）。
- OpenClaw provider fallback 对应你这里的“多来源候选 + 顺序回退”。

这份计划按“最小可用 + 可演进”设计，可直接作为第 3-1 课实现路线图。
