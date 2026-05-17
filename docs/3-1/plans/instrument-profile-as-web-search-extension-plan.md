# fetch_instrument_profile 作为 web_search 扩展层改造计划

- 日期：2026-05-17
- 目标：将 `fetch_instrument_profile` 从“独立候选抓取工具”改造为“基于 `web_search` 的领域提炼扩展”，同时保持现有对外返回结构稳定。
- 范围：
  - `src/investory/agent_core/tools/instrument_profile.py`
  - `src/investory/agent_core/tools/web_search.py`（仅必要扩展）
  - `src/investory/agent_core/actions/executors.py`（如需注入路径调整）
  - 相关测试与 3-1 文档

## 1. 设计原则

1. 分层明确
- `web_search` 负责召回候选来源（检索层）。
- `fetch_instrument_profile` 负责二次筛选与资料提炼（扩展层）。

2. 语义稳定
- 保持 `fetch_instrument_profile` 当前输出字段：
  - `instrument_name_or_code`
  - `source_material`
  - `sources`
  - `as_of`
- 保持失败语义：`error_type` / `retryable` 与当前策略一致。

3. 最小侵入
- 优先复用现有 `http_runner.py` 与 `http_tooling_common.py`。
- 避免在 action/task/gateway 层引入不必要破坏性改动。

## 2. 目标调用链（改造后）

1. `fetch_instrument_profile(instrument_name_or_code)`
2. 内部先调用 `search_web(query=instrument_name_or_code, top_k=N, provider_hint=...)`
3. 由 `web_search` 返回候选 URL 列表
4. `instrument_profile` 对候选 URL 执行抓取/提取（沿用共享 runner）
5. 收敛为现有 `ToolResult` 结构

## 3. 实施步骤

## Step A - 基线锁定

1. 记录当前 `fetch_instrument_profile` 行为快照：
- 成功字段结构
- 错误映射
- fallback 顺序语义
2. 补齐/确认测试：
- web_search 调用前置失败时的错误收敛
- 有候选但解析失败时 parse_error 语义
- 无候选时 not_found 语义

交付物：
- 测试基线报告（worklog）

## Step B - 抽取 profile 专用候选组装接口

1. 在 `instrument_profile` 内新增候选来源装配函数：
- 输入：`web_search` 返回结果
- 输出：`Candidate` 列表（去重、顺序保留）
2. 明确候选过滤规则：
- URL 合法性
- source/domain 白名单策略

交付物：
- 新的候选装配函数 + 单测

## Step C - 将 web_search 作为前置召回层接入

1. `instrument_profile` 内注入 `searcher`（默认指向 `search_web`）
2. 调用 `search_web` 获取候选 URL
3. 将候选 URL 输入 `run_guarded_candidates` 执行提取
4. 若 `search_web` 失败，按策略映射到 `fetch_instrument_profile` 错误语义

交付物：
- `instrument_profile` 主流程迁移完成
- 兼容现有调用点

## Step D - 行为兼容与回归

1. 重点回归：
- `tests/test_instrument_profile_tool.py`
- `tests/test_web_search_tool.py`
- `tests/test_http_runner.py`
- action 层相关 `fetch_then_run_instrument_brief` 路径
2. 验证点：
- 输出 schema 不变
- retryable 语义不变
- 失败文案符合预期

交付物：
- 回归结果记录

## Step E - 文档与风险更新

1. 更新 `docs/3-1/plans/http-tooling-reuse-plan.md` 的扩展策略说明
2. 更新 `docs/3-1/worklog/http-tooling-reuse-worklog.md`
3. 增加“web_search 作为底座工具”的调用链说明

交付物：
- 完整文档锚点 + worklog

## 4. 风险与规避

1. 风险：工具间耦合提升（`instrument_profile -> web_search`）
- 规避：通过可注入 `searcher` 降低硬耦合，测试中可替换。

2. 风险：错误语义漂移
- 规避：先锁测试，再迁移；统一走 `http_tooling_common` 错误收敛。

3. 风险：候选质量波动导致 profile 提取成功率下降
- 规避：保留 domain/内容阈值校验；必要时引入 top_k 与 provider_hint 调优参数。

## 5. 验收标准

1. `fetch_instrument_profile` 内部以前置 `web_search` 作为候选来源。
2. 对外返回结构完全兼容当前 schema。
3. 核心工具测试通过，action 关键链路可回归。
4. 3-1 文档中可追踪该分层改造方案与实际落地结果。

## 6. 建议提交拆分

1. `test(tools): lock instrument_profile semantics before search-layer integration`
2. `refactor(instrument_profile): build profile candidates from web_search results`
3. `refactor(instrument_profile): integrate web_search as retrieval layer`
4. `docs(3-1): document web_search-as-base extension architecture`
