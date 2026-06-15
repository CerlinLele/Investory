# Phase 1：统一能力台账 详细实施指南

## 目标
给 `TaskSpec` 补充治理元数据(`side_effect_level`、`tag`、`desc`),把 9 个任务的治理信息显式化,为后续风险审批、灰度、审计提供基础。

## 改动范围

### 1.1 改动 `task_spec.py`

```python
# 新增字段,含默认值(向后兼容)
@dataclass(slots=True)
class TaskSpec:
    name: str
    prompt_name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    side_effect_level: str = "read"  # read / write / exec
    tag: str = ""                    # learning / document_review / risk / ...
    desc: str = ""                   # 一句话描述
```

**为什么用默认值**:所有现有 `TaskSpec` 实例不用改,自动获得 `"read"` 和 `""` 的默认值。

---

### 1.2 改动 `tasks.py` — 填充元数据

```python
FINANCE_QA_TASK = TaskSpec(
    name=FINANCE_QA_NAME,
    prompt_name=FINANCE_QA_NAME,
    input_model=FinanceQAInput,
    output_model=FinanceQAResult,
    side_effect_level="read",
    tag="learning",
    desc="Answer financial questions based on provided material.",
)

LEARNING_MATERIAL_SUMMARY_TASK = TaskSpec(
    name=LEARNING_MATERIAL_SUMMARY_NAME,
    prompt_name=LEARNING_MATERIAL_SUMMARY_NAME,
    input_model=LearningMaterialSummaryInput,
    output_model=LearningMaterialSummaryResult,
    side_effect_level="read",
    tag="learning",
    desc="Summarize learning material into key concepts.",
)

INSTRUMENT_BRIEF_TASK = TaskSpec(
    name=INSTRUMENT_BRIEF_NAME,
    prompt_name=INSTRUMENT_BRIEF_NAME,
    input_model=InstrumentBriefInput,
    output_model=InstrumentBriefResult,
    side_effect_level="read",
    tag="learning",
    desc="Generate a brief overview of a financial instrument.",
)

# Investment document review tasks
INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_NAME,
    prompt_name=INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_NAME,
    input_model=InvestmentDocumentReviewInput,
    output_model=InvestmentDocumentReviewResult,
    side_effect_level="read",
    tag="document_review",
    desc="Review investment document in a single pass without chunking.",
)

INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_REVIEW_PLAN_NAME,
    prompt_name=INVESTMENT_DOCUMENT_REVIEW_PLAN_NAME,
    input_model=InvestmentDocumentReviewPlanInput,
    output_model=InvestmentDocumentReviewPlanResult,
    side_effect_level="read",
    tag="document_review",
    desc="Generate a To-Do plan for chunked document review.",
)

INVESTMENT_DOCUMENT_EXTRACT_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_EXTRACT_NAME,
    prompt_name=INVESTMENT_DOCUMENT_EXTRACT_NAME,
    input_model=InvestmentDocumentReviewExtractInput,
    output_model=InvestmentDocumentReviewExtractResult,
    side_effect_level="read",
    tag="document_review",
    desc="Extract key facts and evidence from a document chunk.",
)

INVESTMENT_DOCUMENT_ANALYZE_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_ANALYZE_NAME,
    prompt_name=INVESTMENT_DOCUMENT_ANALYZE_NAME,
    input_model=InvestmentDocumentReviewAnalyzeInput,
    output_model=InvestmentDocumentReviewAnalyzeResult,
    side_effect_level="read",
    tag="document_review",
    desc="Analyze extracted evidence across a specific dimension.",
)

INVESTMENT_DOCUMENT_SYNTHESIZE_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_SYNTHESIZE_NAME,
    prompt_name=INVESTMENT_DOCUMENT_SYNTHESIZE_NAME,
    input_model=InvestmentDocumentReviewSynthesizeInput,
    output_model=InvestmentDocumentReviewSynthesizeResult,
    side_effect_level="read",
    tag="document_review",
    desc="Synthesize analysis results into final investment document review.",
)

INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_RISK_ASSESSMENT_NAME,
    prompt_name=INVESTMENT_DOCUMENT_RISK_ASSESSMENT_NAME,
    input_model=InvestmentDocumentReviewRiskAssessmentInput,
    output_model=InvestmentDocumentReviewRiskAssessmentResult,
    side_effect_level="write",  # ← 关键:这个任务会影响 approval_status
    tag="risk",
    desc="Assess risk level and determine if human approval is required.",
)

INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_REVIEW_REFLECTION_NAME,
    prompt_name=INVESTMENT_DOCUMENT_REVIEW_REFLECTION_NAME,
    input_model=InvestmentDocumentReviewReflectionInput,
    output_model=InvestmentDocumentReviewReflectionResult,
    side_effect_level="read",
    tag="document_review",
    desc="Reflect on and validate the investment document review results.",
)
```

**关键决策**:
- risk_assessment = `"write"` 因为会产出 `approval_status`,触发人工审批
- 其余 = `"read"` 因为都是产出文本分析结果
- tag 按业务领域(learning/document_review/risk)而不是技术上的分类

---

### 1.3 改动 `routing.py` — 新增查询接口

```python
def list_specs_by_tag(tag: str) -> list[TaskSpec]:
    """按 tag 返回所有匹配的 TaskSpec"""
    return [spec for spec in TASKS.values() if spec.tag == tag]


def list_specs_by_side_effect(level: str) -> list[TaskSpec]:
    """按 side_effect_level 返回所有匹配的 TaskSpec"""
    return [spec for spec in TASKS.values() if spec.side_effect_level == level]


def list_all_specs() -> list[TaskSpec]:
    """返回全量 TaskSpec"""
    return list(TASKS.values())


def get_spec_metadata(task_name: str) -> dict:
    """获取单个任务的治理元数据"""
    spec = TASKS.get(task_name)
    if spec is None:
        raise UnknownTaskTypeError(task_name)
    return {
        "name": spec.name,
        "side_effect_level": spec.side_effect_level,
        "tag": spec.tag,
        "desc": spec.desc,
    }
```

---

## 验证清单

### 1.4 创建 `tests/test_tasks_metadata.py`

```python
import pytest
from investory.agent_core.tasks import TASKS, FINANCE_QA_TASK, INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK
from investory.gateway.routing import (
    list_specs_by_tag,
    list_specs_by_side_effect,
    get_spec_metadata,
)


class TestTasksMetadata:
    """验证所有任务都有合法的治理元数据"""
    
    def test_all_tasks_have_side_effect_level(self):
        """每个 task 都必须有 side_effect_level"""
        valid_levels = {"read", "write", "exec"}
        for spec in TASKS.values():
            assert spec.side_effect_level in valid_levels, (
                f"{spec.name} has invalid side_effect_level: {spec.side_effect_level}"
            )
    
    def test_all_tasks_have_desc(self):
        """每个 task 都应该有描述"""
        for spec in TASKS.values():
            assert spec.desc and len(spec.desc) > 0, (
                f"{spec.name} has no description"
            )
    
    def test_write_tasks_are_tagged(self):
        """所有 side_effect_level=write 的任务应该有对应的 tag"""
        write_tasks = list_specs_by_side_effect("write")
        assert len(write_tasks) > 0, "Should have at least one write task"
        for spec in write_tasks:
            assert spec.tag, f"{spec.name} is write-level but has no tag"
    
    def test_list_specs_by_tag(self):
        """按 tag 查询应该返回正确的任务集"""
        learning_tasks = list_specs_by_tag("learning")
        assert len(learning_tasks) == 3, "Should have 3 learning tasks"
        assert all(spec.tag == "learning" for spec in learning_tasks)
        
        document_review_tasks = list_specs_by_tag("document_review")
        assert len(document_review_tasks) == 5, "Should have 5 document_review tasks"
        
        risk_tasks = list_specs_by_tag("risk")
        assert len(risk_tasks) == 2, "Should have 2 risk tasks"
    
    def test_list_specs_by_side_effect(self):
        """按 side_effect_level 查询应该返回正确的任务集"""
        read_tasks = list_specs_by_side_effect("read")
        assert len(read_tasks) == 8, "Should have 8 read-level tasks"
        assert all(spec.side_effect_level == "read" for spec in read_tasks)
        
        write_tasks = list_specs_by_side_effect("write")
        assert len(write_tasks) == 1, "Should have 1 write-level task"
        assert write_tasks[0].name == INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name
    
    def test_get_spec_metadata(self):
        """能正确获取单个任务的元数据"""
        metadata = get_spec_metadata(FINANCE_QA_TASK.name)
        assert metadata["side_effect_level"] == "read"
        assert metadata["tag"] == "learning"
        assert "Answer" in metadata["desc"]
```

**运行**:
```bash
pytest tests/test_tasks_metadata.py -v
```

---

## 打包与提交

### 1.5 改动检查清单

- [ ] `src/investory/agent_core/contracts/task_spec.py`:新增三个字段
- [ ] `src/investory/agent_core/tasks.py`:所有 9 个 TaskSpec 补充元数据
- [ ] `src/investory/gateway/routing.py`:新增 4 个查询函数
- [ ] `tests/test_tasks_metadata.py`:新建,12 条测试全过
- [ ] 现有测试仍通过:`pytest` 无失败

### 1.6 Commit Message

```
feat(tasks): add governance metadata to TaskSpec

- Add side_effect_level (read/write/exec) to classify task impact
- Add tag (learning/document_review/risk) for business domain grouping
- Add desc field for human-readable task description
- All defaults are backward compatible with existing TaskSpec instances

Metadata allocation:
- side_effect_level="write": risk_assessment (triggers approval gate)
- side_effect_level="read": all other tasks (pure analysis output)
- tag="learning": qa, summary, brief
- tag="document_review": extract, analyze, synthesize, plan, single_pass
- tag="risk": risk_assessment, reflection

New query functions in routing.py:
- list_specs_by_tag(tag)
- list_specs_by_side_effect(level)
- list_all_specs()
- get_spec_metadata(task_name)

This is the foundation for Phase 2-4 (mock executor, plan handler, governance).

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## 预期时间投入

- 改代码:15 分钟
- 写测试:15 分钟
- 验证:10 分钟
- **总计:0.5 天**

---

## 后续检查点

改完 Phase 1 后,应该:
1. ✅ `pytest tests/test_tasks_metadata.py` 12/12 通过
2. ✅ 全量 `pytest` 其它测试不新增失败
3. ✅ 能用 `list_specs_by_side_effect("write")` 查出 risk_assessment
4. ✅ 能用 `list_specs_by_tag("document_review")` 查出 5 个文档审查任务
