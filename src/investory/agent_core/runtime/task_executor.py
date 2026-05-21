from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.request_runner import (
    ModelCallError,
    RequestRunner,
    StructuredOutputError,
)
from investory.agent_core.runtime.minimal_flow import MinimalTaskFlow


class TaskExecutor:
    def __init__(self, runner: RequestRunner | None = None) -> None:
        self.runner = runner or RequestRunner()
        self.flow = MinimalTaskFlow(runner=self.runner)

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
        except StructuredOutputError as exc:
            return TaskResult(
                ok=False,
                task_name=spec.name,
                error=normalize_task_error(
                    exc.original,
                    stage="output_validation",
                    retry_count=exc.retry_count,
                ),
            )
        except ValidationError as exc:
            return TaskResult(
                ok=False,
                task_name=spec.name,
                error=normalize_task_error(exc, stage="output_validation"),
            )
        except ModelCallError as exc:
            return TaskResult(
                ok=False,
                task_name=spec.name,
                error=normalize_task_error(
                    exc.original,
                    stage="model_call",
                    retry_count=exc.retry_count,
                ),
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
