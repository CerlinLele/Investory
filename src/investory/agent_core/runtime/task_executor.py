import json

from langchain_core.prompts import ChatPromptTemplate
from pydantic import ValidationError

from investory.agent_core.contracts.result_types import TaskResult, normalize_task_error
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.prompt_loader import load_prompt_text
from investory.agent_core.runtime.request_runner import RequestRunner


class TaskExecutor:
    def __init__(self, runner: RequestRunner | None = None) -> None:
        self.runner = runner or RequestRunner()

    def build_messages(self, spec: TaskSpec, payload: dict):
        system_prompt = load_prompt_text("base", "system.md")
        common_rules = load_prompt_text("base", "common_rules.md")
        input_data_block = load_prompt_text("base", "input_data_block.md")
        task_prompt = load_prompt_text("tasks", f"{spec.prompt_name}.md")
        input_json = json.dumps(payload, ensure_ascii=False, indent=2)

        prompt = ChatPromptTemplate(
            [
                ("system", system_prompt),
                ("human", task_prompt),
            ]
        )

        return prompt.invoke(
            {
                "common_rules": common_rules,
                "input_data_block": input_data_block.format(input_json=input_json),
            }
        ).messages

    def run(self, spec: TaskSpec, payload: dict) -> TaskResult:
        try:
            validated_input = spec.input_model.model_validate(payload)
        except ValidationError as exc:
            return TaskResult(
                ok=False,
                task_name=spec.name,
                error=normalize_task_error(exc, stage="input_validation"),
            )

        try:
            messages = self.build_messages(spec, validated_input.model_dump())
        except Exception as exc:
            return TaskResult(
                ok=False,
                task_name=spec.name,
                error=normalize_task_error(exc, stage="prompt_build"),
            )

        try:
            parsed = self.runner.run(messages, spec.output_model)
        except ValidationError as exc:
            return TaskResult(
                ok=False,
                task_name=spec.name,
                error=normalize_task_error(exc, stage="output_validation"),
            )
        except Exception as exc:
            return TaskResult(
                ok=False,
                task_name=spec.name,
                error=normalize_task_error(exc, stage="model_call"),
            )

        return TaskResult(
            ok=True,
            task_name=spec.name,
            result=parsed.model_dump(),
        )
