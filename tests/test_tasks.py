from investory.agent_core.task_models.finance_qa import FinanceQAInput, FinanceQAResult
from investory.agent_core.task_models.investment_document_review import (
    InvestmentDocumentReviewRiskAssessmentInput,
    InvestmentDocumentReviewRiskAssessmentResult,
    InvestmentDocumentReviewInput,
    InvestmentDocumentReviewResult,
)
from investory.agent_core.task_models.investment_document_review_plan import (
    InvestmentDocumentReviewPlanInput,
    InvestmentDocumentReviewPlanResult,
)
from investory.agent_core.task_models.investment_document_review_reflection import (
    InvestmentDocumentReviewReflectionInput,
    InvestmentDocumentReviewReflectionResult,
)
from investory.agent_core.task_models.investment_document_review_todo_tasks import (
    InvestmentDocumentReviewAnalyzeInput,
    InvestmentDocumentReviewAnalyzeResult,
    InvestmentDocumentReviewExtractInput,
    InvestmentDocumentReviewExtractResult,
    InvestmentDocumentReviewSynthesizeInput,
    InvestmentDocumentReviewSynthesizeResult,
)
from investory.agent_core.task_models.instrument_brief import (
    InstrumentBriefInput,
    InstrumentBriefResult,
)
from investory.agent_core.task_models.learning_material_summary import (
    LearningMaterialSummaryInput,
    LearningMaterialSummaryResult,
)
from investory.agent_core.tasks import (
    FINANCE_QA_TASK,
    INVESTMENT_DOCUMENT_ANALYZE_TASK,
    INVESTMENT_DOCUMENT_EXTRACT_TASK,
    INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK,
    INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK,
    INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK,
    INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
    INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
    INSTRUMENT_BRIEF_TASK,
    LEARNING_MATERIAL_SUMMARY_TASK,
    TASKS,
)


def test_finance_qa_task_spec_registers_models_and_prompt():
    assert FINANCE_QA_TASK.name == "finance_qa"
    assert FINANCE_QA_TASK.prompt_name == "finance_qa"
    assert FINANCE_QA_TASK.input_model is FinanceQAInput
    assert FINANCE_QA_TASK.output_model is FinanceQAResult


def test_learning_material_summary_task_spec_registers_models_and_prompt():
    assert LEARNING_MATERIAL_SUMMARY_TASK.name == "learning_material_summary"
    assert LEARNING_MATERIAL_SUMMARY_TASK.prompt_name == "learning_material_summary"
    assert LEARNING_MATERIAL_SUMMARY_TASK.input_model is LearningMaterialSummaryInput
    assert LEARNING_MATERIAL_SUMMARY_TASK.output_model is LearningMaterialSummaryResult


def test_instrument_brief_task_spec_registers_models_and_prompt():
    assert INSTRUMENT_BRIEF_TASK.name == "instrument_brief"
    assert INSTRUMENT_BRIEF_TASK.prompt_name == "instrument_brief"
    assert INSTRUMENT_BRIEF_TASK.input_model is InstrumentBriefInput
    assert INSTRUMENT_BRIEF_TASK.output_model is InstrumentBriefResult


def test_investment_document_review_single_pass_task_spec_registers_models_and_prompt():
    assert (
        INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name
        == "investment_document_review_single_pass"
    )
    assert (
        INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.prompt_name
        == "investment_document_review_single_pass"
    )
    assert (
        INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.input_model
        is InvestmentDocumentReviewInput
    )
    assert (
        INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.output_model
        is InvestmentDocumentReviewResult
    )


def test_investment_document_review_plan_task_spec_registers_models_and_prompt():
    assert (
        INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name
        == "investment_document_review_plan"
    )
    assert (
        INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.prompt_name
        == "investment_document_review_plan"
    )
    assert INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.input_model is (
        InvestmentDocumentReviewPlanInput
    )
    assert INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.output_model is (
        InvestmentDocumentReviewPlanResult
    )


def test_investment_document_extract_task_spec_registers_models_and_prompt():
    assert INVESTMENT_DOCUMENT_EXTRACT_TASK.name == "investment_document_extract"
    assert (
        INVESTMENT_DOCUMENT_EXTRACT_TASK.prompt_name
        == "investment_document_extract"
    )
    assert INVESTMENT_DOCUMENT_EXTRACT_TASK.input_model is (
        InvestmentDocumentReviewExtractInput
    )
    assert INVESTMENT_DOCUMENT_EXTRACT_TASK.output_model is (
        InvestmentDocumentReviewExtractResult
    )


def test_investment_document_analyze_task_spec_registers_models_and_prompt():
    assert INVESTMENT_DOCUMENT_ANALYZE_TASK.name == "investment_document_analyze"
    assert (
        INVESTMENT_DOCUMENT_ANALYZE_TASK.prompt_name
        == "investment_document_analyze"
    )
    assert INVESTMENT_DOCUMENT_ANALYZE_TASK.input_model is (
        InvestmentDocumentReviewAnalyzeInput
    )
    assert INVESTMENT_DOCUMENT_ANALYZE_TASK.output_model is (
        InvestmentDocumentReviewAnalyzeResult
    )


def test_investment_document_synthesize_task_spec_registers_models_and_prompt():
    assert (
        INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name
        == "investment_document_synthesize"
    )
    assert (
        INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.prompt_name
        == "investment_document_synthesize"
    )
    assert INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.input_model is (
        InvestmentDocumentReviewSynthesizeInput
    )
    assert INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.output_model is (
        InvestmentDocumentReviewSynthesizeResult
    )


def test_investment_document_risk_assessment_task_spec_registers_models_and_prompt():
    assert (
        INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name
        == "investment_document_risk_assessment"
    )
    assert (
        INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.prompt_name
        == "investment_document_risk_assessment"
    )
    assert INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.input_model is (
        InvestmentDocumentReviewRiskAssessmentInput
    )
    assert INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.output_model is (
        InvestmentDocumentReviewRiskAssessmentResult
    )


def test_investment_document_review_reflection_task_spec_registers_models_and_prompt():
    assert (
        INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name
        == "investment_document_review_reflection"
    )
    assert (
        INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.prompt_name
        == "investment_document_review_reflection"
    )
    assert INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.input_model is (
        InvestmentDocumentReviewReflectionInput
    )
    assert INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.output_model is (
        InvestmentDocumentReviewReflectionResult
    )


def test_tasks_registry_contains_initial_and_investment_document_review_tasks():
    assert TASKS == {
        "finance_qa": FINANCE_QA_TASK,
        "learning_material_summary": LEARNING_MATERIAL_SUMMARY_TASK,
        "instrument_brief": INSTRUMENT_BRIEF_TASK,
        "investment_document_review_single_pass": (
            INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK
        ),
        "investment_document_review_plan": INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
        "investment_document_extract": INVESTMENT_DOCUMENT_EXTRACT_TASK,
        "investment_document_analyze": INVESTMENT_DOCUMENT_ANALYZE_TASK,
        "investment_document_synthesize": INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
        "investment_document_risk_assessment": (
            INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK
        ),
        "investment_document_review_reflection": (
            INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK
        ),
    }
