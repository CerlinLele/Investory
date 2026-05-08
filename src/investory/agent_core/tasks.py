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


FINANCE_QA_TASK = TaskSpec(
    name="finance_qa",
    prompt_name="finance_qa",
    input_model=FinanceQAInput,
    output_model=FinanceQAResult,
)

LEARNING_MATERIAL_SUMMARY_TASK = TaskSpec(
    name="learning_material_summary",
    prompt_name="learning_material_summary",
    input_model=LearningMaterialSummaryInput,
    output_model=LearningMaterialSummaryResult,
)

INSTRUMENT_BRIEF_TASK = TaskSpec(
    name="instrument_brief",
    prompt_name="instrument_brief",
    input_model=InstrumentBriefInput,
    output_model=InstrumentBriefResult,
)

TASKS = {
    FINANCE_QA_TASK.name: FINANCE_QA_TASK,
    LEARNING_MATERIAL_SUMMARY_TASK.name: LEARNING_MATERIAL_SUMMARY_TASK,
    INSTRUMENT_BRIEF_TASK.name: INSTRUMENT_BRIEF_TASK,
}
