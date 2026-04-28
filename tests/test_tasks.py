from investory.agent_core.task_models.finance_qa import FinanceQAInput, FinanceQAResult
from investory.agent_core.task_models.learning_material_summary import (
    LearningMaterialSummaryInput,
    LearningMaterialSummaryResult,
)
from investory.agent_core.tasks import (
    FINANCE_QA_TASK,
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


def test_tasks_registry_contains_initial_tasks():
    assert TASKS == {
        "finance_qa": FINANCE_QA_TASK,
        "learning_material_summary": LEARNING_MATERIAL_SUMMARY_TASK,
    }
