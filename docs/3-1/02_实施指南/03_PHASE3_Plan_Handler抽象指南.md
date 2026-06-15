# Phase 3：Plan Handler 抽象 详细实施指南

## 目标
把投资文档审查流程的两种规划策略(规则驱动 chunk review vs 模型驱动 LLM plan)从 `if` 写死抽成可替换的 `ReviewPlanHandler` 接口,为 v1/v2/v3 版本的灵活切换奠基。

## 改动范围

### 3.1 新建 `runtime/flow/investment_document_review/plan_handler.py`

```python
"""Plan handler interface and implementations for investment document review."""

from typing import Protocol

from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentReviewState,
)
from investory.agent_core.contracts.todo_execution import TodoExecutionPlan


class ReviewPlanHandler(Protocol):
    """
    Protocol for generating a To-Do plan for investment document review.
    
    Implementations can vary strategy:
    - ChunkRulePlanHandler: deterministic rule-based chunking
    - LLMPlanHandler: LLM-driven dynamic planning
    - FixedAuditPlanHandler: fixed plan for testing/auditing
    """
    
    def build_plan(self, state: InvestmentDocumentReviewState) -> TodoExecutionPlan:
        """
        Generate a To-Do plan for the current review state.
        
        Args:
            state: current review state with document, type, framework
        
        Returns:
            TodoExecutionPlan with tasks, dependencies, and strategy
        
        Raises:
            RuntimeError: if plan cannot be generated (missing required state)
        """
        ...


class ChunkRulePlanHandler:
    """
    Rule-based plan handler: deterministically generates chunk review plan.
    
    Strategy:
    - Split document into chunks
    - Create parallel extract tasks (one per chunk)
    - Create analyze tasks based on review framework dimensions
    - Create synthesis task depending on all analysis tasks
    
    Advantages:
    - Deterministic (same input → same plan)
    - No LLM calls needed
    - Good for high-volume processing
    - Suitable for v2 (cost-optimized version)
    
    Disadvantages:
    - Fixed strategy, no dynamic adjustment
    - May over-parallelize for small documents
    """
    
    def __init__(self):
        pass
    
    def build_plan(self, state: InvestmentDocumentReviewState) -> TodoExecutionPlan:
        """
        Generate chunk-based review plan (existing _build_chunk_review_todo_plan logic).
        
        This is a direct port of the current flow's _build_chunk_review_todo_plan method.
        """
        # Import locally to avoid circular dependency
        from investory.agent_core.runtime.flow.investment_document_review.document_review_flow import (
            _build_chunk_review_analyze_tasks,
            CHUNK_EXTRACT_TASK_ID_PREFIX,
            ANALYZE_TASK_ID_PREFIX,
            SYNTHESIZE_REVIEW_TASK_ID,
            DOCUMENT_TEXT_FIELD,
            EXTRACT_FOCUS_FIELD,
            ANALYZE_FOCUS_FIELD,
            CHUNK_INDEX_FIELD,
            CHUNK_COUNT_FIELD,
            CHUNK_REVIEW_SCOPE_FIELD,
            CHUNK_REVIEW_SCOPE,
        )
        from investory.agent_core.contracts.todo_execution import (
            TodoTaskKind,
        )
        
        if state.review_payload is None:
            raise RuntimeError(
                "Chunk review plan requires review_payload (built by review framework node)."
            )
        
        chunk_count = len(state.document_chunks)
        extract_task_ids = [
            f"{CHUNK_EXTRACT_TASK_ID_PREFIX}_{idx + 1:04d}"
            for idx in range(chunk_count)
        ]
        extract_focus = state.review_payload.get(EXTRACT_FOCUS_FIELD) or []
        analyze_focus = state.review_payload.get(ANALYZE_FOCUS_FIELD) or []
        analyze_tasks = _build_chunk_review_analyze_tasks(
            analyze_focus=analyze_focus,
            extract_task_ids=extract_task_ids,
        )
        analyze_task_ids = [task["id"] for task in analyze_tasks]
        
        tasks = [
            {
                "id": task_id,
                "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                "title": f"Extract evidence from document chunk {idx + 1} of {chunk_count}",
                "description": (
                    "Extract lightweight, document-grounded evidence from this chunk: "
                    "key facts, fees, risks, constraints, disclosures, gaps, unusual "
                    "statements, and source citations."
                ),
                "payload": {
                    DOCUMENT_TEXT_FIELD: chunk,
                    EXTRACT_FOCUS_FIELD: extract_focus,
                    CHUNK_INDEX_FIELD: idx,
                    CHUNK_COUNT_FIELD: chunk_count,
                    CHUNK_REVIEW_SCOPE_FIELD: CHUNK_REVIEW_SCOPE,
                },
                "depends_on": [],
                "completion_criteria": [
                    "Output contains only facts and evidence visible in this chunk.",
                    "Important missing or weak evidence is recorded as information gaps.",
                    "Source citations identify the supporting chunk text or section.",
                ],
            }
            for idx, (task_id, chunk) in enumerate(
                zip(extract_task_ids, state.document_chunks, strict=True)
            )
        ]
        tasks.extend(
            analyze_tasks
            + [
                {
                    "id": SYNTHESIZE_REVIEW_TASK_ID,
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE,
                    "title": "Synthesize full-document review",
                    "description": (
                        "Produce the final investment document review from the aggregated "
                        "chunk evidence and analysis results."
                    ),
                    "payload": {},
                    "depends_on": analyze_task_ids,
                    "completion_criteria": [
                        "Final review covers extracted evidence from all document chunks.",
                        "Facts, risks, gaps, boundary notes, and summary are supported by task results.",
                    ],
                },
            ]
        )
        
        todo_plan = TodoExecutionPlan.model_validate(
            {
                "tasks": tasks,
                "summary": (
                    "Extract lightweight evidence from every document chunk, analyze the "
                    "evidence by review dimension, then synthesize the full document review."
                ),
            }
        )
        
        from investory.agent_core.runtime.todo_core.plan_validator import (
            ensure_valid_todo_plan,
        )
        ensure_valid_todo_plan(todo_plan)
        return todo_plan


class LLMPlanHandler:
    """
    LLM-driven plan handler: delegates plan generation to LLM.
    
    Strategy:
    - Call INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK (LLM generates todo plan)
    - LLM decides task breakdown based on document content and review framework
    - More flexible but requires LLM call
    
    Advantages:
    - Dynamic adaptation to document characteristics
    - LLM can make smart decisions about task decomposition
    - Suitable for v0/v1/v3 (baseline, optimized, reflection versions)
    
    Disadvantages:
    - Slower (requires LLM call)
    - Non-deterministic (same input may produce different plans)
    - Higher cost
    """
    
    def __init__(self, executor):
        """
        Args:
            executor: TaskExecutor for running LLM planning task
        """
        from investory.agent_core.runtime.task_executor import TaskExecutor
        from investory.agent_core.tasks import INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK
        
        self.executor = executor
        self.task_spec = INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK
    
    def build_plan(self, state: InvestmentDocumentReviewState) -> TodoExecutionPlan:
        """
        Generate plan by calling LLM planning task.
        
        This is a port of current flow's generate_review_todo_plan logic for LLM path.
        """
        from investory.agent_core.contracts.result_types import normalize_task_error
        from pydantic import ValidationError
        
        plan_payload = self._build_plan_payload(state)
        
        result = self.executor.run(self.task_spec, plan_payload)
        if not result.ok:
            raise RuntimeError(
                f"LLM plan generation failed: {result.error.debug_message if result.error else 'unknown error'}"
            )
        
        try:
            todo_plan = TodoExecutionPlan.model_validate(result.result)
            from investory.agent_core.runtime.todo_core.plan_validator import (
                ensure_valid_todo_plan,
            )
            ensure_valid_todo_plan(todo_plan)
        except (ValidationError, Exception) as exc:
            raise RuntimeError(
                f"LLM plan validation failed: {str(exc)}"
            ) from exc
        
        return todo_plan
    
    def _build_plan_payload(self, state: InvestmentDocumentReviewState) -> dict:
        """Build payload for LLM plan generation task."""
        from investory.agent_core.runtime.flow.investment_document_review.document_review_flow import (
            DOCUMENT_TEXT_FIELD,
            DOCUMENT_TYPE_FIELD,
            EXTRACT_FOCUS_FIELD,
            ANALYZE_FOCUS_FIELD,
            REVIEW_GOAL_FIELD,
        )
        
        if state.review_payload is None:
            raise RuntimeError("LLM plan generation requires review_payload.")
        
        return {
            DOCUMENT_TEXT_FIELD: state.review_payload.get(DOCUMENT_TEXT_FIELD),
            DOCUMENT_TYPE_FIELD: state.review_payload.get(DOCUMENT_TYPE_FIELD),
            EXTRACT_FOCUS_FIELD: state.review_payload.get(EXTRACT_FOCUS_FIELD),
            ANALYZE_FOCUS_FIELD: state.review_payload.get(ANALYZE_FOCUS_FIELD),
            REVIEW_GOAL_FIELD: state.review_payload.get(REVIEW_GOAL_FIELD),
        }


class FixedAuditPlanHandler:
    """
    Fixed plan handler: returns a predetermined plan for testing/auditing.
    
    Strategy:
    - Config-driven or hardcoded to always return the same plan
    - Useful for testing flow logic without variability
    - Can simulate different scenarios (success, failure, edge cases)
    
    Advantages:
    - Completely deterministic
    - No dependencies (no executor, no LLM, no file I/O)
    - Fast execution
    - Perfect for unit testing and CI/CD
    
    Disadvantages:
    - Doesn't reflect real document variation
    - Only useful for testing specific scenarios
    """
    
    def __init__(self, plan_strategy: str = "simple"):
        """
        Args:
            plan_strategy: 'simple' (minimal plan) or 'comprehensive' (full plan)
        """
        self.plan_strategy = plan_strategy
    
    def build_plan(self, state: InvestmentDocumentReviewState) -> TodoExecutionPlan:
        """Return a fixed predetermined plan."""
        from investory.agent_core.contracts.todo_execution import (
            TodoTaskKind,
            TodoExecutionPlan,
        )
        
        if self.plan_strategy == "simple":
            # Minimal plan: just extract + synthesize, no analysis
            return TodoExecutionPlan.model_validate(
                {
                    "tasks": [
                        {
                            "id": "extract_simple",
                            "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                            "title": "Extract evidence",
                            "description": "Simple extraction task",
                            "payload": {},
                            "depends_on": [],
                            "completion_criteria": ["Evidence extracted"],
                        },
                        {
                            "id": "synthesize_simple",
                            "kind": TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE,
                            "title": "Synthesize review",
                            "description": "Simple synthesis task",
                            "payload": {},
                            "depends_on": ["extract_simple"],
                            "completion_criteria": ["Review synthesized"],
                        },
                    ],
                    "summary": "Simple audit plan: extract → synthesize",
                }
            )
        else:  # comprehensive
            # More realistic plan: extract + analyze + synthesize
            return TodoExecutionPlan.model_validate(
                {
                    "tasks": [
                        {
                            "id": "extract_audit",
                            "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                            "title": "Extract evidence",
                            "description": "Audit extraction task",
                            "payload": {},
                            "depends_on": [],
                            "completion_criteria": ["Evidence extracted"],
                        },
                        {
                            "id": "analyze_audit",
                            "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                            "title": "Analyze evidence",
                            "description": "Audit analysis task",
                            "payload": {},
                            "depends_on": ["extract_audit"],
                            "completion_criteria": ["Evidence analyzed"],
                        },
                        {
                            "id": "synthesize_audit",
                            "kind": TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE,
                            "title": "Synthesize review",
                            "description": "Audit synthesis task",
                            "payload": {},
                            "depends_on": ["analyze_audit"],
                            "completion_criteria": ["Review synthesized"],
                        },
                    ],
                    "summary": "Comprehensive audit plan: extract → analyze → synthesize",
                }
            )
```

---

### 3.2 改动 `document_review_flow.py`

**改动位置 1:构造函数(加 plan_handler 注入)**

```python
class InvestmentDocumentReviewFlow:
    def __init__(
        self,
        executor: TaskExecutor | None = None,
        llm_router: InvestmentDocumentReviewRouter | None = None,
        *,
        supports_realtime_data: bool = False,
        todo_resume_store: InvestmentDocumentReviewTodoResumeStore | None = None,
        plan_handler: "ReviewPlanHandler | None" = None,  # 新增
    ) -> None:
        self.executor = executor or TaskExecutor()
        self.llm_router = llm_router or InvestmentDocumentReviewLLMRouter()
        self.supports_realtime_data = supports_realtime_data
        self.todo_resume_store = todo_resume_store
        self.plan_handler = plan_handler or self._default_plan_handler()  # 新增
        self.graph = self._build_graph()
    
    def _default_plan_handler(self):
        """
        Create default plan handler preserving current behavior.
        
        Current logic: if should_use_chunk_review → ChunkRulePlanHandler
                      else → LLMPlanHandler
        """
        from investory.agent_core.runtime.flow.investment_document_review.plan_handler import (
            DefaultAdaptivePlanHandler,
        )
        return DefaultAdaptivePlanHandler(executor=self.executor)
```

**改动位置 2:generate_review_todo_plan 方法(使用 plan_handler)**

```python
def generate_review_todo_plan(
    self,
    state: InvestmentDocumentReviewState,
) -> dict[str, Any]:
    try:
        todo_plan = self.plan_handler.build_plan(state)
    except (ValidationError, Exception) as exc:
        return {
            "output": TaskResult(
                ok=False,
                task_name=INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name,
                error=normalize_task_error(exc, stage="plan_generation"),
            )
        }
    
    _log_review_todo_plan_generated(
        session_id=state.session_id,
        todo_plan=todo_plan,
        document_type=state.document_type,
        chunk_count=_guess_review_plan_chunk_count(state),
    )
    return {"todo_plan": todo_plan}
```

**删除旧逻辑**:
- 删除 `_build_chunk_review_todo_plan()` 方法(搬到 `ChunkRulePlanHandler`)
- 删除 `should_use_chunk_review` 条件分支(搬到 `DefaultAdaptivePlanHandler`)

---

### 3.3 新增 `DefaultAdaptivePlanHandler` (保持现有行为)

在 `plan_handler.py` 新增:

```python
class DefaultAdaptivePlanHandler:
    """
    Default handler that preserves current behavior.
    
    Adaptively chooses between:
    - ChunkRulePlanHandler if document has multiple chunks
    - LLMPlanHandler if single-chunk document
    """
    
    def __init__(self, executor):
        self.executor = executor
        self.chunk_handler = ChunkRulePlanHandler()
        self.llm_handler = LLMPlanHandler(executor)
    
    def build_plan(self, state: InvestmentDocumentReviewState) -> TodoExecutionPlan:
        """Delegate to appropriate handler based on chunk count."""
        from investory.agent_core.runtime.flow.investment_document_review.document_review_flow import (
            should_use_chunk_review,
        )
        
        if should_use_chunk_review(state):
            return self.chunk_handler.build_plan(state)
        else:
            return self.llm_handler.build_plan(state)
```

---

### 3.4 新建测试 `tests/investment_document_review/test_plan_handlers.py`

```python
"""Tests for investment document review plan handlers."""

import pytest

from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentReviewState,
    InvestmentDocumentType,
)
from investory.agent_core.contracts.todo_execution import TodoTaskKind
from investory.agent_core.runtime.execution import (
    MockTaskExecutor,
    get_investment_document_review_fixtures,
)
from investory.agent_core.runtime.flow.investment_document_review.plan_handler import (
    ChunkRulePlanHandler,
    LLMPlanHandler,
    FixedAuditPlanHandler,
    DefaultAdaptivePlanHandler,
)


@pytest.fixture
def review_state_multi_chunk():
    """State with multiple document chunks (triggers chunk handler)."""
    state = InvestmentDocumentReviewState(
        session_id="test-multi",
        input_payload={"document_text": "Test doc"},
    )
    state.document_chunks = ["Chunk 1 text", "Chunk 2 text", "Chunk 3 text"]
    state.document_type = InvestmentDocumentType.MUTUAL_FUND
    state.review_payload = {
        "document_text": "Full text",
        "document_type": InvestmentDocumentType.MUTUAL_FUND,
        "extract_focus": ["fees", "risks"],
        "analyze_focus": ["cost", "risk", "performance"],
        "review_goal": "Test",
    }
    return state


@pytest.fixture
def review_state_single_chunk():
    """State with single document chunk (triggers LLM handler)."""
    state = InvestmentDocumentReviewState(
        session_id="test-single",
        input_payload={"document_text": "Test doc"},
    )
    state.document_chunks = ["Single chunk text"]
    state.document_type = InvestmentDocumentType.MUTUAL_FUND
    state.review_payload = {
        "document_text": "Full text",
        "document_type": InvestmentDocumentType.MUTUAL_FUND,
        "extract_focus": ["fees"],
        "analyze_focus": ["cost"],
        "review_goal": "Test",
    }
    return state


class TestChunkRulePlanHandler:
    """Test rule-based plan handler."""
    
    def test_chunk_handler_creates_extract_tasks(self, review_state_multi_chunk):
        """Chunk handler should create one extract task per chunk."""
        handler = ChunkRulePlanHandler()
        plan = handler.build_plan(review_state_multi_chunk)
        
        extract_tasks = [t for t in plan.tasks if t.kind == TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT]
        assert len(extract_tasks) == 3, "Should have 3 extract tasks (one per chunk)"
    
    def test_chunk_handler_creates_analyze_tasks(self, review_state_multi_chunk):
        """Chunk handler should create analyze tasks based on analyze_focus."""
        handler = ChunkRulePlanHandler()
        plan = handler.build_plan(review_state_multi_chunk)
        
        analyze_tasks = [t for t in plan.tasks if t.kind == TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE]
        assert len(analyze_tasks) > 0, "Should have analyze tasks"
    
    def test_chunk_handler_creates_synthesize_task(self, review_state_multi_chunk):
        """Chunk handler should create synthesis task depending on analysis."""
        handler = ChunkRulePlanHandler()
        plan = handler.build_plan(review_state_multi_chunk)
        
        synthesize_tasks = [
            t for t in plan.tasks if t.kind == TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE
        ]
        assert len(synthesize_tasks) == 1, "Should have exactly one synthesize task"
        
        # Verify synthesis depends on analysis
        synthesize_task = synthesize_tasks[0]
        assert len(synthesize_task.depends_on) > 0, "Synthesis should depend on other tasks"


class TestLLMPlanHandler:
    """Test LLM-driven plan handler."""
    
    def test_llm_handler_calls_executor(self, review_state_single_chunk):
        """LLM handler should call executor with planning task."""
        fixtures = get_investment_document_review_fixtures()
        executor = MockTaskExecutor(fixtures)
        
        # Add the plan task to fixtures
        from investory.agent_core.contracts.result_types import TaskResult
        from investory.agent_core.contracts.todo_execution import (
            TodoExecutionPlan,
            TodoTask,
            TodoTaskKind,
        )
        
        plan_result = TodoExecutionPlan(
            tasks=[
                TodoTask(
                    id="test_task",
                    kind=TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    title="Test",
                    description="Test task",
                    payload={},
                    depends_on=[],
                    completion_criteria=["Test"],
                )
            ],
            summary="Test plan",
        )
        
        executor.fixtures["investment_document_review_plan"] = TaskResult(
            ok=True,
            task_name="investment_document_review_plan",
            result=plan_result.model_dump(),
        )
        
        handler = LLMPlanHandler(executor)
        plan = handler.build_plan(review_state_single_chunk)
        
        assert plan is not None
        assert executor.get_call_count() > 0


class TestFixedAuditPlanHandler:
    """Test fixed audit plan handler."""
    
    def test_fixed_handler_simple_plan(self, review_state_single_chunk):
        """Simple fixed plan should have minimal tasks."""
        handler = FixedAuditPlanHandler(plan_strategy="simple")
        plan = handler.build_plan(review_state_single_chunk)
        
        assert len(plan.tasks) == 2, "Simple plan should have 2 tasks (extract + synthesize)"
    
    def test_fixed_handler_comprehensive_plan(self, review_state_single_chunk):
        """Comprehensive fixed plan should have more tasks."""
        handler = FixedAuditPlanHandler(plan_strategy="comprehensive")
        plan = handler.build_plan(review_state_single_chunk)
        
        assert len(plan.tasks) == 3, "Comprehensive plan should have 3 tasks"


class TestDefaultAdaptivePlanHandler:
    """Test default handler that adapts between strategies."""
    
    def test_default_handler_uses_chunk_for_multi_chunk(self, review_state_multi_chunk):
        """Default handler should use chunk handler for multi-chunk document."""
        fixtures = get_investment_document_review_fixtures()
        executor = MockTaskExecutor(fixtures)
        
        handler = DefaultAdaptivePlanHandler(executor)
        plan = handler.build_plan(review_state_multi_chunk)
        
        # Should have chunk-based structure (multiple extract tasks)
        extract_tasks = [t for t in plan.tasks if t.kind == TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT]
        assert len(extract_tasks) == 3
    
    def test_default_handler_uses_llm_for_single_chunk(self, review_state_single_chunk):
        """Default handler should use LLM handler for single-chunk document."""
        fixtures = get_investment_document_review_fixtures()
        executor = MockTaskExecutor(fixtures)
        
        # Add plan task to fixtures
        from investory.agent_core.contracts.result_types import TaskResult
        from investory.agent_core.contracts.todo_execution import (
            TodoExecutionPlan,
            TodoTask,
            TodoTaskKind,
        )
        
        plan_result = TodoExecutionPlan(
            tasks=[
                TodoTask(
                    id="llm_task",
                    kind=TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    title="LLM-generated",
                    description="Generated by LLM",
                    payload={},
                    depends_on=[],
                    completion_criteria=["Done"],
                )
            ],
            summary="LLM plan",
        )
        
        executor.fixtures["investment_document_review_plan"] = TaskResult(
            ok=True,
            task_name="investment_document_review_plan",
            result=plan_result.model_dump(),
        )
        
        handler = DefaultAdaptivePlanHandler(executor)
        plan = handler.build_plan(review_state_single_chunk)
        
        assert plan is not None
```

---

## 改动检查清单

- [ ] 新建 `src/investory/agent_core/runtime/flow/investment_document_review/plan_handler.py`
- [ ] 新增 `ReviewPlanHandler` Protocol
- [ ] 新增 `ChunkRulePlanHandler` 类(从 flow 搬过来)
- [ ] 新增 `LLMPlanHandler` 类(新实现)
- [ ] 新增 `FixedAuditPlanHandler` 类(新实现)
- [ ] 新增 `DefaultAdaptivePlanHandler` 类(保持现有行为)
- [ ] 改动 `document_review_flow.py`:构造函数加 `plan_handler` 注入
- [ ] 改动 `document_review_flow.py`:generate_review_todo_plan 使用 plan_handler
- [ ] 删除旧代码:`_build_chunk_review_todo_plan()` 方法从 flow 搬出
- [ ] 新建 `tests/investment_document_review/test_plan_handlers.py`
- [ ] 运行 `pytest tests/investment_document_review/test_plan_handlers.py -v`
- [ ] 现有测试仍通过:`pytest` 无新增失败

---

## Commit Message

```
refactor(plan-handler): extract plan generation into pluggable handlers

Separate plan generation logic from document_review_flow by introducing
ReviewPlanHandler protocol. Enables flexible strategy switching without
changing flow graph structure.

New components:
- ReviewPlanHandler: protocol defining plan generation interface
- ChunkRulePlanHandler: rule-based deterministic chunking strategy
  (moved from flow._build_chunk_review_todo_plan)
- LLMPlanHandler: LLM-driven dynamic planning
  (previously inline in generate_review_todo_plan)
- FixedAuditPlanHandler: fixed plans for testing/auditing
- DefaultAdaptivePlanHandler: adaptive strategy selection (preserves current behavior)

Flow changes:
- InvestmentDocumentReviewFlow now accepts optional plan_handler in __init__
- generate_review_todo_plan delegates to plan_handler.build_plan()
- Preserves current behavior via DefaultAdaptivePlanHandler
- Can be overridden for v1/v2/v3 version-specific strategies

Benefits:
- v1/v2/v3 can now customize plan generation without modifying flow code
- A/B testing different planning strategies without code changes
- Plan logic is testable in isolation via test_plan_handlers.py
- Clearer separation of concerns: flow routing vs plan generation

Breaking changes: none (backward compatible via default handler)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## 预期时间投入

- 抽出 plan handler 接口:20 分钟
- 重构 ChunkRulePlanHandler:15 分钟
- 实现 LLMPlanHandler:15 分钟
- 实现 FixedAuditPlanHandler:10 分钟
- 改动 flow 集成:20 分钟
- 写测试:30 分钟
- 验证:15 分钟
- **总计:1 天**

---

## 后续检查点

改完 Phase 3 后,应该:
1. ✅ `pytest tests/investment_document_review/test_plan_handlers.py -v` 全通过
2. ✅ 现有 flow 测试仍通过(DefaultAdaptivePlanHandler 保持行为不变)
3. ✅ 能用 `ChunkRulePlanHandler` 替换 flow 的 plan_handler 参数
4. ✅ 能用 `FixedAuditPlanHandler` 替换做审计测试
5. ✅ 新的测试覆盖率不下降
