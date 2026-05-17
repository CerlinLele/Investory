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

## Step A - 基线锁定（不改实现）

1. A1: 列出当前行为锚点
- 输入：当前 `instrument_profile.py` 与现有测试。
- 产出：成功字段、失败映射、fallback 顺序的代码锚点清单。

2. A2: 锁定现有测试覆盖
- 运行：
  - `tests/test_instrument_profile_tool.py`
  - `tests/test_web_search_tool.py`（确保前置工具行为稳定）
- 记录：通过数、失败原因（若依赖缺失）。

3. A3: 补缺口测试（仅在缺口存在时）
- 新增场景：
  - web_search 前置失败时的 error fold。
  - 有候选但提取不足时 parse_error。
  - 无候选可用时 not_found。

完成定义：
- 当前行为被测试显式锁定，并记录到 worklog。

交付物：
- 测试基线报告（worklog）

## Step B - 候选装配层抽取（adapter）

1. B1: 定义 `web_search -> profile candidates` 适配函数
- 建议函数：`_build_profile_candidates_from_search(...)`
- 输入：`search_web` 返回 `results`。
- 输出：`list[Candidate]`（`id` 与 `url`）。

2. B2: 设计并实现去重策略
- 规则：按 URL 去重，保留首出现顺序。
- 目标：不打乱 provider 原始优先级。

3. B3: 过滤规则落地
- 规则：
  - URL 非空、https、可解析 hostname。
  - host 在工具 allowlist 可接受范围内。
- 行为：过滤项不抛异常，记录为候选裁剪。

4. B4: 为适配函数补单测
- 场景：
  - 空 results。
  - 重复 URL。
  - 非法 URL / 非 https URL。
  - 多 provider 顺序保持。

完成定义：
- adapter 层独立可测，输入输出契约固定。

交付物：
- 候选装配函数 + 单测

## Step C - 接入 web_search 前置召回

1. C1: 在 `fetch_instrument_profile` 增加可注入 `searcher`
- 默认：`search_web`。
- 测试：可 monkeypatch/注入 fake searcher。

2. C2: 前置调用 `search_web`
- query：`instrument_name_or_code`。
- 参数策略：`top_k` 默认值明确（可常量化），`provider_hint` 可选。

3. C3: 将 search results 映射为 profile candidates
- 调用 Step B adapter。
- 若 candidates 为空，走 `not_found` 语义。

4. C4: 用 `run_guarded_candidates` 执行提取
- 保持当前 parse threshold：
  - `MIN_SOURCE_MATERIAL_CHARS`
- 保持 `source_material` 拼装规则不变。

5. C5: 错误映射对齐
- `search_web` 失败：
  - 归一到 `instrument_profile` 的 error/retryable 策略。
- 抓取/解析失败：
  - 继续沿用 `build_failure_result` 收敛。

完成定义：
- 主流程切换到“search-first + extract-second”，对外 schema 不变。

交付物：
- `instrument_profile` 主流程迁移完成
- 兼容现有调用点（actions/executors）

## Step D - 回归验证（工具层 + 调用链）

1. D1: 工具层回归
- `tests/test_instrument_profile_tool.py`
- `tests/test_web_search_tool.py`
- `tests/test_http_runner.py`

2. D2: action 链路回归
- `fetch_then_run_instrument_brief` 相关测试：
  - 执行器成功路径
  - 执行器失败回传路径

3. D3: 关键验收断言
- 输出 schema 不变。
- `error_type/retryable` 不变。
- `sources` 字段顺序稳定（与候选顺序一致）。
- 用户可见失败文案符合既有语义。

完成定义：
- 相关测试通过；若因环境依赖阻塞，worklog 记录阻塞项与复跑命令。

交付物：
- 回归结果记录

## Step E - 文档与发布准备

1. E1: 更新计划文档
- 在 `http-tooling-reuse-plan.md` 增加本次扩展路径锚点和边界说明。

2. E2: 更新 worklog
- 记录每个步骤的命令、文件、测试结果、阻塞项。

3. E3: 更新分析文档
- 补一页“search-first profile flow”说明（输入/输出/失败收敛图）。

4. E4: PR 描述补充
- 增加“行为兼容性声明”与“已知风险/回滚方式”。

完成定义：
- 文档可追踪到代码锚点、测试证据、风险与扩展方式。

交付物：
- 完整文档锚点 + worklog + PR 更新稿

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
