from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.task_models.finance_qa import FinanceQAInput, FinanceQAResult
from investory.agent_core.task_models.investment_document_review import (
    INVESTMENT_DOCUMENT_RISK_ASSESSMENT_NAME,
    InvestmentDocumentReviewInput,
    InvestmentDocumentReviewRiskAssessmentInput,
    InvestmentDocumentReviewRiskAssessmentResult,
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


FINANCE_QA_NAME = "finance_qa"

LEARNING_MATERIAL_SUMMARY_NAME = "learning_material_summary"

INSTRUMENT_BRIEF_NAME = "instrument_brief"

INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_NAME = (
    "investment_document_review_single_pass"
)
INVESTMENT_DOCUMENT_REVIEW_PLAN_NAME = "investment_document_review_plan"
INVESTMENT_DOCUMENT_EXTRACT_NAME = "investment_document_extract"
INVESTMENT_DOCUMENT_ANALYZE_NAME = "investment_document_analyze"
INVESTMENT_DOCUMENT_SYNTHESIZE_NAME = "investment_document_synthesize"
INVESTMENT_DOCUMENT_REVIEW_REFLECTION_NAME = (
    "investment_document_review_reflection"
)


FINANCE_QA_TASK = TaskSpec(
    name=FINANCE_QA_NAME,
    prompt_name=FINANCE_QA_NAME,
    input_model=FinanceQAInput,
    output_model=FinanceQAResult,
)

LEARNING_MATERIAL_SUMMARY_TASK = TaskSpec(
    name=LEARNING_MATERIAL_SUMMARY_NAME,
    prompt_name=LEARNING_MATERIAL_SUMMARY_NAME,
    input_model=LearningMaterialSummaryInput,
    output_model=LearningMaterialSummaryResult,
)

INSTRUMENT_BRIEF_TASK = TaskSpec(
    name=INSTRUMENT_BRIEF_NAME,
    prompt_name=INSTRUMENT_BRIEF_NAME,
    input_model=InstrumentBriefInput,
    output_model=InstrumentBriefResult,
)

INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_NAME,
    prompt_name=INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_NAME,
    input_model=InvestmentDocumentReviewInput,
    output_model=InvestmentDocumentReviewResult,
)

INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_REVIEW_PLAN_NAME,
    prompt_name=INVESTMENT_DOCUMENT_REVIEW_PLAN_NAME,
    input_model=InvestmentDocumentReviewPlanInput,
    output_model=InvestmentDocumentReviewPlanResult,
)

INVESTMENT_DOCUMENT_EXTRACT_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_EXTRACT_NAME,
    prompt_name=INVESTMENT_DOCUMENT_EXTRACT_NAME,
    input_model=InvestmentDocumentReviewExtractInput,
    output_model=InvestmentDocumentReviewExtractResult,
)

INVESTMENT_DOCUMENT_ANALYZE_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_ANALYZE_NAME,
    prompt_name=INVESTMENT_DOCUMENT_ANALYZE_NAME,
    input_model=InvestmentDocumentReviewAnalyzeInput,
    output_model=InvestmentDocumentReviewAnalyzeResult,
)

INVESTMENT_DOCUMENT_SYNTHESIZE_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_SYNTHESIZE_NAME,
    prompt_name=INVESTMENT_DOCUMENT_SYNTHESIZE_NAME,
    input_model=InvestmentDocumentReviewSynthesizeInput,
    output_model=InvestmentDocumentReviewSynthesizeResult,
)

INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_RISK_ASSESSMENT_NAME,
    prompt_name=INVESTMENT_DOCUMENT_RISK_ASSESSMENT_NAME,
    input_model=InvestmentDocumentReviewRiskAssessmentInput,
    output_model=InvestmentDocumentReviewRiskAssessmentResult,
)

INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK = TaskSpec(
    name=INVESTMENT_DOCUMENT_REVIEW_REFLECTION_NAME,
    prompt_name=INVESTMENT_DOCUMENT_REVIEW_REFLECTION_NAME,
    input_model=InvestmentDocumentReviewReflectionInput,
    output_model=InvestmentDocumentReviewReflectionResult,
)

TASKS = {
    FINANCE_QA_TASK.name: FINANCE_QA_TASK,
    LEARNING_MATERIAL_SUMMARY_TASK.name: LEARNING_MATERIAL_SUMMARY_TASK,
    INSTRUMENT_BRIEF_TASK.name: INSTRUMENT_BRIEF_TASK,
    INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK.name: (
        INVESTMENT_DOCUMENT_REVIEW_SINGLE_PASS_TASK
    ),
    INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK.name: INVESTMENT_DOCUMENT_REVIEW_PLAN_TASK,
    INVESTMENT_DOCUMENT_EXTRACT_TASK.name: INVESTMENT_DOCUMENT_EXTRACT_TASK,
    INVESTMENT_DOCUMENT_ANALYZE_TASK.name: INVESTMENT_DOCUMENT_ANALYZE_TASK,
    INVESTMENT_DOCUMENT_SYNTHESIZE_TASK.name: INVESTMENT_DOCUMENT_SYNTHESIZE_TASK,
    INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name: (
        INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK
    ),
    INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK.name: (
        INVESTMENT_DOCUMENT_REVIEW_REFLECTION_TASK
    ),
}
