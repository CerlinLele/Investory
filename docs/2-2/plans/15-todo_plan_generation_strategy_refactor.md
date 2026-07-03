# 投资文档审查 To-Do Plan 生成策略重构方案

## 问题诊断

### 当前实现的问题

**判断逻辑**：
```python
def should_use_chunk_review(state) -> bool:
    return len(state.document_chunks or []) > 1

# 在 generate_review_todo_plan 中：
if should_use_chunk_review(state):
    todo_plan = self._build_chunk_review_todo_plan(state)  # 代码构建
else:
    result = self.executor.run(INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK, ...)  # LLM 生成
```

**问题**：
1. **概念混淆**：用"是否分块"（技术手段）判断"如何生成计划"（策略决策）
2. **耦合不清**：分块是处理长文档的优化手段，不应决定计划生成方式
3. **扩展受限**：已知文档类型的非分块场景，仍走 LLM 生成（浪费成本、可能幻觉）
4. **语义不准**：`should_use_chunk_review` 名称只表达了"分块"，没有表达"代码构建 vs LLM 生成"

### 真实的区分维度

```
确定性策略（已知文档类型） → 代码构建固定计划
不确定性策略（未知类型）     → LLM 理解后动态生成
```

**当前已知文档类型**（config/review_frameworks.yaml）：
- `etf_factsheet` - ETF 说明书
- `fund_prospectus` - 基金招募说明书
- `product_brochure` - 产品宣传册
- `earnings_report` - 财报
- `learning_material` - 学习材料

这些类型都有明确的 `extract_focus` 和 `analyze_focus`，可以直接构建固定审查计划。

---

## 重构目标

### 核心原则

**按文档类型确定性判断**：
```python
def should_use_code_built_plan(state) -> bool:
    """已知文档类型使用代码构建固定计划，未知类型使用 LLM 生成"""
    if state.document_type is None:
        return False
    if state.document_type == InvestmentDocumentType.UNKNOWN:
        return False
    # 检查是否有对应的 review framework
    return state.document_type in KNOWN_REVIEW_FRAMEWORK_DOCUMENT_TYPES
```

**分块与计划生成解耦**：
- 分块：只决定单个文档是否需要拆分处理（技术优化）
- 计划生成：由文档类型是否已知决定（策略确定性）

### 四种场景

| 文档类型 | 是否分块 | 计划生成方式 | 执行流程 |
|---------|---------|------------|---------|
| 已知类型 | 不分块 | **代码构建** | 单次全文审查（新增） |
| 已知类型 | 分块 | **代码构建** | 分块 extract → analyze → synthesize（已有） |
| UNKNOWN | 不分块 | **LLM 生成** | 按 LLM 生成的计划执行（已有） |
| UNKNOWN | 分块 | **LLM 生成** | 按 LLM 生成的计划执行（已有，理论场景） |

---

## 实施计划

### Step 1: 新增已知类型全文审查计划构建

**新增方法**：`_build_known_type_full_document_plan`

**职责**：为已知文档类型构建单次全文审查计划（不分块场景）

**实现逻辑**：
```python
def _build_known_type_full_document_plan(
    self,
    state: InvestmentDocumentReviewState,
) -> TodoExecutionPlan:
    """
    为已知文档类型构建全文审查计划（不分块）
    
    任务结构：
    1. extract_full_document (kind: INVESTMENT_DOCUMENT_EXTRACT)
       - 从完整文档提取事实和证据
       - 使用 framework.extract_focus
    
    2. analyze_* (kind: INVESTMENT_DOCUMENT_ANALYZE, 依赖 extract)
       - 每个 analyze_focus 生成一个 analyze 任务
       - 使用 framework.analyze_focus
    
    3. synthesize_review (kind: INVESTMENT_DOCUMENT_SYNTHESIZE, 依赖所有 analyze)
       - 综合生成最终审查结果
    """
    if state.review_framework is None:
        raise RuntimeError("Known document type must have review framework")
    
    extract_focus = state.review_framework.extract_focus
    analyze_focus = state.review_framework.analyze_focus
    
    # 1. 构建 extract 任务
    extract_task = {
        "id": "extract_full_document",
        "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
        "title": "Extract evidence from full document",
        "description": (
            "Extract key facts, fees, risks, constraints, disclosures, gaps, "
            "and source citations from the complete document."
        ),
        "payload": {
            DOCUMENT_TEXT_FIELD: state.input_payload.get(DOCUMENT_TEXT_FIELD),
            EXTRACT_FOCUS_FIELD: extract_focus,
            CHUNK_REVIEW_SCOPE_FIELD: FULL_DOCUMENT_REVIEW_SCOPE,
        },
        "depends_on": [],
        "completion_criteria": [
            "Output contains only facts and evidence from the document.",
            "Important gaps are recorded as information gaps.",
            "Source citations identify supporting sections.",
        ],
    }
    
    # 2. 构建 analyze 任务
    analyze_tasks = []
    for focus in analyze_focus:
        task_id = f"analyze_{_normalize_todo_task_id_fragment(focus)}"
        analyze_tasks.append({
            "id": task_id,
            "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
            "title": f"Analyze {focus}",
            "description": (
                "Review the extracted evidence for this dimension and "
                "identify supported risks, inconsistencies, limits, and gaps."
            ),
            "payload": {ANALYZE_FOCUS_FIELD: [focus]},
            "depends_on": ["extract_full_document"],
            "completion_criteria": [
                f"Findings stay focused on {focus}.",
                "Findings are based only on successful extraction results.",
                "Material gaps, conflicts, and boundary limits are identified.",
            ],
        })
    
    analyze_task_ids = [task["id"] for task in analyze_tasks]
    
    # 3. 构建 synthesize 任务
    synthesize_task = {
        "id": "synthesize_full_document_review",
        "kind": TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE,
        "title": "Synthesize full-document review",
        "description": (
            "Produce the final investment document review from the extracted "
            "evidence and analysis results."
        ),
        "payload": {},
        "depends_on": analyze_task_ids,
        "completion_criteria": [
            "Final review covers all extracted evidence.",
            "Facts, risks, gaps, boundary notes, and summary are supported.",
        ],
    }
    
    # 4. 组装计划
    tasks = [extract_task] + analyze_tasks + [synthesize_task]
    todo_plan = TodoExecutionPlan.model_validate({
        "tasks": tasks,
        "summary": (
            f"Extract evidence from the {state.document_type.value}, "
            f"analyze by review dimension, and synthesize the final review."
        ),
    })
    
    ensure_valid_todo_plan(todo_plan)
    return todo_plan
```

---

### Step 2: 重命名和重构判断逻辑

**重命名**：
```python
# 旧名称（语义不清）
def should_use_chunk_review(state) -> bool:
    return len(state.document_chunks or []) > 1

# 新名称（明确策略）
def should_use_code_built_plan(state) -> bool:
    """已知文档类型使用代码构建，未知类型使用 LLM 生成"""
    if state.document_type is None:
        return False
    if state.document_type == InvestmentDocumentType.UNKNOWN:
        return False
    return state.document_type in KNOWN_REVIEW_FRAMEWORK_DOCUMENT_TYPES

def is_chunked_document(state) -> bool:
    """判断文档是否已分块（技术层面）"""
    return len(state.document_chunks or []) > 1
```

**重构 `generate_review_todo_plan`**：
```python
def generate_review_todo_plan(
    self,
    state: InvestmentDocumentReviewState,
) -> dict[str, Any]:
    # 判断：已知类型用代码构建，未知类型用 LLM
    if should_use_code_built_plan(state):
        try:
            # 进一步判断是否分块
            if is_chunked_document(state):
                # 场景 1: 已知类型 + 分块
                todo_plan = self._build_chunk_review_todo_plan(state)
            else:
                # 场景 2: 已知类型 + 全文（新增）
                todo_plan = self._build_known_type_full_document_plan(state)
        except (ValidationError, TodoPlanValidationException) as exc:
            return {
                "output": TaskResult(
                    ok=False,
                    task_name=INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name,
                    error=normalize_task_error(exc, stage="output_validation"),
                )
            }
        
        _log_review_todo_plan_generated(
            session_id=state.session_id,
            todo_plan=todo_plan,
            document_type=state.document_type,
            chunk_count=len(state.document_chunks) if is_chunked_document(state) else 0,
        )
        return {"todo_plan": todo_plan}
    
    # 场景 3/4: Unknown 类型用 LLM 生成（分块或全文）
    plan_payload = self.build_review_todo_plan_payload(state)
    result = self.executor.run(
        INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
        plan_payload,
    )
    if not result.ok:
        return {"output": result}
    
    try:
        todo_plan = TodoExecutionPlan.model_validate(result.result)
        ensure_valid_todo_plan(todo_plan)
    except (ValidationError, TodoPlanValidationException) as exc:
        return {
            "output": TaskResult(
                ok=False,
                task_name=INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name,
                error=normalize_task_error(exc, stage="output_validation"),
            )
        }
    
    _log_review_todo_plan_generated(
        session_id=state.session_id,
        todo_plan=todo_plan,
        document_type=state.document_type,
        chunk_count=len(state.document_chunks) if is_chunked_document(state) else 0,
    )
    return {"todo_plan": todo_plan}
```

---

### Step 3: 调整 `_build_chunk_review_todo_plan`

**当前问题**：方法名暗示只用于分块，但实际上已经承担了"已知类型代码构建"的职责

**改进**：保持方法不变，但明确其适用范围是"已知类型 + 分块"

或者重命名为 `_build_known_type_chunk_plan`，与新增的 `_build_known_type_full_document_plan` 对称。

---

### Step 4: 更新日志和常量

**新增常量**：
```python
FULL_DOCUMENT_EXTRACT_TASK_ID = "extract_full_document"
FULL_DOCUMENT_ANALYZE_TASK_ID_PREFIX = "analyze"
FULL_DOCUMENT_SYNTHESIZE_TASK_ID = "synthesize_full_document_review"
```

**日志调整**：
- `_log_review_todo_plan_generated` 已支持 `chunk_count=0` 场景
- 可以增加一个 `plan_source` 字段标识 "code_built_known_type" | "code_built_chunk" | "llm_generated"

---

## 验证计划

### 测试场景

**场景 1：已知类型 + 短文档（不分块）**
- 输入：3000 字的 ETF factsheet
- 预期：代码构建全文审查计划
- 任务结构：1 extract + N analyze + 1 synthesize

**场景 2：已知类型 + 长文档（分块）**
- 输入：30000 字的 Fund prospectus
- 预期：代码构建分块审查计划（当前逻辑）
- 任务结构：M extract_chunk + N analyze + 1 synthesize

**场景 3：Unknown 类型 + 短文档**
- 输入：非标准投资建议文档
- 预期：LLM 生成审查计划
- 任务结构：由 LLM 决定

**场景 4：Unknown 类型 + 长文档（理论场景）**
- 输入：超长非标准文档
- 预期：LLM 生成审查计划（可能需要在 prompt 中提示分块）
- 任务结构：由 LLM 决定

### 回归测试

确保已有的 apifox smoke test 通过：
- `hyg-file-upload` 测试（ETF factsheet 分块场景）
- 其他已知类型的测试用例

---

## 收益

### 成本优化

**节省 LLM 调用**：
- 已知类型的短文档，不再调用 LLM 生成计划
- 按当前测试比例估算，约 30% 场景受益

### 质量提升

**确定性保证**：
- 已知类型的审查流程完全可预测
- 避免 LLM 生成计划时的幻觉风险（任务 ID 错误、依赖循环等）

**维护性增强**：
- 判断逻辑清晰：文档类型决定策略
- 扩展性强：新增已知类型只需添加 framework 配置

### 语义准确

**概念解耦**：
- 分块：技术优化手段
- 代码构建 vs LLM：策略确定性判断
- 不再混淆

---

## 风险和缓解

### 风险 1：已知类型全文审查未充分测试

**缓解**：
- 先在测试环境验证已知类型的短文档
- 逐步放量到生产

### 风险 2：某些已知类型的 framework 不完善

**缓解**：
- 增加 framework 完整性校验
- 缺少 extract_focus 或 analyze_focus 时降级到 LLM 生成

### 风险 3：Unknown 类型分块场景的 LLM 生成质量

**缓解**：
- 在 LLM prompt 中增加分块场景的引导
- 或者对 Unknown + 长文档强制使用简化的代码构建策略

---

## 实施优先级

### P0: 核心重构
1. 新增 `_build_known_type_full_document_plan` 方法
2. 重构 `generate_review_todo_plan` 判断逻辑
3. 重命名 `should_use_chunk_review` → `should_use_code_built_plan`

### P1: 完善和测试
4. 补充场景 1 的单元测试（已知类型 + 全文）
5. 回归测试已有场景（分块、Unknown）
6. 更新日志和常量

### P2: 优化
7. 考虑 Unknown 类型分块场景的优化
8. 增加 framework 完整性校验
9. 性能和成本监控

---

## 总结

**核心改进**：将判断逻辑从"是否分块"改为"文档类型是否已知"

**架构优势**：
- 概念清晰：策略确定性与技术优化解耦
- 成本优化：已知类型不再浪费 LLM 调用
- 扩展性强：新增已知类型只需配置 framework

**实施路径**：
1. 新增已知类型全文计划构建
2. 重构判断逻辑
3. 测试和验证
4. 逐步放量