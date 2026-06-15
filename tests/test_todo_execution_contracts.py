from investory.agent_core.contracts.todo_execution import (
    INVESTMENT_DOCUMENT_ANALYZE_TASK_KIND,
    INVESTMENT_DOCUMENT_EXTRACT_TASK_KIND,
    INVESTMENT_DOCUMENT_SYNTHESIZE_TASK_KIND,
    TodoTaskKind,
)


def test_investment_document_review_task_kinds_use_stable_values() -> None:
    assert (
        TodoTaskKind.INVESTMENT_DOCUMENT_EXTRACT
        == INVESTMENT_DOCUMENT_EXTRACT_TASK_KIND
    )
    assert (
        TodoTaskKind.INVESTMENT_DOCUMENT_ANALYZE
        == INVESTMENT_DOCUMENT_ANALYZE_TASK_KIND
    )
    assert (
        TodoTaskKind.INVESTMENT_DOCUMENT_SYNTHESIZE
        == INVESTMENT_DOCUMENT_SYNTHESIZE_TASK_KIND
    )

    assert INVESTMENT_DOCUMENT_EXTRACT_TASK_KIND == "investment_document_extract"
    assert INVESTMENT_DOCUMENT_ANALYZE_TASK_KIND == "investment_document_analyze"
    assert (
        INVESTMENT_DOCUMENT_SYNTHESIZE_TASK_KIND
        == "investment_document_synthesize"
    )
