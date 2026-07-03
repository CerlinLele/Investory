from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentType,
)
from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoTaskKind,
    TodoTaskResult,
    TodoTaskStatus,
)
from investory.agent_core.runtime.message_builder import build_messages
from investory.agent_core.tasks import (
    INVESTMENT_DOCUMENT_ANALYZE_TASK,
    INVESTMENT_DOCUMENT_EXTRACT_TASK,
    INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK,
    INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
    INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
)


def _sample_plan() -> TodoExecutionPlan:
    return TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts.",
                    "payload": {"extract_focus": ["fees"]},
                    "completion_criteria": ["Fees are cited."],
                }
            ],
            "summary": "Extract fees before analysis.",
        }
    )


def _sample_result() -> TodoTaskResult:
    return TodoTaskResult.model_validate(
        {
            "id": "extract_fees",
            "status": TodoTaskStatus.SUCCEEDED,
            "result": {"extracted_facts": ["The fee is 0.10%."]},
        }
    )


def test_investment_document_review_plan_prompt_builds_messages() -> None:
    messages = build_messages(
        INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
        {
            "document_text": "ETF factsheet with fees and risks.",
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "extract_focus": ["fees"],
            "analyze_focus": ["risk disclosure"],
            "review_goal": "Review fees",
        },
    )

    assert len(messages) == 2
    assert "structured To-Do plan" in messages[1].content
    assert "investment_document_extract" in messages[1].content
    assert "Extract tasks must use `depends_on=[]`" in messages[1].content
    assert "must not invent raw facts" in messages[1].content
    assert "lowercase snake_case" in messages[1].content
    assert "must reference an existing task id exactly" in messages[1].content
    assert "specific and checkable" in messages[1].content
    assert "Review fees" in messages[1].content


def test_investment_document_extract_prompt_builds_messages() -> None:
    messages = build_messages(
        INVESTMENT_DOCUMENT_EXTRACT_TASK,
        {
            "task_id": "extract_fees",
            "task_title": "Extract fees",
            "task_description": "Extract fee facts.",
            "completion_criteria": ["Fees are cited."],
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "document_text": "The fee is 0.10%.",
            "extract_focus": ["fees"],
        },
    )

    assert len(messages) == 2
    assert "Extract facts only" in messages[1].content
    assert "source citations" in messages[1].content
    assert "extract_fees" in messages[1].content


def test_investment_document_extract_prompt_includes_visual_only_redundancy_rule() -> None:
    messages = build_messages(
        INVESTMENT_DOCUMENT_EXTRACT_TASK,
        {
            "task_id": "extract_performance",
            "task_title": "Extract performance metrics",
            "task_description": "Extract performance chart data.",
            "completion_criteria": ["Performance data is cited."],
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "document_text": "The $10,000 growth chart shows annual returns.",
            "extract_focus": ["performance"],
        },
    )

    assert len(messages) == 2
    assert "visual-only representation" in messages[1].content


def test_investment_document_analyze_prompt_builds_messages() -> None:
    messages = build_messages(
        INVESTMENT_DOCUMENT_ANALYZE_TASK,
        {
            "task_id": "analyze_fee_disclosure",
            "task_title": "Analyze fee disclosure",
            "task_description": "Analyze fee disclosure quality.",
            "completion_criteria": ["Findings use extracted facts."],
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "document_text": "The fee is 0.10%.",
            "analyze_focus": ["fee disclosure"],
            "dependency_results": [_sample_result().model_dump()],
        },
    )

    assert len(messages) == 2
    assert "upstream extraction results" in messages[1].content
    assert "dependency_results" in messages[1].content
    assert "analyze_fee_disclosure" in messages[1].content


def test_investment_document_synthesize_prompt_builds_messages() -> None:
    messages = build_messages(
        INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
        {
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "route_reason": "The document describes ETF fees.",
            "route_confidence": 0.91,
            "review_goal": "Review fees",
            "todo_plan": _sample_plan().model_dump(),
            "todo_results": [_sample_result().model_dump()],
        },
    )

    assert len(messages) == 2
    assert "final review result" in messages[1].content
    assert "failed or were skipped" in messages[1].content
    assert "route_confidence" in messages[1].content


def test_investment_document_risk_assessment_prompt_builds_messages() -> None:
    messages = build_messages(
        INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK,
        {
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "route_confidence": 0.91,
            "risk_findings": ["Fee disclosure is incomplete."],
            "information_gaps": ["No benchmark methodology is provided."],
            "boundary_notes": [
                "The review does not assess live market conditions."
            ],
            "task_status_summary": [
                "analyze-fees: succeeded",
                "analyze-benchmark: skipped",
            ],
        },
    )

    assert len(messages) == 2
    assert "structured review evidence" in messages[1].content
    assert "do not ask for or rely on the full document text" in messages[1].content
    assert "high` risk must include one or more `critical_issues`" in messages[
        1
    ].content
    assert "auto_proceed=false" in messages[1].content
