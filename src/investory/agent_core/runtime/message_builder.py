import json
from typing import Any

from langchain_core.prompts import ChatPromptTemplate

from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.prompt_loader import load_prompt_text


def build_messages(spec: TaskSpec, payload: dict[str, Any]) -> list[Any]:
    system_prompt = load_prompt_text("base", "system.md")
    common_rules = load_prompt_text("base", "common_rules.md")
    input_data_block = load_prompt_text("base", "input_data_block.md")
    task_prompt = load_prompt_text("tasks", f"{spec.prompt_name}.md")
    input_json = json.dumps(payload, ensure_ascii=False, indent=2)

    prompt = ChatPromptTemplate(
        [
            ("system", system_prompt),
            ("human", task_prompt),
        ]
    )

    return prompt.invoke(
        {
            "common_rules": common_rules,
            "input_data_block": input_data_block.format(input_json=input_json),
        }
    ).messages
