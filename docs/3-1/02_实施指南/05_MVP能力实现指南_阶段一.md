# 讲座 MVP 在 Investory 中的具体实现指南

> 基于 [02_讲座MVP与现有代码的映射与迁移.md](./02_讲座MVP与现有代码的映射与迁移.md)  
> 本文档展示讲座 MVP 的四个核心能力如何在 Investory 中逐步实现

## 🎯 核心思想回顾

讲座 MVP 的四个能力：
1. **register(id, desc, schema, func)** — 集中声明
2. **list_all()** — 全量清单  
3. **get_spec(id)** — 按 ID 查询声明
4. **get_func(id)** — 按 ID 获取执行函数

Investory 的现状：
- ✅ 已有 `register()` 和 `get_spec()` 的框架
- ❌ 缺 `func` 字段、`list_all()`、`get_func()` 的实现

---

## 🛠️ 阶段一：扩展 ToolSpec 和 Registry（0.5 天）

### 步骤 1.1：扩展 ToolSpec 数据类

**文件**：`src/investory/agent_core/runtime/react_core/tool_registry.py`

**改动**：

```python
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
    func: Callable | None = None              # ← 新增：执行函数
    desc: str = ""                            # ← 新增：工具描述
    side_effect_level: str = "read"           # ← 新增：read/write/exec
    tag: str = ""                             # ← 新增：业务标签
    requires_confirmation: bool = False
    allowed_task_names: frozenset[str] = ALL_TASKS_ALLOWED
    
    def to_spec_dict(self) -> dict:
        """返回工具的能力声明（不含 func）"""
        return {
            "name": self.name,
            "desc": self.desc,
            "side_effect_level": self.side_effect_level,
            "tag": self.tag,
            "args_schema": self.args_model.model_json_schema(),
        }
```

### 步骤 1.2：扩展 ToolRegistry 查询方法

**在同一文件中添加**：

```python
class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._specs[spec.name] = spec

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)
    
    # ── 新增查询方法 ────────────────────────
    
    def list_all(self) -> list[dict]:
        """返回所有工具的能力声明"""
        return [spec.to_spec_dict() for spec in self._specs.values()]
    
    def list_by_tag(self, tag: str) -> list[dict]:
        """按业务标签筛选工具"""
        return [
            spec.to_spec_dict()
            for spec in self._specs.values()
            if spec.tag == tag
        ]
    
    def list_by_side_effect(self, level: str) -> list[dict]:
        """按副作用等级筛选工具"""
        return [
            spec.to_spec_dict()
            for spec in self._specs.values()
            if spec.side_effect_level == level
        ]
    
    def get_spec_dict(self, name: str) -> dict | None:
        """获取单个工具的能力声明"""
        spec = self.get(name)
        return spec.to_spec_dict() if spec else None
    
    def get_func(self, name: str) -> Callable | None:
        """获取工具的执行函数"""
        spec = self.get(name)
        return spec.func if spec else None
    
    def call_func(self, name: str, args: dict[str, Any]) -> Any:
        """执行工具函数（中间层，可挂审计/风控）"""
        func = self.get_func(name)
        if func is None:
            raise ValueError(f"Tool '{name}' not found or has no executable function")
        
        # TODO: 可在这里加审计日志、风控检查等
        return func(**args)
    
    # ── 保留现有方法 ────────────────────────
    
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
```

### 步骤 1.3：验证改动不破坏现有代码

**命令**：
```bash
# 确保现有测试仍然通过
pytest tests/ -v -k "test_tool_registry or test_task" --tb=short
```

**预期**：所有现有测试通过（新字段有默认值，向后兼容）

### 步骤 1.4：为新方法写测试

**新文件**：`tests/test_tool_registry_enhanced.py`

```python
import pytest
from pydantic import BaseModel
from investory.agent_core.runtime.react_core.tool_registry import ToolRegistry, ToolSpec


class SimpleArgs(BaseModel):
    value: str


def dummy_func(value: str) -> dict:
    return {"result": value}


def test_list_all_returns_all_tools():
    """测试 list_all() 返回所有已注册的工具"""
    registry = ToolRegistry()
    spec1 = ToolSpec(
        name="tool1",
        args_model=SimpleArgs,
        func=dummy_func,
        desc="Tool 1",
        side_effect_level="read",
        tag="test"
    )
    spec2 = ToolSpec(
        name="tool2",
        args_model=SimpleArgs,
        func=dummy_func,
        desc="Tool 2",
        side_effect_level="write",
        tag="test"
    )
    registry.register(spec1)
    registry.register(spec2)
    
    specs = registry.list_all()
    assert len(specs) == 2
    assert specs[0]["name"] in ["tool1", "tool2"]


def test_list_by_tag():
    """测试按 tag 筛选"""
    registry = ToolRegistry()
    spec1 = ToolSpec(
        name="query_tool",
        args_model=SimpleArgs,
        func=dummy_func,
        tag="query"
    )
    spec2 = ToolSpec(
        name="write_tool",
        args_model=SimpleArgs,
        func=dummy_func,
        tag="write"
    )
    registry.register(spec1)
    registry.register(spec2)
    
    query_specs = registry.list_by_tag("query")
    assert len(query_specs) == 1
    assert query_specs[0]["name"] == "query_tool"


def test_list_by_side_effect():
    """测试按 side_effect_level 筛选"""
    registry = ToolRegistry()
    spec1 = ToolSpec(
        name="read_tool",
        args_model=SimpleArgs,
        func=dummy_func,
        side_effect_level="read"
    )
    spec2 = ToolSpec(
        name="write_tool",
        args_model=SimpleArgs,
        func=dummy_func,
        side_effect_level="write"
    )
    registry.register(spec1)
    registry.register(spec2)
    
    write_specs = registry.list_by_side_effect("write")
    assert len(write_specs) == 1
    assert write_specs[0]["name"] == "write_tool"


def test_get_func():
    """测试 get_func() 返回执行函数"""
    registry = ToolRegistry()
    spec = ToolSpec(
        name="test_tool",
        args_model=SimpleArgs,
        func=dummy_func,
        desc="Test Tool"
    )
    registry.register(spec)
    
    func = registry.get_func("test_tool")
    assert func is not None
    assert func("hello") == {"result": "hello"}


def test_call_func():
    """测试 call_func() 执行工具"""
    registry = ToolRegistry()
    spec = ToolSpec(
        name="test_tool",
        args_model=SimpleArgs,
        func=dummy_func,
        desc="Test Tool"
    )
    registry.register(spec)
    
    result = registry.call_func("test_tool", {"value": "world"})
    assert result == {"result": "world"}


def test_call_func_not_found():
    """测试调用不存在的工具"""
    registry = ToolRegistry()
    
    with pytest.raises(ValueError):
        registry.call_func("nonexistent", {})
```

**运行**：
```bash
pytest tests/test_tool_registry_enhanced.py -v
```

---

## 📋 阶段一完成检查清单

```
Commit: feat(tool-registry): add core MVP capabilities

[ ] src/investory/agent_core/runtime/react_core/tool_registry.py
    - ToolSpec: add func, desc, side_effect_level, tag
    - ToolRegistry: add list_all()
    - ToolRegistry: add list_by_tag()
    - ToolRegistry: add list_by_side_effect()
    - ToolRegistry: add get_func()
    - ToolRegistry: add call_func()
    - ToolSpec: add to_spec_dict()

[ ] tests/test_tool_registry_enhanced.py (new)
    - test_list_all_returns_all_tools
    - test_list_by_tag
    - test_list_by_side_effect
    - test_get_func
    - test_call_func
    - test_call_func_not_found

[ ] pytest tests/test_tool_registry_enhanced.py -v
    => all tests pass

[ ] pytest tests/ -v
    => no new failures in existing tests

[ ] Code review:
    - 所有新字段都有默认值（向后兼容）
    - 文档字符串清晰
    - 错误处理合理
```

---

## 🎯 收益验收

### 阶段一完成后，你有了什么

✅ **ToolRegistry 现在是讲座 MVP 中描述的样子**

```python
# 现在可以这样用
registry.register(ToolSpec(
    name="query_leave",
    desc="查询员工剩余年假天数",
    args_model=QueryLeaveArgs,
    func=query_leave,
    side_effect_level="read",
    tag="query"
))

# 查询
specs = registry.list_all()                    # ← list_all
specs = registry.list_by_tag("query")          # ← list_specs by tag
specs = registry.list_by_side_effect("read")   # ← list_specs by level
func = registry.get_func("query_leave")        # ← get_func
result = registry.call_func("query_leave", {"employee_id": "E001"})  # ← execute
```

✅ **Investory 现有的验证机制仍然工作**

- `registry.validate()` 仍然可以检查权限、参数有效性、确认要求
- 所有现有测试通过

✅ **为下一阶段奠基**

- 阶段二需要用 `func` 来注册真实的 actions
- 阶段三需要用 `call_func()` 来执行
- 阶段四需要用 `list_*()` 来查询

---

## 🚀 后续阶段预告

| 阶段 | 核心任务 | 依赖 | 产出 |
|---|---|---|---|
| **二** | 把 actions 改成工具函数，注册到 registry | 阶段一 | `investory_actions.py` 成为 registry 的管理中心 |
| **三** | LoopEngine 从 registry 调函数 | 阶段二 | 执行可被追踪、可注入审计日志 |
| **四** | routing 暴露查询 API | 阶段一 | 前端/管理页面可查工具清单 |

---

**注意**：本指南只涉及阶段一。完成后可参考各阶段的后续指南。
