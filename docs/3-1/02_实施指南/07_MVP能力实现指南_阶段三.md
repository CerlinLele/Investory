# MVP 能力实现指南 — 阶段三：流程集成

> 基于 [阶段二](./06_MVP能力实现指南_阶段二.md) 已完成  
> 本阶段：改造 LoopEngine，让它从 registry 调函数

## 🎯 阶段三目标

从**直接调用** → **通过 registry 调用**

让执行层统一，便于后续的审计、风控、mock 注入。

---

## 🛠️ 具体改动

### 步骤 3.1：在 LoopEngine 中集成 registry

**文件**：`src/investory/agent_core/runtime/react_core/loop_engine.py`

**假设当前代码**：

```python
class LoopEngine:
    def __init__(self, llm, planner, executor):
        self.llm = llm
        self.planner = planner
        self.executor = executor
    
    def run(self, state):
        while not state.is_done:
            # 规划下一步
            planned_step = self.planner.plan_next_step(state)
            
            # 执行
            if planned_step.action_type == "call_tool":
                tool_name = planned_step.metadata.get("tool_name")
                # ❌ 旧：直接执行，无法追踪
                result = some_direct_call(tool_name, args)
```

**改造后**：

```python
from investory.agent_core.runtime.tools_factory import get_action_tools_registry
from investory.agent_core.runtime.react_core.tool_registry import ToolRegistry


class LoopEngine:
    def __init__(
        self,
        llm,
        planner,
        executor,
        action_registry: ToolRegistry | None = None,
        audit_callback=None
    ):
        self.llm = llm
        self.planner = planner
        self.executor = executor
        self.action_registry = action_registry or get_action_tools_registry()
        self.audit_callback = audit_callback  # 可选的审计回调
    
    def run(self, state):
        """运行 react 循环"""
        state.session_id = state.session_id or self._generate_session_id()
        
        while not state.is_done:
            # 规划下一步
            planned_step = self.planner.plan_next_step(state)
            
            # 执行
            if planned_step.action_type == "call_tool":
                tool_name = planned_step.metadata.get("tool_name")
                tool_args = planned_step.metadata.get("args", {})
                
                # ✅ 新：通过 registry 调用，可追踪
                result = self._execute_action(
                    tool_name=tool_name,
                    args=tool_args,
                    session_id=state.session_id
                )
                
                # 更新状态
                state.tool_calls.append({
                    "tool": tool_name,
                    "args": tool_args,
                    "result": result
                })
            
            elif planned_step.action_type == "finalize":
                state.is_done = True
        
        return state
    
    def _execute_action(self, tool_name: str, args: dict, session_id: str) -> dict:
        """执行工具，中间层可挂审计/风控
        
        这是从声明到执行的关键桥梁。
        """
        # 验证工具存在
        spec = self.action_registry.get(tool_name)
        if spec is None:
            raise ValueError(f"Tool '{tool_name}' not registered")
        
        # 可选的前置钩子（风控、权限检查等）
        if self.audit_callback:
            self.audit_callback("before_action", {
                "session_id": session_id,
                "tool_name": tool_name,
                "args": args,
                "timestamp": self._now()
            })
        
        # 执行
        try:
            result = self.action_registry.call_func(tool_name, args)
            
            # 可选的后置钩子（审计日志）
            if self.audit_callback:
                self.audit_callback("after_action", {
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "result": result,
                    "status": "success",
                    "timestamp": self._now()
                })
            
            return result
        
        except Exception as e:
            # 可选的异常钩子
            if self.audit_callback:
                self.audit_callback("action_error", {
                    "session_id": session_id,
                    "tool_name": tool_name,
                    "error": str(e),
                    "timestamp": self._now()
                })
            
            raise
    
    @staticmethod
    def _generate_session_id() -> str:
        """生成会话 ID"""
        import uuid
        return str(uuid.uuid4())
    
    @staticmethod
    def _now() -> str:
        """获取当前时间戳"""
        from datetime import datetime
        return datetime.now().isoformat()
```

### 步骤 3.2：让流程也用 registry

**文件**：`src/investory/agent_core/runtime/flow/learning_entry/learning_entry_flow.py`

假设现有流程代码直接调用工具，改成从 registry 调：

```python
# 旧写法
def generate_learning_plan(state):
    # 直接调用
    plan = some_planner.plan(state.context)
    return {"plan": plan}

# 新写法
from investory.agent_core.runtime.tools_factory import get_action_tools_registry

def generate_learning_plan(state):
    registry = get_action_tools_registry()
    
    # 通过 registry 调用
    result = registry.call_func("execute_learning_task", {
        "task_name": "generate_plan",
        "payload": {"context": state.context}
    })
    
    return result
```

### 步骤 3.3：为 LoopEngine 的新功能写测试

**新文件**：`tests/test_loop_engine_with_registry.py`

```python
import pytest
from unittest.mock import Mock, MagicMock
from investory.agent_core.runtime.react_core.loop_engine import LoopEngine
from investory.agent_core.runtime.tools_factory import get_action_tools_registry, reset_action_tools_registry
from investory.agent_core.contracts.react_loop import ReactLoopState, ReactActionType


@pytest.fixture(autouse=True)
def reset_registry():
    yield
    reset_action_tools_registry()


class TestLoopEngineWithRegistry:
    """测试 LoopEngine 与 registry 的集成"""
    
    def test_loop_engine_calls_tool_via_registry(self):
        """测试 LoopEngine 通过 registry 调用工具"""
        # 准备
        llm = Mock()
        planner = Mock()
        executor = Mock()
        registry = get_action_tools_registry()
        
        engine = LoopEngine(llm, planner, executor, action_registry=registry)
        
        state = ReactLoopState(
            context="test context",
            session_id="test-session-123"
        )
        
        # 规划返回一个工具调用
        planned_step = Mock()
        planned_step.action_type = ReactActionType.CALL_TOOL
        planned_step.metadata = {
            "tool_name": "finalize",
            "args": {"summary": "Test completed"}
        }
        
        planner.plan_next_step.return_value = planned_step
        
        # 执行
        result = engine._execute_action(
            tool_name="finalize",
            args={"summary": "Test completed"},
            session_id="test-session-123"
        )
        
        # 验证
        assert result["action"] == "finalize"
        assert result["status"] == "completed"
    
    def test_loop_engine_calls_audit_callback(self):
        """测试 LoopEngine 调用审计回调"""
        registry = get_action_tools_registry()
        
        audit_calls = []
        def audit_callback(event_type, data):
            audit_calls.append({"type": event_type, "data": data})
        
        engine = LoopEngine(
            Mock(), Mock(), Mock(),
            action_registry=registry,
            audit_callback=audit_callback
        )
        
        # 执行工具
        result = engine._execute_action(
            tool_name="finalize",
            args={"summary": "Test"},
            session_id="session-123"
        )
        
        # 验证回调被调用了（before 和 after）
        assert len(audit_calls) >= 2
        assert audit_calls[0]["type"] == "before_action"
        assert audit_calls[1]["type"] == "after_action"
        assert audit_calls[1]["data"]["status"] == "success"
    
    def test_loop_engine_handles_tool_error(self):
        """测试 LoopEngine 处理工具错误"""
        registry = get_action_tools_registry()
        
        audit_calls = []
        def audit_callback(event_type, data):
            audit_calls.append({"type": event_type, "data": data})
        
        engine = LoopEngine(
            Mock(), Mock(), Mock(),
            action_registry=registry,
            audit_callback=audit_callback
        )
        
        # 调用不存在的工具
        with pytest.raises(ValueError):
            engine._execute_action(
                tool_name="nonexistent_tool",
                args={},
                session_id="session-123"
            )
        
        # 验证错误回调被调用
        error_calls = [c for c in audit_calls if c["type"] == "action_error"]
        assert len(error_calls) == 1
```

**运行**：
```bash
pytest tests/test_loop_engine_with_registry.py -v
```

### 步骤 3.4：验证现有流程仍然工作

**命令**：
```bash
pytest tests/ -v --tb=short
```

---

## 📋 阶段三完成检查清单

```
Commit: feat(loop-engine): integrate with action registry for unified execution

[ ] src/investory/agent_core/runtime/react_core/loop_engine.py
    - Add action_registry parameter to __init__
    - Add audit_callback parameter to __init__
    - Add _execute_action() method
    - Update run() to use registry for tool calls
    - Add _generate_session_id() helper
    - Add _now() helper

[ ] tests/test_loop_engine_with_registry.py (new)
    - test_loop_engine_calls_tool_via_registry
    - test_loop_engine_calls_audit_callback
    - test_loop_engine_handles_tool_error

[ ] pytest tests/test_loop_engine_with_registry.py -v
    => all pass

[ ] pytest tests/ -v
    => no regressions

[ ] Code review:
    - 错误处理完善
    - 审计回调设计清晰
    - 向后兼容（registry 可选，有默认值）
```

---

## 🎯 收益验收

### 阶段三完成后，你有了什么

✅ **执行层统一**

所有工具调用都必须经过 registry，可以在中间层进行：
- 审计日志记录
- 权限检查
- 性能监控
- 异常捕获

✅ **审计回调机制**

```python
def my_audit_callback(event_type, data):
    if event_type == "before_action":
        log_action_start(data)
    elif event_type == "after_action":
        log_action_end(data)
    elif event_type == "action_error":
        log_action_error(data)

engine = LoopEngine(
    llm, planner, executor,
    audit_callback=my_audit_callback
)
```

✅ **为阶段四奠基**

现在可以在 routing 层暴露查询 API，并且所有执行都是可追踪的。

---

## 🚀 下一阶段

**阶段四** — 在 routing 层暴露查询 API，让工具对内外可查询。
