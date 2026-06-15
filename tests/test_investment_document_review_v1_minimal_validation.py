from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentType,
)
from investory.agent_core.contracts.todo_execution import (
    TodoExecutionPlan,
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


def test_minimal_investment_document_review_v1_models_validate() -> None:
    plan_input = InvestmentDocumentReviewPlanInput.model_validate(
        {
            "document_text": "ETF factsheet states the management fee is 0.10%.",
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "extract_focus": ["fees"],
            "analyze_focus": ["fee disclosure clarity"],
            "review_goal": "Review fee disclosure",
        }
    )
    plan = InvestmentDocumentReviewPlanResult.model_validate(
        {
            "tasks": [
                {
                    "id": "extract_fees",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                    "title": "Extract fees",
                    "description": "Extract fee facts from the factsheet.",
                    "payload": {"extract_focus": ["fees"]},
                    "depends_on": [],
                    "completion_criteria": ["Fee facts include source support."],
                },
                {
                    "id": "analyze_fee_disclosure",
                    "kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                    "title": "Analyze fee disclosure",
                    "description": "Assess fee disclosure clarity from extracted facts.",
                    "payload": {"analyze_focus": ["fee disclosure clarity"]},
                    "depends_on": ["extract_fees"],
                    "completion_criteria": ["Findings cite upstream facts."],
                },
            ],
            "summary": "Extract fee facts before assessing fee disclosure clarity.",
        }
    )

    extract_input = InvestmentDocumentReviewExtractInput.model_validate(
        {
            "task_id": "extract_fees",
            "task_title": "Extract fees",
            "task_description": "Extract fee facts from the factsheet.",
            "completion_criteria": ["Fee facts include source support."],
            "document_type": plan_input.document_type,
            "review_goal": plan_input.review_goal,
            "document_text": plan_input.document_text,
            "extract_focus": ["fees"],
        }
    )
    extract_result_payload = InvestmentDocumentReviewExtractResult.model_validate(
        {
            "extracted_facts": ["The management fee is 0.10%."],
            "source_citations": ["Factsheet fee section"],
            "information_gaps": [],
            "boundary_notes": ["No investment recommendation was made."],
            "summary": "Fee disclosure was extracted.",
        }
    )
    extract_task_result = TodoTaskResult.model_validate(
        {
            "id": extract_input.task_id,
            "status": TodoTaskStatus.SUCCEEDED,
            "result": extract_result_payload.model_dump(),
        }
    )

    analyze_input = InvestmentDocumentReviewAnalyzeInput.model_validate(
        {
            "task_id": "analyze_fee_disclosure",
            "task_title": "Analyze fee disclosure",
            "task_description": "Assess fee disclosure clarity from extracted facts.",
            "completion_criteria": ["Findings cite upstream facts."],
            "document_type": plan_input.document_type,
            "review_goal": plan_input.review_goal,
            "document_text": plan_input.document_text,
            "analyze_focus": ["fee disclosure clarity"],
            "dependency_results": [extract_task_result],
        }
    )
    analyze_result_payload = InvestmentDocumentReviewAnalyzeResult.model_validate(
        {
            "risk_findings": ["Fee disclosure is explicit in the provided text."],
            "supporting_evidence": ["extract_fees"],
            "information_gaps": [],
            "boundary_notes": ["No fee comparison or suitability advice was made."],
            "summary": "Fee disclosure clarity was assessed from extracted facts.",
        }
    )
    analyze_task_result = TodoTaskResult.model_validate(
        {
            "id": analyze_input.task_id,
            "status": TodoTaskStatus.SUCCEEDED,
            "result": analyze_result_payload.model_dump(),
        }
    )

    synthesize_input = InvestmentDocumentReviewSynthesizeInput.model_validate(
        {
            "document_type": plan_input.document_type,
            "route_reason": "The text is an ETF factsheet excerpt.",
            "route_confidence": 0.91,
            "review_goal": plan_input.review_goal,
            "todo_plan": plan,
            "todo_results": [extract_task_result, analyze_task_result],
            "review_summary": {
                "plan_summary": "Extract fee facts before assessing fee disclosure clarity.",
                "planned_task_count": 2,
                "completed_task_count": 2,
                "succeeded_task_ids": ["extract_fees", "analyze_fee_disclosure"],
                "failed_task_ids": [],
                "skipped_task_ids": [],
                "extracted_facts": ["The management fee is 0.10%."],
                "risk_findings": [
                    "Fee disclosure is explicit in the provided text."
                ],
                "information_gaps": [],
                "boundary_notes": [
                    "No investment recommendation was made.",
                    "No fee comparison or suitability advice was made.",
                ],
                "task_summaries": [
                    {
                        "task_id": "extract_fees",
                        "task_title": "Extract fees",
                        "task_kind": TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT,
                        "status": TodoTaskStatus.SUCCEEDED,
                        "summary": "Fee disclosure was extracted.",
                    },
                    {
                        "task_id": "analyze_fee_disclosure",
                        "task_title": "Analyze fee disclosure",
                        "task_kind": TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE,
                        "status": TodoTaskStatus.SUCCEEDED,
                        "summary": (
                            "Fee disclosure clarity was assessed from extracted facts."
                        ),
                    },
                ],
            },
        }
    )
    final_result = InvestmentDocumentReviewSynthesizeResult.model_validate(
        {
            "document_type": synthesize_input.document_type,
            "extracted_facts": ["The management fee is 0.10%."],
            "risk_findings": ["Fee disclosure is explicit in the provided text."],
            "information_gaps": [],
            "boundary_notes": ["This review does not recommend buying or selling."],
            "summary": "The factsheet excerpt gives a clear fee disclosure.",
        }
    )

    assert isinstance(plan, TodoExecutionPlan)
    assert plan.tasks[1].depends_on == ["extract_fees"]
    assert analyze_input.dependency_results == [extract_task_result]
    assert synthesize_input.todo_results == [extract_task_result, analyze_task_result]
    assert final_result.document_type is InvestmentDocumentType.ETF_FACTSHEET
