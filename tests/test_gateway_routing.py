import pytest

from investory.agent_core.tasks import (
    FINANCE_QA_TASK,
    INVESTMENT_DOCUMENT_ANALYZE_TASK,
    INVESTMENT_DOCUMENT_EXTRACT_TASK,
    INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK,
    INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK,
    INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
    INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
    INSTRUMENT_BRIEF_TASK,
    LEARNING_MATERIAL_SUMMARY_TASK,
)
from investory.gateway.routing import (
    UnknownTaskTypeError,
    resolve_task_name,
    resolve_task_spec,
)


def test_resolve_task_name_maps_qa_alias_to_finance_qa():
    assert resolve_task_name("qa") == "finance_qa"


def test_resolve_task_name_maps_summary_alias_to_learning_material_summary():
    assert resolve_task_name("summary") == "learning_material_summary"


def test_resolve_task_name_maps_brief_alias_to_instrument_brief():
    assert resolve_task_name("brief") == "instrument_brief"


def test_resolve_task_name_accepts_internal_task_name():
    assert resolve_task_name("finance_qa") == "finance_qa"


def test_resolve_task_name_strips_surrounding_whitespace():
    assert resolve_task_name("  qa  ") == "finance_qa"


def test_resolve_task_spec_returns_registered_task_spec():
    assert resolve_task_spec("qa") is FINANCE_QA_TASK
    assert (
        resolve_task_spec("learning_material_summary")
        is LEARNING_MATERIAL_SUMMARY_TASK
    )
    assert resolve_task_spec("instrument_brief") is INSTRUMENT_BRIEF_TASK
    assert (
        resolve_task_spec("investment_document_review_single_pass")
        is INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK
    )
    assert (
        resolve_task_spec("investment_document_review_plan")
        is INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK
    )
    assert (
        resolve_task_spec("investment_document_extract")
        is INVESTMENT_DOCUMENT_EXTRACT_TASK
    )
    assert (
        resolve_task_spec("investment_document_analyze")
        is INVESTMENT_DOCUMENT_ANALYZE_TASK
    )
    assert (
        resolve_task_spec("investment_document_synthesize")
        is INVESTMENT_DOCUMENT_SYNTHESIZE_TASK
    )
    assert (
        resolve_task_spec("investment_document_risk_assessment")
        is INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK
    )


def test_resolve_task_name_rejects_unknown_task_type():
    with pytest.raises(UnknownTaskTypeError) as exc_info:
        resolve_task_name("study_plan")

    assert exc_info.value.task_type == "study_plan"
    assert "Unknown task type 'study_plan'" in str(exc_info.value)
    assert "brief" in str(exc_info.value)
    assert "qa" in str(exc_info.value)
    assert "summary" in str(exc_info.value)
