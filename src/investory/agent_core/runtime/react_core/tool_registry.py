from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from pydantic import BaseModel, Field, ValidationError


CONFIRMATION_GRANTED_ARG = "confirmation_granted"
ALL_TASKS_ALLOWED = frozenset[str]()


class ToolValidationErrorCode(str, Enum):
    TOOL_NOT_REGISTERED = "tool_not_registered"
    TOOL_NOT_ALLOWED_FOR_TASK = "tool_not_allowed_for_task"
    CONFIRMATION_REQUIRED = "confirmation_required"
    INVALID_TOOL_ARGS = "invalid_tool_args"


class ToolValidationError(BaseModel):
    code: ToolValidationErrorCode
    tool_name: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ToolValidationResult(BaseModel):
    ok: bool
    tool_name: str
    normalized_args: dict[str, Any] | None = None
    requires_confirmation: bool = False
    error: ToolValidationError | None = None


@dataclass(slots=True)
class ToolSpec:
    name: str
    args_model: type[BaseModel]
    func: Callable | None = None
    desc: str = ""
    side_effect_level: str = "read"
    tag: str = ""
    requires_confirmation: bool = False
    allowed_task_names: frozenset[str] = ALL_TASKS_ALLOWED

    def to_spec_dict(self) -> dict[str, Any]:
        """Return the tool capability declaration without the executable function."""
        return {
            "name": self.name,
            "desc": self.desc,
            "side_effect_level": self.side_effect_level,
            "tag": self.tag,
            "args_schema": self.args_model.model_json_schema(),
        }


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def list_all(self) -> list[dict[str, Any]]:
        """Return capability declarations for all registered tools."""
        return [spec.to_spec_dict() for spec in self._specs.values()]

    def list_by_tag(self, tag: str) -> list[dict[str, Any]]:
        """Return capability declarations filtered by business tag."""
        return [
            spec.to_spec_dict()
            for spec in self._specs.values()
            if spec.tag == tag
        ]

    def list_by_side_effect(self, level: str) -> list[dict[str, Any]]:
        """Return capability declarations filtered by side-effect level."""
        return [
            spec.to_spec_dict()
            for spec in self._specs.values()
            if spec.side_effect_level == level
        ]

    def get_spec_dict(self, name: str) -> dict[str, Any] | None:
        """Return a single tool capability declaration."""
        spec = self.get(name)
        return spec.to_spec_dict() if spec else None

    def get_func(self, name: str) -> Callable | None:
        """Return the executable function for a registered tool."""
        spec = self.get(name)
        return spec.func if spec else None

    def call_func(self, name: str, args: dict[str, Any]) -> Any:
        """Execute a registered tool function with the provided arguments."""
        func = self.get_func(name)
        if func is None:
            raise ValueError(f"Tool '{name}' not found or has no executable function")

        return func(**args)

    def validate(
        self,
        tool_name: str,
        args: dict[str, Any] | None,
        task_name: str,
    ) -> ToolValidationResult:
        spec = self.get(tool_name)
        if spec is None:
            return self._error_result(
                tool_name=tool_name,
                code=ToolValidationErrorCode.TOOL_NOT_REGISTERED,
                message="Tool is not registered in the registry.",
            )

        if spec.allowed_task_names and task_name not in spec.allowed_task_names:
            return self._error_result(
                tool_name=tool_name,
                code=ToolValidationErrorCode.TOOL_NOT_ALLOWED_FOR_TASK,
                message="Tool is not allowed for the provided task.",
                details={"task_name": task_name},
            )

        raw_args = args or {}
        if spec.requires_confirmation and not bool(
            raw_args.get(CONFIRMATION_GRANTED_ARG, False)
        ):
            return self._error_result(
                tool_name=tool_name,
                code=ToolValidationErrorCode.CONFIRMATION_REQUIRED,
                message="Tool call requires explicit confirmation.",
            )

        args_for_validation = dict(raw_args)
        args_for_validation.pop(CONFIRMATION_GRANTED_ARG, None)

        try:
            validated_args = spec.args_model.model_validate(args_for_validation)
        except ValidationError as exc:
            return self._error_result(
                tool_name=tool_name,
                code=ToolValidationErrorCode.INVALID_TOOL_ARGS,
                message="Tool arguments failed schema validation.",
                details={"errors": exc.errors()},
            )

        return ToolValidationResult(
            ok=True,
            tool_name=tool_name,
            normalized_args=validated_args.model_dump(),
            requires_confirmation=spec.requires_confirmation,
        )

    @staticmethod
    def _error_result(
        *,
        tool_name: str,
        code: ToolValidationErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> ToolValidationResult:
        return ToolValidationResult(
            ok=False,
            tool_name=tool_name,
            error=ToolValidationError(
                code=code,
                tool_name=tool_name,
                message=message,
                details=details or {},
            ),
        )