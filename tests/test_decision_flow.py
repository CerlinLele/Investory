from investory.agent_core.actions.router import ActionRouter
from investory.agent_core.contracts import tool_contract
from investory.agent_core.contracts.action_contract import ActionCall, ActionResult
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.runtime.decision_flow import (
    DecisionFlow,
    backfill_action_result,
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
    task_executor = FakeTaskExecutor(
        TaskResult(
            ok=True,
            task_name="instrument_brief",
            result={"overview": "Generated from fetched profile."},
        )
    )
    flow = DecisionFlow(task_executor=task_executor)

    result = flow.run(
        INSTRUMENT_BRIEF_TASK,
        {"instrument_name_or_code": "VOO"},
        request_id="req_123",
    )

    assert result.ok is True
    assert result.task_name == "instrument_brief"
    assert result.error is None
    assert result.result is not None
    assert result.result["overview"] == "Generated from fetched profile."
    assert task_executor.calls
    assert task_executor.calls[0][1]["instrument_name_or_code"] == "VOO"
    assert "source_material" in task_executor.calls[0][1]
    assert flow.last_state is not None
    assert flow.last_state.task_id == "req_123"
    assert flow.last_state.decision is not None
    assert flow.last_state.decision.action == "fetch_then_run_instrument_brief"
    assert flow.last_state.action_call is not None
    assert flow.last_state.action_call.action == "fetch_then_run_instrument_brief"
    assert flow.last_state.action_result is not None
    assert flow.last_state.action_result.status == "success"


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


def test_decision_flow_degrades_to_requires_user_input_when_tool_fetch_fails(
    monkeypatch,
):
    from investory.agent_core.actions import executors as executors_module

    monkeypatch.setattr(
        executors_module,
        "fetch_instrument_profile",
        lambda code: tool_contract.ToolResult(
            tool_name="fetch_instrument_profile",
            ok=False,
            error_type="network_error",
            error_message="timeout",
            retryable=True,
        ),
    )

    flow = DecisionFlow(
        task_executor=FakeTaskExecutor(
            TaskResult(
                ok=True,
                task_name="instrument_brief",
                result={"overview": "unused"},
            )
        )
    )

    result = flow.run(
        INSTRUMENT_BRIEF_TASK,
        {"instrument_name_or_code": "VOO"},
        request_id="req_456",
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result["action"] == "fetch_then_run_instrument_brief"
    assert result.result["tool_error_type"] == "network_error"
    assert flow.last_state is not None
    assert flow.last_state.action_result is not None
    assert flow.last_state.action_result.status == "requires_user_input"


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
