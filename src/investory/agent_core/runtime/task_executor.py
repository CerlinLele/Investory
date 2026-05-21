from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.minimal_flow import MinimalTaskFlow
from investory.agent_core.runtime.request_runner import RequestRunner


class TaskExecutor:
    def __init__(self, runner: RequestRunner | None = None) -> None:
        self.flow = MinimalTaskFlow(runner=runner)

    def run(self, spec: TaskSpec, payload: dict) -> TaskResult:
        return self.flow.run(spec, payload)
