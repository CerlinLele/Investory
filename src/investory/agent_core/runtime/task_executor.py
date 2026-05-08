from pydantic import ValidationError

from investory.agent_core.contracts.result_types import TaskResult, normalize_task_error
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.message_builder import build_messages
from investory.agent_core.runtime.request_runner import RequestRunner


class TaskExecutor:
    def __init__(self, runner: RequestRunner | None = None) -> None:
        self.runner = runner or RequestRunner()

    def build_messages(self, spec: TaskSpec, payload: dict):
        return build_messages(spec, payload)

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
