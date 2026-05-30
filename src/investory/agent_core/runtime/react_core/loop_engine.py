from enum import Enum
from typing import Protocol

from pydantic import BaseModel, Field

from investory.agent_core.contracts.react_loop import (
    ReactActionType,
    ReactAuditEvent,
    ReactLoopState,
    ReactLoopStatus,
    ReactStepRecord,
    ReactToolCallRecord,
)


class ReactStopReason(str, Enum):
    FINALIZE = "finalize"
    WAITING_FOR_USER = "waiting_for_user"
    MAX_STEPS_REACHED = "max_steps_reached"
    MAX_TOOL_CALLS_REACHED = "max_tool_calls_reached"
    REPEATED_ACTION_LIMIT_REACHED = "repeated_action_limit_reached"
    NON_RETRY_ERROR = "non_retry_error"


class ReactAuditEventType(str, Enum):
    LOOP_STARTED = "loop_started"
    STEP_PLANNED = "step_planned"
    STEP_VALIDATED = "step_validated"
    STEP_EXECUTED = "step_executed"
    STEP_FAILED = "step_failed"
    LOOP_STOPPED = "loop_stopped"


STOP_REASON_MESSAGES: dict[ReactStopReason, str] = {
    ReactStopReason.FINALIZE: "Loop finalized.",
    ReactStopReason.WAITING_FOR_USER: "Loop is waiting for user input.",
    ReactStopReason.MAX_STEPS_REACHED: "Loop stopped because max steps were reached.",
    ReactStopReason.MAX_TOOL_CALLS_REACHED: "Loop stopped because max tool calls were reached.",
    ReactStopReason.REPEATED_ACTION_LIMIT_REACHED: (
        "Loop stopped because repeated action limit was reached."
    ),
    ReactStopReason.NON_RETRY_ERROR: "Loop stopped because a non-retry error occurred.",
}

DEFAULT_MAX_REPEATED_ACTIONS = 3


class PlannedStep(BaseModel):
    action_type: ReactActionType
    summary: str | None = None
    metadata: dict[str, object] = Field(default_factory=dict)


class StepValidationResult(BaseModel):
    ok: bool
    retryable: bool = False
    error_message: str | None = None
    details: dict[str, object] = Field(default_factory=dict)


class StepExecutionResult(BaseModel):
    finalize: bool = False
    waiting_for_user: bool = False
    retryable_error: bool = False
    error_message: str | None = None
    details: dict[str, object] = Field(default_factory=dict)
    tool_call_record: ReactToolCallRecord | None = None


class StepPlanner(Protocol):
    def plan_next_step(self, state: ReactLoopState) -> PlannedStep:
        ...


class StepPolicy(Protocol):
    def validate_step(
        self,
        state: ReactLoopState,
        planned_step: PlannedStep,
    ) -> StepValidationResult:
        ...


class StepExecutor(Protocol):
    def execute_step(
        self,
        state: ReactLoopState,
        planned_step: PlannedStep,
    ) -> StepExecutionResult:
        ...


class LoopEngine:
    def __init__(
        self,
        *,
        planner: StepPlanner,
        policy: StepPolicy,
        executor: StepExecutor,
        max_repeated_actions: int = DEFAULT_MAX_REPEATED_ACTIONS,
    ) -> None:
        self._planner = planner
        self._policy = policy
        self._executor = executor
        self._max_repeated_actions = max_repeated_actions

    def run(self, state: ReactLoopState | None = None) -> ReactLoopState:
        loop_state = state or ReactLoopState()
        loop_state.status = ReactLoopStatus.RUNNING
        self.record_audit(
            loop_state,
            event_type=ReactAuditEventType.LOOP_STARTED,
            message="Loop execution started.",
        )

        while True:
            stop_reason = self.check_stop_condition(loop_state)
            if stop_reason is not None:
                self._apply_stop_reason(loop_state, stop_reason)
                self.record_audit(
                    loop_state,
                    event_type=ReactAuditEventType.LOOP_STOPPED,
                    message=STOP_REASON_MESSAGES[stop_reason],
                    details={"stop_reason": stop_reason.value},
                )
                return loop_state

            planned_step = self.plan_next_step(loop_state)
            self._record_step(loop_state, planned_step)
            self.record_audit(
                loop_state,
                event_type=ReactAuditEventType.STEP_PLANNED,
                action_type=planned_step.action_type,
                message=planned_step.summary,
                details=planned_step.metadata,
            )

            validation_result = self.validate_step(loop_state, planned_step)
            self.record_audit(
                loop_state,
                event_type=ReactAuditEventType.STEP_VALIDATED,
                action_type=planned_step.action_type,
                message="Step validation completed.",
                details={
                    "ok": validation_result.ok,
                    "retryable": validation_result.retryable,
                },
            )
            if not validation_result.ok:
                self._handle_validation_error(
                    loop_state,
                    planned_step,
                    validation_result,
                )
                continue

            execution_result = self.execute_step(loop_state, planned_step)
            if execution_result.tool_call_record is not None:
                loop_state.tool_call_records.append(execution_result.tool_call_record)

            if planned_step.action_type == ReactActionType.CALL_TOOL:
                loop_state.tool_call_count += 1

            if execution_result.error_message is not None:
                self._handle_execution_error(
                    loop_state,
                    planned_step,
                    execution_result,
                )
                continue

            loop_state.retry_count = 0
            if planned_step.action_type == ReactActionType.FINALIZE or execution_result.finalize:
                loop_state.status = ReactLoopStatus.FINALIZED
            elif (
                planned_step.action_type == ReactActionType.WAIT_FOR_USER
                or execution_result.waiting_for_user
            ):
                loop_state.requires_user_input = True
                loop_state.status = ReactLoopStatus.WAITING_FOR_USER
            else:
                loop_state.status = ReactLoopStatus.RUNNING

            self.record_audit(
                loop_state,
                event_type=ReactAuditEventType.STEP_EXECUTED,
                action_type=planned_step.action_type,
                message="Step execution completed.",
                details=execution_result.details,
            )

    def plan_next_step(self, state: ReactLoopState) -> PlannedStep:
        return self._planner.plan_next_step(state)

    def validate_step(
        self,
        state: ReactLoopState,
        planned_step: PlannedStep,
    ) -> StepValidationResult:
        return self._policy.validate_step(state, planned_step)

    def execute_step(
        self,
        state: ReactLoopState,
        planned_step: PlannedStep,
    ) -> StepExecutionResult:
        return self._executor.execute_step(state, planned_step)

    def record_audit(
        self,
        state: ReactLoopState,
        *,
        event_type: ReactAuditEventType,
        action_type: ReactActionType | None = None,
        message: str | None = None,
        details: dict[str, object] | None = None,
    ) -> None:
        state.audit_events.append(
            ReactAuditEvent(
                event_type=event_type.value,
                step_index=state.step_count,
                status=state.status,
                action_type=action_type,
                message=message,
                details=details or {},
            )
        )

    def check_stop_condition(self, state: ReactLoopState) -> ReactStopReason | None:
        if state.status == ReactLoopStatus.FINALIZED:
            return ReactStopReason.FINALIZE

        if state.status == ReactLoopStatus.WAITING_FOR_USER or state.requires_user_input:
            return ReactStopReason.WAITING_FOR_USER

        if state.step_count >= state.budget.max_steps:
            return ReactStopReason.MAX_STEPS_REACHED

        if state.tool_call_count >= state.budget.max_tool_calls:
            return ReactStopReason.MAX_TOOL_CALLS_REACHED

        if state.repeated_action_count >= self._max_repeated_actions:
            return ReactStopReason.REPEATED_ACTION_LIMIT_REACHED

        if state.status == ReactLoopStatus.FAILED:
            return ReactStopReason.NON_RETRY_ERROR

        return None

    def _record_step(self, state: ReactLoopState, planned_step: PlannedStep) -> None:
        state.step_count += 1
        state.current_action = planned_step.action_type

        previous_action = state.step_records[-1].action_type if state.step_records else None
        if previous_action == planned_step.action_type:
            state.repeated_action_count += 1
        else:
            state.repeated_action_count = 1

        state.step_records.append(
            ReactStepRecord(
                step_index=state.step_count,
                action_type=planned_step.action_type,
                summary=planned_step.summary,
                metadata=dict(planned_step.metadata),
            )
        )

    def _handle_validation_error(
        self,
        state: ReactLoopState,
        planned_step: PlannedStep,
        validation_result: StepValidationResult,
    ) -> None:
        error_message = validation_result.error_message or "Step validation failed."
        state.last_error = error_message

        if validation_result.retryable and state.retry_count < state.budget.max_retries:
            state.retry_count += 1
            self.record_audit(
                state,
                event_type=ReactAuditEventType.STEP_FAILED,
                action_type=planned_step.action_type,
                message=error_message,
                details={"retryable": True, **validation_result.details},
            )
            return

        state.status = ReactLoopStatus.FAILED
        self.record_audit(
            state,
            event_type=ReactAuditEventType.STEP_FAILED,
            action_type=planned_step.action_type,
            message=error_message,
            details={"retryable": False, **validation_result.details},
        )

    def _handle_execution_error(
        self,
        state: ReactLoopState,
        planned_step: PlannedStep,
        execution_result: StepExecutionResult,
    ) -> None:
        state.last_error = execution_result.error_message
        retryable_error = execution_result.retryable_error

        if retryable_error and state.retry_count < state.budget.max_retries:
            state.retry_count += 1
            self.record_audit(
                state,
                event_type=ReactAuditEventType.STEP_FAILED,
                action_type=planned_step.action_type,
                message=execution_result.error_message,
                details={"retryable": True, **execution_result.details},
            )
            return

        state.status = ReactLoopStatus.FAILED
        self.record_audit(
            state,
            event_type=ReactAuditEventType.STEP_FAILED,
            action_type=planned_step.action_type,
            message=execution_result.error_message,
            details={"retryable": False, **execution_result.details},
        )

    @staticmethod
    def _apply_stop_reason(state: ReactLoopState, stop_reason: ReactStopReason) -> None:
        if stop_reason == ReactStopReason.FINALIZE:
            state.status = ReactLoopStatus.FINALIZED
            return

        if stop_reason == ReactStopReason.WAITING_FOR_USER:
            state.requires_user_input = True
            state.status = ReactLoopStatus.WAITING_FOR_USER
            return

        if stop_reason in {
            ReactStopReason.MAX_STEPS_REACHED,
            ReactStopReason.MAX_TOOL_CALLS_REACHED,
            ReactStopReason.REPEATED_ACTION_LIMIT_REACHED,
        }:
            state.status = ReactLoopStatus.STOPPED
            return

        state.status = ReactLoopStatus.FAILED
