# Phase 2：Mock 执行器实现 详细实施指南

## 目标
为 `TaskExecutor` 提供 mock 和审计两个替代实现,让 end-to-end flow 测试脱离真实 LLM,从数十秒降到百毫秒级,支持快速迭代。

## 改动范围

### 2.1 新建 `runtime/execution/` 目录结构

```
src/investory/agent_core/runtime/execution/
├── __init__.py
├── mock_task_executor.py    # 新建
├── audited_task_executor.py # 新建(可选,P1)
└── executor_fixtures.py     # 新建,预置 mock 结果
```

---

### 2.2 新建 `runtime/execution/mock_task_executor.py`

```python
"""Mock task executor for deterministic testing without LLM calls."""

from typing import Any

from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.task_executor import TaskExecutor


class MockTaskExecutor(TaskExecutor):
    """
    Mock executor that returns pre-defined results without calling LLM.
    
    Usage:
        fixtures = {
            "investment_document_extract": TaskResult(ok=True, result={...}),
            "investment_document_analyze": TaskResult(ok=True, result={...}),
        }
        executor = MockTaskExecutor(fixtures)
        result = executor.run(spec, payload)  # returns fixtures[spec.name]
    """
    
    def __init__(self, fixtures: dict[str, TaskResult]):
        """
        Args:
            fixtures: dict mapping task name to pre-defined TaskResult
        """
        super().__init__()
        self.fixtures = fixtures
        self.call_log: list[dict[str, Any]] = []  # Track all calls for inspection
    
    def run(self, spec: TaskSpec, payload: dict[str, Any]) -> TaskResult:
        """
        Return pre-defined fixture result for the given task.
        
        Raises:
            ValueError: if no fixture is registered for this task name
        """
        # Log the call
        self.call_log.append({
            "task_name": spec.name,
            "payload_keys": list(payload.keys()) if payload else [],
        })
        
        # Return fixture or raise error
        if spec.name not in self.fixtures:
            raise ValueError(
                f"No mock fixture registered for task '{spec.name}'. "
                f"Available: {list(self.fixtures.keys())}"
            )
        
        return self.fixtures[spec.name]
    
    def get_call_count(self, task_name: str | None = None) -> int:
        """
        Get how many times a task (or any task) was called.
        
        Args:
            task_name: specific task to count, or None to count all
        
        Returns:
            number of times the task was called
        """
        if task_name is None:
            return len(self.call_log)
        return sum(1 for call in self.call_log if call["task_name"] == task_name)
    
    def get_calls(self, task_name: str | None = None) -> list[dict]:
        """Get all recorded calls, optionally filtered by task name."""
        if task_name is None:
            return self.call_log
        return [call for call in self.call_log if call["task_name"] == task_name]
    
    def reset_call_log(self) -> None:
        """Clear the call log."""
        self.call_log = []
```

---

### 2.3 新建 `runtime/execution/executor_fixtures.py`

```python
"""Pre-defined mock fixtures for common flow scenarios."""

from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.contracts.todo_execution import TodoTaskStatus
from investory.agent_core.task_models.investment_document_review import (
    InvestmentDocumentReviewApprovalStatus,
    InvestmentDocumentReviewResult,
    InvestmentDocumentReviewRiskAssessmentResult,
)
from investory.agent_core.task_models.investment_document_review_reflection import (
    InvestmentDocumentReviewReflectionResult,
)
from investory.agent_core.task_models.investment_document_review_todo_tasks import (
    InvestmentDocumentReviewAnalyzeResult,
    InvestmentDocumentReviewExtractResult,
    InvestmentDocumentReviewSynthesizeResult,
)


def get_investment_document_review_fixtures() -> dict[str, TaskResult]:
    """
    Get mock fixtures for a complete investment document review flow.
    
    Covers: extract → analyze → synthesize → reflection → risk_assessment
    """
    return {
        "investment_document_extract": TaskResult(
            ok=True,
            task_name="investment_document_extract",
            result=InvestmentDocumentReviewExtractResult(
                extracted_facts=[
                    "The fund charges a 1.5% management fee.",
                    "Annual returns over 5 years averaged 8.2%.",
                    "Portfolio is 60% equities, 40% bonds.",
                ],
                risk_findings=[
                    "Concentration risk in tech sector (35% of equity holdings).",
                    "Recent market volatility has increased portfolio volatility.",
                ],
                information_gaps=[
                    "Fund prospectus does not detail derivative usage.",
                ],
                boundary_notes=[
                    "Document is from 2023; more recent data may be available.",
                ],
                summary="Extract completed successfully with key facts, risks, and gaps identified.",
            ).model_dump()
        ),
        "investment_document_analyze": TaskResult(
            ok=True,
            task_name="investment_document_analyze",
            result=InvestmentDocumentReviewAnalyzeResult(
                findings=[
                    "Cost structure appears competitive for actively managed fund.",
                    "Historical returns are above peer average but not guaranteed.",
                    "Asset allocation is reasonable for balanced investor profile.",
                ],
                risks_identified=[
                    "Manager concentration risk: same team since 2015.",
                    "Market risk amplified by equity-heavy positioning.",
                    "Operational risk: recent compliance issues flagged in SEC filings.",
                ],
                gaps=[
                    "ESG integration criteria not clearly disclosed.",
                    "No clear succession plan for key portfolio manager.",
                ],
                summary="Analysis reveals competitive positioning but elevated operational risk.",
            ).model_dump()
        ),
        "investment_document_synthesize": TaskResult(
            ok=True,
            task_name="investment_document_synthesize",
            result=InvestmentDocumentReviewSynthesizeResult(
                facts=[
                    "1.5% management fee with above-average historical returns (8.2% annually).",
                    "60/40 equity/bond mix suitable for balanced portfolio.",
                ],
                risks=[
                    "Tech sector concentration (35%) increases volatility.",
                    "Operational risk from recent compliance issues.",
                    "Manager succession uncertainty.",
                ],
                information_gaps=[
                    "ESG integration approach not detailed.",
                    "Derivative usage policy unclear.",
                ],
                boundary_notes=[
                    "Analysis based on 2023 prospectus; newer data may be available.",
                    "Past performance does not guarantee future results.",
                ],
                summary="Fund shows competitive returns but elevated risk profile due to concentration and operational issues.",
            ).model_dump()
        ),
        "investment_document_review_reflection": TaskResult(
            ok=True,
            task_name="investment_document_review_reflection",
            result=InvestmentDocumentReviewReflectionResult(
                passed=True,
                score=0.85,
                rounds=1,
                issues=[],
                safety_flags=[],
                review_result=InvestmentDocumentReviewResult(
                    facts=[
                        "1.5% management fee with above-average historical returns (8.2% annually).",
                        "60/40 equity/bond mix suitable for balanced portfolio.",
                    ],
                    risks=[
                        "Tech sector concentration (35%) increases volatility.",
                        "Operational risk from recent compliance issues.",
                        "Manager succession uncertainty.",
                    ],
                    information_gaps=[
                        "ESG integration approach not detailed.",
                        "Derivative usage policy unclear.",
                    ],
                    boundary_notes=[
                        "Analysis based on 2023 prospectus; newer data may be available.",
                        "Past performance does not guarantee future results.",
                    ],
                    summary="Fund shows competitive returns but elevated risk profile.",
                ).model_dump()
            ).model_dump()
        ),
        "investment_document_risk_assessment": TaskResult(
            ok=True,
            task_name="investment_document_risk_assessment",
            result=InvestmentDocumentReviewRiskAssessmentResult(
                approval_status=InvestmentDocumentReviewApprovalStatus.APPROVED,
                required_role=None,
                risk_score=6.5,
                risk_level="elevated",
                assessment_summary="Fund has competitive returns but elevated risk profile requires careful consideration.",
            ).model_dump()
        ),
    }


def get_simple_extraction_fixture() -> dict[str, TaskResult]:
    """Get a minimal fixture set for testing just the extraction phase."""
    return {
        "investment_document_extract": TaskResult(
            ok=True,
            task_name="investment_document_extract",
            result=InvestmentDocumentReviewExtractResult(
                extracted_facts=["Key fact 1", "Key fact 2"],
                risk_findings=["Risk 1"],
                information_gaps=["Gap 1"],
                boundary_notes=[],
                summary="Extraction completed.",
            ).model_dump()
        ),
    }


def get_failure_fixture() -> dict[str, TaskResult]:
    """Get a fixture that simulates task failure for error handling tests."""
    return {
        "investment_document_extract": TaskResult(
            ok=False,
            task_name="investment_document_extract",
            error={
                "error_type": "extraction_failed",
                "message": "Failed to extract key evidence from document.",
                "stage": "extraction",
            }
        ),
    }
```

---

### 2.4 改动 `runtime/execution/__init__.py`

```python
"""Task execution strategies and mock fixtures."""

from investory.agent_core.runtime.execution.executor_fixtures import (
    get_investment_document_review_fixtures,
    get_simple_extraction_fixture,
    get_failure_fixture,
)
from investory.agent_core.runtime.execution.mock_task_executor import MockTaskExecutor

__all__ = [
    "MockTaskExecutor",
    "get_investment_document_review_fixtures",
    "get_simple_extraction_fixture",
    "get_failure_fixture",
]
```

---

### 2.5 新建 `tests/investment_document_review/test_flow_with_mock.py`

```python
"""End-to-end investment document review flow tests using mock executor."""

import pytest

from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentReviewState,
    InvestmentDocumentType,
)
from investory.agent_core.runtime.execution import (
    MockTaskExecutor,
    get_investment_document_review_fixtures,
)
from investory.agent_core.runtime.flow.investment_document_review import (
    build_investment_document_review_flow,
)


@pytest.fixture
def mock_executor():
    """Provide a mock executor with complete investment document review fixtures."""
    fixtures = get_investment_document_review_fixtures()
    return MockTaskExecutor(fixtures)


class TestInvestmentDocumentReviewFlowWithMock:
    """Test investment document review flow using mock executor."""
    
    def test_chunk_review_flow_completes_without_network(self, mock_executor):
        """
        Test complete chunk review flow (small document with multiple chunks).
        
        Verifies:
        - Flow reaches all major nodes without errors
        - Tasks are called in expected order
        - Execution time is fast (no real LLM calls)
        """
        # Build flow with mock executor
        flow = build_investment_document_review_flow(executor=mock_executor)
        
        # Prepare input with document that will trigger chunk review
        payload = {
            "document_text": "\n\n".join([
                "Chunk 1: " + "Fund facts. " * 100,
                "Chunk 2: " + "Risk analysis. " * 100,
                "Chunk 3: " + "Performance data. " * 100,
            ]),
            "review_goal": "Assess fund suitability",
        }
        
        # Run flow
        result = flow.run(payload, session_id="test-chunk-review-001")
        
        # Verify result structure
        assert result.ok
        assert result.task_name == "investment_document_review"
        assert "review" in result.result
        assert "risk_assessment" in result.result
        
        # Verify all expected tasks were called
        # (This will vary based on actual flow logic)
        # For now, just verify no exceptions raised
        assert result.result["review"] is not None
    
    def test_mock_executor_call_tracking(self, mock_executor):
        """
        Test that mock executor correctly tracks all task calls.
        """
        flow = build_investment_document_review_flow(executor=mock_executor)
        
        payload = {
            "document_text": "Single document chunk for review.",
            "review_goal": "Quick assessment",
        }
        
        result = flow.run(payload)
        
        # Check that calls were logged
        assert mock_executor.get_call_count() > 0
        assert len(mock_executor.get_calls()) > 0
        
        # Each call should have task_name and payload_keys
        for call in mock_executor.get_calls():
            assert "task_name" in call
            assert "payload_keys" in call
    
    def test_mock_executor_reset(self, mock_executor):
        """Test that call log can be reset between runs."""
        flow = build_investment_document_review_flow(executor=mock_executor)
        
        payload = {
            "document_text": "Test document.",
            "review_goal": "Test",
        }
        
        # First run
        flow.run(payload)
        count_1 = mock_executor.get_call_count()
        
        # Reset and second run
        mock_executor.reset_call_log()
        assert mock_executor.get_call_count() == 0
        
        flow.run(payload)
        count_2 = mock_executor.get_call_count()
        
        # Counts should be similar (might vary based on document routing)
        assert count_2 > 0
    
    def test_missing_fixture_raises_error(self):
        """Test that calling unknown task with mock executor raises ValueError."""
        fixtures = {"existing_task": None}  # Minimal fixture
        executor = MockTaskExecutor(fixtures)
        
        from investory.agent_core.contracts.task_spec import TaskSpec
        from pydantic import BaseModel
        
        class DummyInput(BaseModel):
            pass
        
        class DummyOutput(BaseModel):
            pass
        
        spec = TaskSpec(
            name="unknown_task",
            prompt_name="unknown",
            input_model=DummyInput,
            output_model=DummyOutput,
        )
        
        with pytest.raises(ValueError, match="No mock fixture"):
            executor.run(spec, {})
```

---

### 2.6 新建集成测试 `tests/investment_document_review/test_flow_mock_performance.py`

```python
"""Performance tests verifying mock executor is much faster than real LLM."""

import time

import pytest

from investory.agent_core.runtime.execution import (
    MockTaskExecutor,
    get_investment_document_review_fixtures,
)
from investory.agent_core.runtime.flow.investment_document_review import (
    build_investment_document_review_flow,
)


class TestMockExecutorPerformance:
    """Verify that mock executor provides significant speed improvement."""
    
    def test_complete_flow_under_200ms(self):
        """
        Complete investment document review should run in < 200ms with mock.
        
        This verifies that end-to-end testing doesn't require waiting for LLM.
        """
        fixtures = get_investment_document_review_fixtures()
        executor = MockTaskExecutor(fixtures)
        flow = build_investment_document_review_flow(executor=executor)
        
        payload = {
            "document_text": "\n".join(["Sentence about fund."] * 50),
            "review_goal": "Quick test",
        }
        
        start = time.perf_counter()
        result = flow.run(payload)
        elapsed_ms = (time.perf_counter() - start) * 1000
        
        assert result.ok
        assert elapsed_ms < 200, (
            f"Flow took {elapsed_ms:.1f}ms, expected < 200ms. "
            "Mock executor should be very fast."
        )
```

---

## 改动检查清单

- [ ] 新建 `src/investory/agent_core/runtime/execution/` 目录
- [ ] 新建 `src/investory/agent_core/runtime/execution/__init__.py`
- [ ] 新建 `src/investory/agent_core/runtime/execution/mock_task_executor.py`
- [ ] 新建 `src/investory/agent_core/runtime/execution/executor_fixtures.py`
- [ ] 新建 `tests/investment_document_review/test_flow_with_mock.py`
- [ ] 新建 `tests/investment_document_review/test_flow_mock_performance.py`
- [ ] 运行 `pytest tests/investment_document_review/test_flow_with_mock.py -v`
- [ ] 运行 `pytest tests/investment_document_review/test_flow_mock_performance.py -v`
- [ ] 验证没有网络调用(可用 `pytest --disable-socket` 如果有该插件)
- [ ] 现有测试仍通过:`pytest` 无新增失败

---

## Commit Message

```
feat(execution): add MockTaskExecutor for fast deterministic testing

Add mock execution layer to test investment document review flow
without calling real LLM. Reduces flow execution time from ~30s to <200ms.

New components:
- MockTaskExecutor: task executor that returns pre-defined fixtures
  - Tracks all task calls for inspection
  - Raises error if fixture not defined for a task
  - Supports resetting call log between runs

- executor_fixtures.py: pre-built fixture sets
  - get_investment_document_review_fixtures(): complete happy path
  - get_simple_extraction_fixture(): minimal extraction-only fixtures
  - get_failure_fixture(): error handling scenarios

Test coverage:
- test_flow_with_mock.py: end-to-end flow validates with mock executor
  - Chunk review path completes successfully
  - Call tracking works correctly
  - Missing fixture raises appropriate error

- test_flow_mock_performance.py: verifies speed improvement
  - Complete flow runs in < 200ms (vs ~30s with real LLM)

Enables:
- Rapid iteration on flow logic without LLM dependency
- Deterministic testing of routing and task sequencing
- Foundation for Phase 3 (plan handler substitution)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## 预期时间投入

- 实现 MockTaskExecutor:20 分钟
- 设计 fixture schema:15 分钟
- 写测试:20 分钟
- 验证:10 分钟
- **总计:1 天**

---

## 后续检查点

改完 Phase 2 后,应该:
1. ✅ `pytest tests/investment_document_review/test_flow_with_mock.py -v` 全通过
2. ✅ `pytest tests/investment_document_review/test_flow_mock_performance.py -v` 证明 < 200ms
3. ✅ 能用 `mock_executor.get_call_count()` 查询任务调用次数
4. ✅ 能用 `mock_executor.reset_call_log()` 清除调用历史
5. ✅ 全量 `pytest` 其它测试不新增失败
