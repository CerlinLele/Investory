from investory.agent_core.contracts.react_loop import (
    ReactActionType,
    ReactBudget,
    ReactLoopState,
    ReactLoopStatus,
    ReactToolCallRecord,
)
from investory.agent_core.runtime.react_core.loop_engine import (
    LoopEngine,
    PlannedStep,
    StepExecutionResult,
    StepValidationResult,
)


class SequencePlanner:
    def __init__(self, actions: list[ReactActionType]) -> None:
        self._actions = actions
        self._index = 0

    def plan_next_step(self, state: ReactLoopState) -> PlannedStep:
        action = self._actions[min(self._index, len(self._actions) - 1)]
        self._index += 1
        return PlannedStep(action_type=action, summary=f"plan {self._index}")


class AllowAllPolicy:
    def validate_step(
        self,
        state: ReactLoopState,
        planned_step: PlannedStep,
    ) -> StepValidationResult:
        return StepValidationResult(ok=True)


class RejectPolicy:
    def validate_step(
        self,
        state: ReactLoopState,
        planned_step: PlannedStep,
    ) -> StepValidationResult:
        return StepValidationResult(
            ok=False,
            retryable=False,
            error_message="validation failed",
        )


class FixedExecutor:
    def __init__(self, result_factory):
        self._result_factory = result_factory

    def execute_step(
        self,
        state: ReactLoopState,
        planned_step: PlannedStep,
    ) -> StepExecutionResult:
        return self._result_factory(state, planned_step)


def test_loop_engine_stops_on_finalize() -> None:
    engine = LoopEngine(
        planner=SequencePlanner([ReactActionType.FINALIZE]),
        policy=AllowAllPolicy(),
        executor=FixedExecutor(lambda *_: StepExecutionResult(finalize=True)),
    )
    state = ReactLoopState(budget=ReactBudget(max_steps=5, max_tool_calls=5))

    result = engine.run(state)

    assert result.status == ReactLoopStatus.FINALIZED
    assert result.step_count == 1


def test_loop_engine_stops_when_waiting_for_user() -> None:
    engine = LoopEngine(
        planner=SequencePlanner([ReactActionType.WAIT_FOR_USER]),
        policy=AllowAllPolicy(),
        executor=FixedExecutor(lambda *_: StepExecutionResult(waiting_for_user=True)),
    )
    state = ReactLoopState(budget=ReactBudget(max_steps=5, max_tool_calls=5))

    result = engine.run(state)

    assert result.status == ReactLoopStatus.WAITING_FOR_USER
    assert result.requires_user_input is True
    assert result.step_count == 1


def test_loop_engine_stops_when_max_steps_reached() -> None:
    engine = LoopEngine(
        planner=SequencePlanner([ReactActionType.EXECUTE]),
        policy=AllowAllPolicy(),
        executor=FixedExecutor(lambda *_: StepExecutionResult()),
    )
    state = ReactLoopState(budget=ReactBudget(max_steps=2, max_tool_calls=10))

    result = engine.run(state)

    assert result.status == ReactLoopStatus.STOPPED
    assert result.step_count == 2


def test_loop_engine_stops_when_max_tool_calls_reached() -> None:
    def _execute(state: ReactLoopState, _planned_step: PlannedStep) -> StepExecutionResult:
        return StepExecutionResult(
            tool_call_record=ReactToolCallRecord(
                step_index=state.step_count,
                tool_name="search",
            )
        )

    engine = LoopEngine(
        planner=SequencePlanner([ReactActionType.CALL_TOOL]),
        policy=AllowAllPolicy(),
        executor=FixedExecutor(_execute),
    )
    state = ReactLoopState(budget=ReactBudget(max_steps=10, max_tool_calls=1))

    result = engine.run(state)

    assert result.status == ReactLoopStatus.STOPPED
    assert result.tool_call_count == 1
    assert len(result.tool_call_records) == 1


def test_loop_engine_stops_on_repeated_action_limit() -> None:
    engine = LoopEngine(
        planner=SequencePlanner([ReactActionType.EXECUTE]),
        policy=AllowAllPolicy(),
        executor=FixedExecutor(lambda *_: StepExecutionResult()),
        max_repeated_actions=2,
    )
    state = ReactLoopState(budget=ReactBudget(max_steps=10, max_tool_calls=10))

    result = engine.run(state)

    assert result.status == ReactLoopStatus.STOPPED
    assert result.repeated_action_count == 2


def test_loop_engine_stops_on_non_retry_validation_error() -> None:
    engine = LoopEngine(
        planner=SequencePlanner([ReactActionType.VALIDATE]),
        policy=RejectPolicy(),
        executor=FixedExecutor(lambda *_: StepExecutionResult()),
    )
    state = ReactLoopState(budget=ReactBudget(max_steps=10, max_tool_calls=10))

    result = engine.run(state)

    assert result.status == ReactLoopStatus.FAILED
    assert result.last_error == "validation failed"
    stop_events = [
        event
        for event in result.audit_events
        if event.event_type == "loop_stopped"
    ]
    assert len(stop_events) == 1
    assert stop_events[0].details["stop_reason"] == "non_retry_error"
