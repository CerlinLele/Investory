from investory.agent_core.tools.financial_concepts import FinancialConceptTool
from investory.agent_core.tools.instrument_profile import InstrumentProfileTool
from investory.agent_core.tools.material_extraction import MaterialExtractionTool
from investory.agent_core.tools.registry import ToolRegistry


def build_mock_tool_registry() -> ToolRegistry:
    return ToolRegistry(
        [
            FinancialConceptTool(),
            InstrumentProfileTool(),
            MaterialExtractionTool(),
        ]
    )
