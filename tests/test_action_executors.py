from investory.agent_core.actions.executors import (
    AskMissingFieldsExecutor,
    FetchThenRunInstrumentBriefExecutor,
    RefuseInvestmentAdviceExecutor,
    RunWebSearchExecutor,
    RunTaskModelExecutor,
)
from investory.agent_core.contracts.action_contract import ActionCall
from investory.agent_core.contracts.result_types import TaskError, TaskResult
from investory.agent_core.contracts.tool_contract import ToolResult
from investory.agent_core.tasks import INSTRUMENT_BRIEF_TASK


class FakeTaskExecutor:
    def __init__(self, result: TaskResult) -> None:
        self.result = result
        self.calls: list[tuple[object, dict]] = []

    def run(self, spec, payload: dict) -> TaskResult:
        self.calls.append((spec, payload))
        return self.result


def test_ask_missing_fields_executor_returns_requires_user_input_result():
    call = ActionCall(
        action="ask_missing_fields",
        task_name="instrument_brief",
        params={"missing_fields": ["source_material"]},
        decision_reason="The request is missing source_material.",
    )

    result = AskMissingFieldsExecutor().execute(call, INSTRUMENT_BRIEF_TASK)

    assert result.action == "ask_missing_fields"
    assert result.task_name == "instrument_brief"
    assert result.status == "requires_user_input"
    assert result.result is not None
    assert result.result["action"] == "ask_missing_fields"
    assert result.result["missing_fields"] == ["source_material"]
    assert result.user_message == result.result["user_message"]


def test_run_task_model_executor_converts_successful_task_result():
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
    call = ActionCall(
        action="run_task_model",
        task_name="instrument_brief",
        params={"payload": payload},
        decision_reason="Ready to run.",
    )

    result = RunTaskModelExecutor(task_executor=task_executor).execute(
        call,
        INSTRUMENT_BRIEF_TASK,
    )

    assert result.status == "success"
    assert result.result == {"overview": "Broad US equities."}
    assert result.error is None
    assert task_executor.calls == [(INSTRUMENT_BRIEF_TASK, payload)]


def test_run_task_model_executor_converts_failed_task_result():
    task_error = TaskError(
        error_type="structured_output_failed",
        stage="output_validation",
        user_safe_message="The AI response did not match the required format.",
        retryable=True,
    )
    task_result = TaskResult(
        ok=False,
        task_name="instrument_brief",
        error=task_error,
    )
    call = ActionCall(
        action="run_task_model",
        task_name="instrument_brief",
        params={"payload": {}},
        decision_reason="Ready to run.",
    )

    result = RunTaskModelExecutor(
        task_executor=FakeTaskExecutor(task_result),
    ).execute(call, INSTRUMENT_BRIEF_TASK)

    assert result.status == "failed"
    assert result.result is None
    assert result.error == task_error


def test_refuse_investment_advice_executor_returns_refused_result():
    call = ActionCall(
        action="refuse_investment_advice",
        task_name="instrument_brief",
        params={
            "refused_reason": "The request asks for a buy or sell decision.",
            "allowed_alternative": "I can help create an educational brief.",
            "user_message": "I cannot decide whether you should buy or sell.",
        },
        decision_reason="High-risk investment advice request.",
    )

    result = RefuseInvestmentAdviceExecutor().execute(call, INSTRUMENT_BRIEF_TASK)

    assert result.status == "refused"
    assert result.user_message == "I cannot decide whether you should buy or sell."
    assert result.result == {
        "action": "refuse_investment_advice",
        "task_name": "instrument_brief",
        "refused_reason": "The request asks for a buy or sell decision.",
        "allowed_alternative": "I can help create an educational brief.",
        "user_message": "I cannot decide whether you should buy or sell.",
    }


def test_fetch_then_run_executor_fetches_material_and_runs_task_model():
    payload = {"instrument_name_or_code": "VTI"}
    task_result = TaskResult(
        ok=True,
        task_name="instrument_brief",
        result={"overview": "US total market ETF."},
    )
    task_executor = FakeTaskExecutor(task_result)

    def fake_fetcher(code: str) -> ToolResult:
        assert code == "VTI"
        return ToolResult(
            tool_name="fetch_instrument_profile",
            ok=True,
            data={
                "instrument_name_or_code": "VTI",
                "source_material": "VTI factsheet mock text.",
                "sources": ["https://example.com/vti"],
                "as_of": "2026-05-15",
            },
        )

    call = ActionCall(
        action="fetch_then_run_instrument_brief",
        task_name="instrument_brief",
        params={
            "instrument_name_or_code": "VTI",
            "payload": payload,
        },
        decision_reason="Need source material before running the task model.",
    )

    result = FetchThenRunInstrumentBriefExecutor(
        task_executor=task_executor,
        fetcher=fake_fetcher,
    ).execute(call, INSTRUMENT_BRIEF_TASK)

    assert result.status == "success"
    assert result.result == {"overview": "US total market ETF."}
    assert task_executor.calls == [
        (
            INSTRUMENT_BRIEF_TASK,
            {
                "instrument_name_or_code": "VTI",
                "source_material": "VTI factsheet mock text.",
                "source_links": ["https://example.com/vti"],
                "source_as_of": "2026-05-15",
            },
        )
    ]


def test_fetch_then_run_executor_returns_requires_user_input_when_fetch_fails():
    task_executor = FakeTaskExecutor(
        TaskResult(ok=True, task_name="instrument_brief", result={"overview": "unused"})
    )

    def fake_fetcher(code: str) -> ToolResult:
        assert code == "VTI"
        return ToolResult(
            tool_name="fetch_instrument_profile",
            ok=False,
            error_type="network_error",
            error_message="timeout",
            retryable=True,
        )

    call = ActionCall(
        action="fetch_then_run_instrument_brief",
        task_name="instrument_brief",
        params={
            "instrument_name_or_code": "VTI",
            "payload": {"instrument_name_or_code": "VTI"},
        },
        decision_reason="Need source material before running the task model.",
    )

    result = FetchThenRunInstrumentBriefExecutor(
        task_executor=task_executor,
        fetcher=fake_fetcher,
    ).execute(call, INSTRUMENT_BRIEF_TASK)

    assert result.status == "requires_user_input"
    assert result.user_message is not None
    assert len(result.user_message.strip()) > 0
    assert result.result is not None
    assert result.result["action"] == "fetch_then_run_instrument_brief"
    assert result.result["instrument_name_or_code"] == "VTI"
    assert result.result["tool_error_type"] == "network_error"
    assert result.result["tool_error_message"] == "timeout"
    assert task_executor.calls == []


def test_run_web_search_executor_returns_successful_results():
    def fake_searcher(query: str, top_k: int, provider_hint: str | None) -> ToolResult:
        assert query == "VTI"
        assert top_k == 3
        assert provider_hint == "example_search"
        return ToolResult(
            tool_name="web_search",
            ok=True,
            data={
                "query": "VTI",
                "results": [
                    {
                        "title": "Mock Result",
                        "url": "https://example.com/mock",
                        "snippet": "mock snippet",
                        "source": "example.com",
                        "provider": "example_search",
                    }
                ],
                "provider_attempt_order": ["example_search"],
            },
        )

    call = ActionCall(
        action="run_web_search",
        task_name="web_search_brief",
        params={"query": "VTI", "top_k": 3, "provider_hint": "example_search"},
        decision_reason="Run web search tool.",
    )
    result = RunWebSearchExecutor(searcher=fake_searcher).execute(call, INSTRUMENT_BRIEF_TASK)

    assert result.status == "success"
    assert result.result is not None
    assert result.result["query"] == "VTI"
    assert len(result.result["results"]) == 1


def test_run_web_search_executor_returns_requires_user_input_when_search_fails():
    def fake_searcher(query: str, top_k: int, provider_hint: str | None) -> ToolResult:
        return ToolResult(
            tool_name="web_search",
            ok=False,
            error_type="network_error",
            error_message="timeout",
            retryable=True,
        )

    call = ActionCall(
        action="run_web_search",
        task_name="web_search_brief",
        params={"query": "VTI"},
        decision_reason="Run web search tool.",
    )
    result = RunWebSearchExecutor(searcher=fake_searcher).execute(call, INSTRUMENT_BRIEF_TASK)

    assert result.status == "requires_user_input"
    assert result.result is not None
    assert result.result["tool_error_type"] == "network_error"
    assert result.result["retryable"] is True
