from pydantic import BaseModel

from investory.agent_core.tools import (
    ToolCallRecord,
    ToolExecutor,
    ToolSource,
)


class ExampleToolInput(BaseModel):
    query: str


class ExampleToolOutput(BaseModel):
    answer: str


class ExampleTool:
    name = "example_tool"
    description = "Returns a deterministic answer for contract tests."
    input_model = ExampleToolInput
    output_model = ExampleToolOutput

    def run(self, payload: BaseModel) -> BaseModel:
        validated_payload = self.input_model.model_validate(payload)
        return self.output_model(answer=f"Result for {validated_payload.query}")


def test_tool_source_is_serializable():
    source = ToolSource(
        provider="mock_provider",
        source_url="https://example.test/source",
        as_of="2026-05-23",
    )

    assert source.model_dump() == {
        "provider": "mock_provider",
        "source_url": "https://example.test/source",
        "as_of": "2026-05-23",
    }


def test_tool_call_record_captures_success_result():
    record = ToolCallRecord(
        tool_name="example_tool",
        args={"query": "ETF"},
        result={"answer": "Exchange-traded fund"},
        elapsed_ms=12,
    )

    assert record.error is None
    assert record.model_dump() == {
        "tool_name": "example_tool",
        "args": {"query": "ETF"},
        "result": {"answer": "Exchange-traded fund"},
        "error": None,
        "elapsed_ms": 12,
    }


def test_tool_call_record_captures_failure_result():
    record = ToolCallRecord(
        tool_name="example_tool",
        args={"query": ""},
        error="query must not be empty",
        elapsed_ms=3,
    )

    assert record.result is None
    assert record.error == "query must not be empty"


def test_tool_executor_is_a_structural_protocol():
    tool = ExampleTool()

    assert isinstance(tool, ToolExecutor)

    payload = tool.input_model(query="index fund")
    result = tool.run(payload)

    assert result == ExampleToolOutput(answer="Result for index fund")
