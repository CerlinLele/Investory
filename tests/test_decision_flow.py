from investory.agent_core.actions.router import ActionRouter, ActionRoutingError
from investory.agent_core.contracts.action_contract import ActionCall, ActionResult
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.runtime.decision_flow import (
    DecisionFlow,
    LearningQaFlowState,
    backfill_action_result,
    route_by_action_key,
)
from investory.agent_core.tasks import INSTRUMENT_BRIEF_TASK


class FakeTaskExecutor:
    def __init__(self, result: TaskResult) -> None:
        self.result = result
        self.calls: list[tuple[object, dict]] = []

    def run(self, spec, payload: dict) -> TaskResult:
        self.calls.append((spec, payload))
        return self.result


def test_decision_flow_returns_requires_user_input_for_missing_fields():
    flow = DecisionFlow()

    result = flow.run(
        INSTRUMENT_BRIEF_TASK,
        {"instrument_name_or_code": "VOO"},
        request_id="req_123",
    )

    assert result.ok is True
    assert result.task_name == "instrument_brief"
    assert result.error is None
    assert result.result is not None
    assert result.result["action"] == "ask_missing_fields"
    assert result.result["missing_fields"] == ["source_material"]
    assert flow.last_state is not None
    assert flow.last_state.task_id == "req_123"
    assert flow.last_state.decision is not None
    assert flow.last_state.decision.action == "ask_missing_fields"
    assert flow.last_state.action_call is not None
    assert flow.last_state.action_call.action == "ask_missing_fields"
    assert flow.last_state.action_result is not None
    assert flow.last_state.action_result.status == "requires_user_input"


def test_decision_flow_runs_task_executor_for_complete_payload():
    payload = {
        "instrument_name_or_code": "VOO",
        "source_material": "VOO tracks a broad US equity index.",
    }
    task_result = TaskResult(
        ok=True,
        task_name="instrument_brief",
        result={"overview": "Broad US equities."},
    )
    task_executor = FakeTaskExecutor(task_result)
    flow = DecisionFlow(task_executor=task_executor)

    result = flow.run(INSTRUMENT_BRIEF_TASK, payload)

    assert result.ok is True
    assert result.result == {"overview": "Broad US equities."}
    assert result.error is None
    assert task_executor.calls == [(INSTRUMENT_BRIEF_TASK, payload)]
    assert flow.last_state is not None
    assert flow.last_state.decision is not None
    assert flow.last_state.decision.action == "run_task_model"
    assert flow.last_state.action_result is not None
    assert flow.last_state.action_result.status == "success"


def test_decision_flow_backfills_failed_task_executor_result():
    payload = {
        "instrument_name_or_code": "VOO",
        "source_material": "VOO tracks a broad US equity index.",
    }
    task_error = TaskError(
        error_type="structured_output_failed",
        stage="output_validation",
        user_safe_message="The AI response did not match the required format.",
        retryable=True,
    )
    task_executor = FakeTaskExecutor(
        TaskResult(
            ok=False,
            task_name="instrument_brief",
            error=task_error,
        )
    )
    flow = DecisionFlow(task_executor=task_executor)

    result = flow.run(INSTRUMENT_BRIEF_TASK, payload)

    assert result.ok is False
    assert result.result is None
    assert result.error == task_error
    assert flow.last_state is not None
    assert flow.last_state.error == task_error


def test_decision_flow_can_use_custom_router_for_refusal_action():
    call_seen: list[ActionCall] = []

    class RefusePlanner:
        def decide(self, spec, payload):
            from investory.agent_core.contracts.action_contract import TaskDecision

            return TaskDecision(
                action="refuse_investment_advice",
                task_name=spec.name,
                reason="The request asks for a buy or sell decision.",
                params={
                    "refused_reason": "The system does not provide investment advice.",
                    "allowed_alternative": "I can help create an educational brief.",
                },
                user_message="I cannot decide whether you should buy or sell.",
            )

    class FakeRefuseExecutor:
        def execute(self, call, spec):
            call_seen.append(call)
            return ActionResult(
                action=call.action,
                task_name=call.task_name,
                status="refused",
                result={
                    "action": call.action,
                    "allowed_alternative": call.params["allowed_alternative"],
                },
                user_message="I cannot decide whether you should buy or sell.",
            )

    flow = DecisionFlow(
        planner=RefusePlanner(),
        router=ActionRouter(
            executors={"refuse_investment_advice": FakeRefuseExecutor()}
        ),
    )

    result = flow.run(INSTRUMENT_BRIEF_TASK, {})

    assert result.ok is True
    assert result.result == {
        "action": "refuse_investment_advice",
        "allowed_alternative": "I can help create an educational brief.",
    }
    assert len(call_seen) == 1


def test_backfill_action_result_creates_error_when_failed_action_has_none():
    action_result = ActionResult(
        action="run_task_model",
        task_name="instrument_brief",
        status="failed",
    )

    result = backfill_action_result(action_result)

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "unknown_error"
    assert result.error.stage == "model_call"


def test_route_by_action_key_returns_build_task_response_when_action_call_missing():
    state = LearningQaFlowState(
        task_id="req_1",
        spec=INSTRUMENT_BRIEF_TASK,
        task_name=INSTRUMENT_BRIEF_TASK.name,
        input_payload={},
    )

    assert route_by_action_key(state) == "build_task_response"


def test_route_by_action_key_returns_action_value_when_action_call_exists():
    state = LearningQaFlowState(
        task_id="req_2",
        spec=INSTRUMENT_BRIEF_TASK,
        task_name=INSTRUMENT_BRIEF_TASK.name,
        input_payload={},
        action_call=ActionCall(
            action="run_task_model",
            task_name=INSTRUMENT_BRIEF_TASK.name,
            params={"payload": {}},
            decision_reason="test",
        ),
    )

    assert route_by_action_key(state) == "run_task_model"


def test_decision_flow_converges_action_validation_error_to_failed_task_result():
    class InvalidRunPlanner:
        def decide(self, spec, payload):
            from investory.agent_core.contracts.action_contract import TaskDecision

            return TaskDecision(
                action="run_task_model",
                task_name=spec.name,
                reason="Invalid run_task_model decision without payload.",
                params={},
            )

    flow = DecisionFlow(planner=InvalidRunPlanner())

    result = flow.run(INSTRUMENT_BRIEF_TASK, {})

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "input_validation_failed"
    assert result.error.stage == "input_validation"
    assert flow.last_state is not None
    assert flow.last_state.error == result.error


def test_decision_flow_converges_action_routing_error_to_failed_task_result():
    class BrokenRouter:
        def route(self, call):
            raise ActionRoutingError("No route")

    payload = {
        "instrument_name_or_code": "VOO",
        "source_material": "VOO tracks a broad US equity index.",
    }
    flow = DecisionFlow(router=BrokenRouter())

    result = flow.run(INSTRUMENT_BRIEF_TASK, payload)

    assert result.ok is False
    assert result.error is not None
    assert result.error.error_type == "unknown_error"
    assert result.error.stage == "model_call"
