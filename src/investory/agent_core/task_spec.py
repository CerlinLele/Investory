from dataclasses import dataclass

from pydantic import BaseModel


@dataclass(slots=True)
class TaskSpec:
    name: str
    prompt_name: str
    input_model: type[BaseModel]
    output_model: type[BaseModel]
