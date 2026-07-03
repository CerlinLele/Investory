from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(slots=True)
class TaskSpec:
    name: str
    prompt_name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    side_effect_level: str = "read"  # read / write / exec
    tag: str = ""  # learning / document_review / risk / ...
    desc: str = ""  # one-line description
