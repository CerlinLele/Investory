# Instrument Profile / Web Search 复用改造计划（含实施步骤）

- 日期：2026-05-16
- 范围：`src/investory/agent_core/tools/instrument_profile.py` 与 `src/investory/agent_core/tools/web_search.py`
- 目标：减少重复逻辑，保留现有对外行为与错误语义不变。

## 1. 背景与问题

当前两个工具都实现了一套相似流程：

1. 构造候选 URL 列表。
2. 循环调用 `guarded_get`。
3. 记录 `log_http_attempt`。
4. 失败路径汇总为统一 `ToolResult(ok=False)`。
5. 成功路径解析文本并返回业务结构。

这导致：
- 重复代码高。
- 错误策略与日志语义后续容易漂移。
- 新增第三个 HTTP 工具时会继续复制骨架代码。

## 2. 改造目标

1. 抽取通用 HTTP 候选执行骨架（fallback + logging + error fold）。
2. 两个工具仅保留业务差异：候选源构建、解析规则、成功 payload 结构。
3. 不改变既有 API/返回结构/错误类型与 `retryable` 语义。

## 3. 复用边界（先定接口）

## 3.1 应抽取（共享层）

- 候选请求遍历逻辑（按顺序尝试，首个成功或收敛失败）。
- `guarded_get` 调用与超时/allowlist 参数透传。
- `log_http_attempt` 统一打点。
- `last_error` 维护与最终错误映射。
- 通用 `error_type -> retryable` 策略映射（可覆盖）。

## 3.2 不抽取（工具层）

- `instrument_profile` 的 `source_material/as_of/sources` 业务字段。
- `web_search` 的 `results/provider_attempt_order` 结构。
- 各工具独立的输入校验文案与 parse 判定阈值。

## 3.3 建议共享接口（草案）

可新增 `src/investory/agent_core/tools/http_runner.py`，提供类似接口：

```python
run_guarded_candidates(
    *,
    tool_name: str,
    candidates: list[Candidate],
    timeout_seconds: int,
    allowed_hosts: tuple[str, ...],
    user_agent: str,
    parse_success: Callable[[Candidate, str], ParseOutcome],
    build_not_found_error: Callable[[], ToolResult],
    build_error_result: Callable[[GuardedHttpResult | None], ToolResult],
    max_successes: int = 1,
) -> RunnerOutcome
```

说明：
- `Candidate`：包含 `id/name/url`（例如 provider 名或 source URL）。
- `parse_success`：工具层回调，负责把 HTML 解析成业务结果项；可返回 parse_error。
- `RunnerOutcome`：统一返回成功项列表、尝试顺序、最后错误，供工具层组装 `ToolResult`。

## 4. 实施步骤（Implementation Steps）

## Step 1 - 建立重复点基线（只读）

1. 输出重复逻辑对照表（函数/代码块/行号）。
2. 标注每个重复点：抽取 or 保留。
3. 形成“行为不变清单”（错误码、日志、返回字段）。

交付物：
- `docs/3-1/analysis/http-tooling-reuse-analysis.md`（建议新增）

## Step 2 - 先补测试锁行为

1. 补共享语义测试用例（即便共享模块尚未落地，可先在现有测试补场景）。
2. 重点覆盖：
   - 前序候选失败、后序成功。
   - 全失败时 error_type/retryable 是否一致。
   - parse_error 是否按原逻辑处理。
3. 记录当前基线测试结果。

交付物：
- 测试清单 + 通过记录（worklog）。

## Step 3 - 引入共享执行骨架（新增文件，不改业务语义）

1. 新建 `http_runner.py`（或等价命名）。
2. 迁移通用流程：候选循环、guarded_get、attempt logging、error fold。
3. 先保持 API 内部使用，不对外暴露额外协议。

交付物：
- 新共享模块 + 单元测试。

## Step 4 - 迁移 `web_search` 到共享层

1. 保留 `_provider_candidates`、结果项结构、`provider_attempt_order` 输出。
2. 将网络尝试与失败收敛改为调用共享 runner。
3. 确认 `web_search` 原有测试全绿。

交付物：
- `web_search.py` 精简版本。

## Step 5 - 迁移 `instrument_profile` 到共享层

1. 保留 `_build_candidate_sources` 与 `source_material` 组装逻辑。
2. 将网络尝试与失败收敛改为调用共享 runner。
3. 确认 `instrument_profile` 相关测试与集成路径不变。

交付物：
- `instrument_profile.py` 精简版本。

## Step 5.1 - 实施补充（2026-05-17）

在 Step 3-5 完成后，仍识别到 `instrument_profile.py` 与 `web_search.py` 存在“工具级重复”：

1. HTML 文本清洗逻辑重复。
2. `error_type/retryable` 错误收敛与 `ToolResult` 构造重复。

为进一步降低重复且保持行为不变，新增共享模块：

- `src/investory/agent_core/tools/http_tooling_common.py`
  - `normalize_html_text`
  - `build_error_result`
  - `build_failure_result`
  - `DEFAULT_ERROR_RETRYABLE_POLICY`

并在两个工具中替换本地重复实现为共享调用，不改变：

- 成功 payload 字段结构；
- `error_type/retryable` 语义；
- fallback 顺序语义与测试契约（`guarded_get` monkeypatch 注入点保留）。

## Step 6 - 回归与文档更新

1. 全量跑相关测试：tools/action/router/tasks/gateway。
2. 更新 3-1 文档：新增“共享 HTTP runner”调用链锚点。
3. 更新风险说明：新增工具时的扩展方式。

交付物：
- 更新后的 worklog + 定位文档 + PR 描述。

Step 6 文档锚点（调用链）：
- `src/investory/agent_core/tools/http_runner.py`
  - `run_guarded_candidates`：共享候选执行骨架（guarded_get + logging + parse_error 收敛）。
- `src/investory/agent_core/tools/http_tooling_common.py`
  - `normalize_html_text`：共享 HTML 文本清洗。
  - `build_error_result` / `build_failure_result`：共享错误结果与 last_error 收敛。
- `src/investory/agent_core/tools/web_search.py`
  - `search_web`：业务层解析回调 + payload (`query/results/provider_attempt_order`) 组装。
- `src/investory/agent_core/tools/instrument_profile.py`
  - `fetch_instrument_profile`：业务层解析阈值 + payload (`instrument_name_or_code/source_material/sources/as_of`) 组装。

Step 6 风险补充（新增工具扩展方式）：
- 新增 HTTP 工具时，优先复用 `run_guarded_candidates`，仅在工具层实现：
  - candidates 构造；
  - parse_success 规则；
  - 成功 payload 组装；
  - not_found/default error message。
- 若新工具出现与现有语义冲突的错误策略，不要在工具内复制 `_build_failure_result`，应先评估在 `http_tooling_common.py` 增加可配置参数以保持策略集中。

## 5. 风险与规避

- 风险 1：错误语义回归（`error_type/retryable` 改变）。
  - 规避：先测试锁定，再迁移。
- 风险 2：日志字段漂移导致观测断层。
  - 规避：共享层统一打点格式，迁移前后比对样例日志。
- 风险 3：过度抽象导致工具层可读性下降。
  - 规避：仅抽“执行骨架”，不抽业务 payload 组装。

## 6. 验收标准

1. 两个工具核心重复块显著减少（代码审查可见）。
2. 对外行为一致：
   - 成功返回字段不变。
   - 失败 `error_type/retryable` 不变。
   - fallback 顺序语义不变。
3. 测试通过：
   - 既有相关测试全绿。
   - 新增共享层测试全绿。
4. 文档可追溯：
   - 有接口说明。
   - 有迁移步骤记录与锚点。

## 7. 建议提交拆分（小步可回滚）

1. `test(tools): lock current fallback and error semantics`
2. `feat(tools): add shared http runner for guarded candidate execution`
3. `refactor(web_search): reuse shared http runner without behavior change`
4. `refactor(instrument_profile): reuse shared http runner without behavior change`
5. `docs(3-1): document shared runner architecture and migration anchors`
