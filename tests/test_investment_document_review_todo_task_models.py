from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentType,
)
from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
    TodoFailurePolicy,
    TodoTaskKind,
    TodoTaskResult,
    TodoTaskStatus,
)
from investory.agent_core.task_models.investment_document_review_plan import (
    InvestmentDocumentReviewPlanInput,
    InvestmentDocumentReviewPlanResult,
)
from investory.agent_core.task_models.investment_document_review_todo_tasks import (
    InvestmentDocumentReviewAnalyzeInput,
    InvestmentDocumentReviewAnalyzeResult,
    InvestmentDocumentReviewExtractInput,
    InvestmentDocumentReviewExtractResult,
    InvestmentDocumentReviewSynthesizeInput,
    InvestmentDocumentReviewSynthesizeResult,
)


def _sample_plan() -> TodoExecutionPlan:
    return TodoExecutionPlan.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts from the document.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Fees are listed with source citations."],
                }
            ],
            "summary": "Review ETF fees before analysis.",
            "failure_policy": TodoFailurePolicy.RETRY_THEN_FAIL,
        }
    )


def _sample_result() -> TodoTaskResult:
    return TodoTaskResult.model_validate(
        {
            "id": "extract_fees",
            "status": TodoTaskStatus.SUCCEEDED,
            "result": {"extracted_facts": ["The management fee is 0.10%."]},
        }
    )


def _sample_review_summary() -> dict:
    return {
        "plan_summary": "Review ETF fees before analysis.",
        "planned_task_count": 1,
        "completed_task_count": 1,
        "succeeded_task_ids": ["extract_fees"],
        "failed_task_ids": [],
        "skipped_task_ids": [],
        "extracted_facts": ["The management fee is 0.10%."],
        "risk_findings": [],
        "information_gaps": [],
        "boundary_notes": [],
        "task_summaries": [
            {
                "task_id": "extract_fees",
                "task_title": "Extract fees",
                "task_kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                "status": TodoTaskStatus.SUCCEEDED,
                "summary": None,
            }
        ],
    }


def test_plan_input_accepts_existing_review_fields() -> None:
    payload = InvestmentDocumentReviewPlanInput.model_validate(
        {
            "document_text": "ETF factsheet with fee and index details.",
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "extract_focus": ["fees", "index"],
            "analyze_focus": ["risk disclosures"],
            "review_goal": "Review fee clarity",
        }
    )

    assert payload.document_type is InvestmentDocumentType.ETF_FACTSHEET
    assert payload.extract_focus == ["fees", "index"]


def test_plan_result_reuses_todo_execution_plan() -> None:
    plan = InvestmentDocumentReviewPlanResult.model_validate(_sample_plan())

    assert isinstance(plan, TodoExecutionPlan)
    assert plan.tasks[0].kind is TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT


def test_extract_models_validate_task_payload_and_result() -> None:
    payload = InvestmentDocumentReviewExtractInput.model_validate(
        {
            "task_id": "extract_fees",
            "task_title": "Extract fees",
            "task_description": "Extract fee facts from the document.",
            "completion_criteria": ["Fees are listed with source citations."],
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "review_goal": None,
            "document_text": "The management fee is 0.10%.",
            "extract_focus": ["fees"],
        }
    )
    result = InvestmentDocumentReviewExtractResult.model_validate(
        {
            "extracted_facts": ["The management fee is 0.10%."],
            "source_citations": ["Fee table"],
            "information_gaps": [],
            "boundary_notes": ["No investment recommendation was made."],
            "summary": "Fee facts were extracted.",
        }
    )

    assert payload.task_id == "extract_fees"
    assert result.extracted_facts == ["The management fee is 0.10%."]


def test_analyze_models_accept_dependency_results() -> None:
    payload = InvestmentDocumentReviewAnalyzeInput.model_validate(
        {
            "task_id": "analyze_fee_risk",
            "task_title": "Analyze fee risk",
            "task_description": "Analyze fee disclosure clarity.",
            "completion_criteria": ["Findings are supported by extract results."],
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "document_text": "The management fee is 0.10%.",
            "analyze_focus": ["fee disclosure"],
            "dependency_results": [_sample_result()],
        }
    )
    result = InvestmentDocumentReviewAnalyzeResult.model_validate(
        {
            "risk_findings": ["Fee disclosure appears explicit."],
            "supporting_evidence": ["extract_fees"],
            "information_gaps": [],
            "boundary_notes": ["This is not a fee comparison recommendation."],
            "summary": "Fee disclosure was analyzable from extracted facts.",
        }
    )

    assert payload.dependency_results[0].id == "extract_fees"
    assert result.supporting_evidence == ["extract_fees"]


def test_synthesize_input_and_result_models_validate_review_output() -> None:
    payload = InvestmentDocumentReviewSynthesizeInput.model_validate(
        {
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "route_reason": "The document describes ETF fees and index tracking.",
            "route_confidence": 0.91,
            "review_goal": "Review fee clarity",
            "todo_plan": _sample_plan(),
            "todo_results": [_sample_result()],
            "review_summary": _sample_review_summary(),
        }
    )
    result = InvestmentDocumentReviewSynthesizeResult.model_validate(
        {
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "extracted_facts": ["The management fee is 0.10%."],
            "risk_findings": ["Fee disclosure appears explicit."],
            "information_gaps": [],
            "boundary_notes": ["The review does not recommend buying or selling."],
            "summary": "The ETF factsheet includes clear fee disclosure.",
        }
    )

    assert payload.route_confidence == 0.91
    assert result.learning_next_steps is None
