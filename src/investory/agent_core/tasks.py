from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.task_models.finance_qa import FinanceQAInput, FinanceQAResult
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

TASKS = {
    FINANCE_QA_TASK.name: FINANCE_QA_TASK,
    LEARNING_MATERIAL_SUMMARY_TASK.name: LEARNING_MATERIAL_SUMMARY_TASK,
    INSTRUMENT_BRIEF_TASK.name: INSTRUMENT_BRIEF_TASK,
}
