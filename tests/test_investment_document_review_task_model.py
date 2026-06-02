from investory.agent_core.contracts.investment_document_review_state import (
    InvestmentDocumentType,
)
from investory.agent_core.runtime.message_builder import build_prompt_messages
from investory.agent_core.task_models.investment_document_review import (
    InvestmentDocumentReviewInput,
    InvestmentDocumentReviewResult,
)


def test_investment_document_review_input_accepts_expected_payload() -> None:
    payload = InvestmentDocumentReviewInput.model_validate(
        {
            "document_text": "ETF factsheet covering fees and tracking index.",
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "extract_focus": ["fees", "index"],
            "analyze_focus": ["risk disclosures"],
            "review_goal": "Check fees and risks",
        }
    )

    assert payload.document_type is InvestmentDocumentType.ETF_FACTSHEET
    assert payload.review_goal == "Check fees and risks"


def test_investment_document_review_result_allows_optional_learning_steps() -> None:
    result = InvestmentDocumentReviewResult.model_validate(
        {
            "document_type": InvestmentDocumentType.FUND_PROSPECTUS,
            "extracted_facts": ["The fund may suspend redemptions in rare cases."],
            "risk_findings": ["Liquidity risk is disclosed."],
            "information_gaps": ["No fee example is provided."],
            "boundary_notes": ["The review does not assess current market conditions."],
            "summary": "The prospectus outlines constraints and risks but leaves fee examples unclear.",
        }
    )

    assert result.learning_next_steps is None


def test_investment_document_review_prompt_builds_messages() -> None:
    messages = build_prompt_messages(
        "tasks",
        "investment_document_review_single_pass.md",
        {
            "document_text": "This ETF tracks a broad market index.",
            "document_type": InvestmentDocumentType.ETF_FACTSHEET,
            "extract_focus": ["underlying index"],
            "analyze_focus": ["risk disclosures"],
            "review_goal": "Summarize major risks",
        },
    )

    assert len(messages) == 2
    assert "document_text" in messages[1].content
    assert "extract_focus" in messages[1].content
    assert "Summarize major risks" in messages[1].content
