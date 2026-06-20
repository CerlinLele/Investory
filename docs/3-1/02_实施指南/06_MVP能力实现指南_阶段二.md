# MVP 能力实现指南 — 阶段二：工具函数注册

> 基于 [阶段一](./05_MVP能力实现指南_阶段一.md) 已完成  
> 本阶段：把现有的 actions 改成真实的工具函数，注册到 registry

## 🎯 阶段二目标

从**枚举型 actions** 转换到**函数式 actions**，每个工具都有：
- 真实的执行函数
- 参数模型（Pydantic）
- 元数据（描述、标签、副作用等级）
- 注册到 registry

---

## 🛠️ 具体改动

### 步骤 2.1：重构 investory_actions.py

**当前状态** (`investory_actions.py`)：
```python
class InvestoryAction(str, Enum):
    ASK_FOR_MISSING_INPUT = "ask_for_missing_input"
    REFUSE_AND_REDIRECT = "refuse_and_redirect"
    EXECUTE_LEARNING_TASK = "execute_learning_task"
    CALL_TOOL = "call_tool"
    FINALIZE = "finalize"
```

**问题**：这只是字符串常量，没有对应的执行函数。

**改造方案**：

**新文件**：`src/investory/agent_core/runtime/tools_factory.py`

```python
"""工具函数定义和注册工厂

这个模块集中定义所有可用的工具函数，并负责管理它们的注册。
"""
from typing import Any
from pydantic import BaseModel, Field
from investory.agent_core.runtime.react_core.tool_registry import ToolRegistry, ToolSpec


# ── 参数模型 ────────────────────────────────────────


class AskForMissingInputArgs(BaseModel):
    """请求用户补充缺失信息"""
    task_name: str = Field(..., description="任务名称")
    missing_fields: list[str] = Field(..., description="缺失的字段列表")


class RefuseAndRedirectArgs(BaseModel):
    """拒绝并重定向"""
    reason: str = Field(..., description="拒绝原因")
    redirect_to: str = Field(..., description="重定向目标")


class ExecuteLearningTaskArgs(BaseModel):
    """执行学习任务"""
    task_name: str = Field(..., description="任务名称")
    payload: dict[str, Any] = Field(default_factory=dict, description="任务输入")


class CallToolArgs(BaseModel):
    """调用工具"""
    tool_name: str = Field(..., description="工具名称")
    args: dict[str, Any] = Field(default_factory=dict, description="工具参数")


class FinalizeArgs(BaseModel):
    """完成流程"""
    summary: str = Field(..., description="完成总结")


# ── 工具函数实现 ────────────────────────────────────


def ask_for_missing_input(task_name: str, missing_fields: list[str]) -> dict:
    """请求用户补充缺失信息
    
    当系统检测到输入不完整时调用此工具。
    """
    return {
        "action": "ask_for_missing_input",
        "task_name": task_name,
        "missing_fields": missing_fields,
        "message": f"请补充以下信息: {', '.join(missing_fields)}"
    }


def refuse_and_redirect(reason: str, redirect_to: str) -> dict:
    """拒绝并重定向
    
    当系统判断当前请求不适合处理时调用此工具。
    """
    return {
        "action": "refuse_and_redirect",
        "reason": reason,
        "redirect_to": redirect_to,
        "message": f"无法处理: {reason}，已重定向至 {redirect_to}"
    }


def execute_learning_task(task_name: str, payload: dict[str, Any] | None = None) -> dict:
    """执行学习任务
    
    触发具体的学习任务执行。
    """
    if payload is None:
        payload = {}
    
    return {
        "action": "execute_learning_task",
        "task_name": task_name,
        "payload": payload,
        "status": "pending"
    }


def call_tool(tool_name: str, args: dict[str, Any] | None = None) -> dict:
    """调用工具
    
    通过名字调用注册的工具。
    """
    if args is None:
        args = {}
    
    return {
        "action": "call_tool",
        "tool_name": tool_name,
        "args": args,
        "status": "pending"
    }


def finalize(summary: str) -> dict:
    """完成流程
    
    标记流程结束并返回最终总结。
    """
    return {
        "action": "finalize",
        "summary": summary,
        "status": "completed"
    }


# ── 注册工厂 ────────────────────────────────────────


def create_action_tools_registry() -> ToolRegistry:
    """创建并返回包含所有 action 工具的 registry
    
    每个工具都有完整的元数据：
    - name: 工具唯一标识
    - desc: 工具功能描述
    - args_model: 参数模型（Pydantic）
    - func: 执行函数
    - side_effect_level: 读/写等级
    - tag: 业务分类标签
    """
    registry = ToolRegistry()
    
    # 交互类工具
    registry.register(ToolSpec(
        name="ask_for_missing_input",
        desc="请求用户补充缺失信息",
        args_model=AskForMissingInputArgs,
        func=ask_for_missing_input,
        side_effect_level="read",
        tag="interaction",
        requires_confirmation=False
    ))
    
    registry.register(ToolSpec(
        name="refuse_and_redirect",
        desc="拒绝当前请求并重定向",
        args_model=RefuseAndRedirectArgs,
        func=refuse_and_redirect,
        side_effect_level="read",
        tag="interaction",
        requires_confirmation=False
    ))
    
    # 执行类工具
    registry.register(ToolSpec(
        name="execute_learning_task",
        desc="执行学习任务",
        args_model=ExecuteLearningTaskArgs,
        func=execute_learning_task,
        side_effect_level="write",
        tag="execution",
        requires_confirmation=False
    ))
    
    registry.register(ToolSpec(
        name="call_tool",
        desc="调用工具",
        args_model=CallToolArgs,
        func=call_tool,
        side_effect_level="write",
        tag="execution",
        requires_confirmation=False
    ))
    
    # 流程控制工具
    registry.register(ToolSpec(
        name="finalize",
        desc="完成流程",
        args_model=FinalizeArgs,
        func=finalize,
        side_effect_level="read",
        tag="control",
        requires_confirmation=False
    ))
    
    return registry


# ── 单例管理 ────────────────────────────────────────

_global_action_registry: ToolRegistry | None = None


def get_action_tools_registry() -> ToolRegistry:
    """获取全局 action tools registry（单例）"""
    global _global_action_registry
    if _global_action_registry is None:
        _global_action_registry = create_action_tools_registry()
    return _global_action_registry


def reset_action_tools_registry() -> None:
    """重置全局 registry（测试用）"""
    global _global_action_registry
    _global_action_registry = None
```

### 步骤 2.2：更新现有引用点

**文件** `src/investory/agent_core/runtime/flow/learning_entry/learning_entry_flow.py`

假设现有代码是这样的：

```python
def some_step(state):
    # 旧写法：直接用字符串
    if some_condition:
        return {"action": InvestoryAction.ASK_FOR_MISSING_INPUT}
```

改成：

```python
from investory.agent_core.runtime.tools_factory import get_action_tools_registry

def some_step(state):
    registry = get_action_tools_registry()
    # 新写法：调用 registry
    if some_condition:
        result = registry.call_func("ask_for_missing_input", {
            "task_name": state.task_name,
            "missing_fields": ["field1", "field2"]
        })
        return {"action": result}
```

### 步骤 2.3：为工具函数写测试

**新文件**：`tests/test_action_tools.py`

```python
import pytest
from investory.agent_core.runtime.tools_factory import (
    get_action_tools_registry,
    reset_action_tools_registry,
    AskForMissingInputArgs,
    ExecuteLearningTaskArgs,
)


@pytest.fixture(autouse=True)
def reset_registry():
    """每个测试后重置 registry"""
    yield
    reset_action_tools_registry()


class TestActionToolsRegistry:
    """测试 action tools registry"""
    
    def test_registry_has_all_five_actions(self):
        """验证所有 5 个 action 都被注册"""
        registry = get_action_tools_registry()
        specs = registry.list_all()
        assert len(specs) == 5
        
        names = {spec["name"] for spec in specs}
        assert names == {
            "ask_for_missing_input",
            "refuse_and_redirect",
            "execute_learning_task",
            "call_tool",
            "finalize"
        }
    
    def test_ask_for_missing_input_execution(self):
        """测试 ask_for_missing_input 工具执行"""
        registry = get_action_tools_registry()
        result = registry.call_func("ask_for_missing_input", {
            "task_name": "learning_task",
            "missing_fields": ["name", "email"]
        })
        
        assert result["action"] == "ask_for_missing_input"
        assert result["task_name"] == "learning_task"
        assert result["missing_fields"] == ["name", "email"]
    
    def test_execute_learning_task_execution(self):
        """测试 execute_learning_task 工具执行"""
        registry = get_action_tools_registry()
        result = registry.call_func("execute_learning_task", {
            "task_name": "document_review",
            "payload": {"doc_id": "123"}
        })
        
        assert result["action"] == "execute_learning_task"
        assert result["task_name"] == "document_review"
        assert result["payload"]["doc_id"] == "123"
    
    def test_finalize_execution(self):
        """测试 finalize 工具执行"""
        registry = get_action_tools_registry()
        result = registry.call_func("finalize", {
            "summary": "Process completed successfully"
        })
        
        assert result["action"] == "finalize"
        assert result["summary"] == "Process completed successfully"
        assert result["status"] == "completed"
    
    def test_list_by_side_effect(self):
        """测试按 side_effect_level 筛选"""
        registry = get_action_tools_registry()
        
        read_tools = registry.list_by_side_effect("read")
        write_tools = registry.list_by_side_effect("write")
        
        # 应该有读工具和写工具
        assert len(read_tools) > 0
        assert len(write_tools) > 0
        
        # 读工具中应该有 finalize
        read_names = {spec["name"] for spec in read_tools}
        assert "finalize" in read_names
        
        # 写工具中应该有 execute_learning_task
        write_names = {spec["name"] for spec in write_tools}
        assert "execute_learning_task" in write_names
    
    def test_list_by_tag(self):
        """测试按 tag 筛选"""
        registry = get_action_tools_registry()
        
        interaction_tools = registry.list_by_tag("interaction")
        execution_tools = registry.list_by_tag("execution")
        
        interaction_names = {spec["name"] for spec in interaction_tools}
        execution_names = {spec["name"] for spec in execution_tools}
        
        assert "ask_for_missing_input" in interaction_names
        assert "execute_learning_task" in execution_names
```

**运行**：
```bash
pytest tests/test_action_tools.py -v
```

### 步骤 2.4：验证现有流程仍然工作

**命令**：
```bash
pytest tests/ -v --tb=short
```

**预期**：
- 新测试全过
- 现有测试也全过（因为我们只是在 registry 之外新增，暂未改现有流程）

---

## 📋 阶段二完成检查清单

```
Commit: feat(actions): refactor to function-based tool registry

[ ] src/investory/agent_core/runtime/tools_factory.py (new)
    - AskForMissingInputArgs
    - RefuseAndRedirectArgs
    - ExecuteLearningTaskArgs
    - CallToolArgs
    - FinalizeArgs
    - ask_for_missing_input()
    - refuse_and_redirect()
    - execute_learning_task()
    - call_tool()
    - finalize()
    - create_action_tools_registry()
    - get_action_tools_registry()
    - reset_action_tools_registry()

[ ] tests/test_action_tools.py (new)
    - test_registry_has_all_five_actions
    - test_ask_for_missing_input_execution
    - test_execute_learning_task_execution
    - test_finalize_execution
    - test_list_by_side_effect
    - test_list_by_tag

[ ] pytest tests/test_action_tools.py -v
    => all pass

[ ] pytest tests/ -v
    => no regressions in existing tests

[ ] Code review:
    - 每个工具函数都有文档字符串
    - 参数模型都有 Field 注解
    - metadata 准确（desc, tag, side_effect_level）
```

---

## 🎯 收益验收

### 阶段二完成后，你有了什么

✅ **Action 工具完整化**

```python
# 现在可以这样用
registry = get_action_tools_registry()

# 查询所有工具
all_tools = registry.list_all()

# 按分类查询
write_tools = registry.list_by_side_effect("write")
interaction_tools = registry.list_by_tag("interaction")

# 执行工具
result = registry.call_func("ask_for_missing_input", {
    "task_name": "learning_entry",
    "missing_fields": ["email"]
})
```

✅ **工具的元数据清晰化**

每个工具都有明确的：
- 描述（`desc`）
- 分类（`tag`）
- 副作用等级（`side_effect_level`）
- 参数模型（`args_model`）
- 执行函数（`func`）

✅ **为阶段三奠基**

现在流程可以从 registry 查函数并执行，下一步只需改流程代码。

---

## 🚀 下一阶段

**阶段三** — 改造 LoopEngine，让它从 registry 调函数而不是直接调用。

这样做的好处：
- 执行层统一，便于审计
- 可以在中间层加风控、日志
- 未来可以轻松切换 mock/real executor
