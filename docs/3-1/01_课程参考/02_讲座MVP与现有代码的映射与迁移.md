# 讲座 MVP × Investory 现有代码：映射与迁移计划

## 🎯 核心问题

讲座讲了"工具注册中心 MVP"的四个核心能力，Investory 已经有 `ToolRegistry` 了。问题是：

1. **讲座的 MVP 有什么能力？** — register、list_all、list_specs、get_func
2. **Investory 现有代码实现了哪些？** — 部分（但不完整）
3. **缺口在哪里？** — 执行函数、发现查询
4. **如何分阶段补齐？** — 与现有 4-phase 计划如何融合

本文档给出明确的映射和迁移路线。

---

## 📊 讲座 MVP 的四个核心能力

### 1. `register(id, desc, schema, func)` — 集中声明

**意义**：把"工具是什么"和"工具怎么运行"集中到一个中心，而不是散落各处。

```python
# 讲座 MVP 示例
registry.register(
    tool_id="query_leave",
    desc="查询员工剩余年假天数",
    input_schema={"employee_id": "str"},
    func=query_leave,
    side_effect_level="read"
)
```

**四个输入**：
- `id`：工具的唯一标识符
- `desc`：工具做什么（给模型和人看）
- `schema`：工具接受什么参数
- `func`：工具的执行函数（可被调用）
- `side_effect_level`（扩展）：读/写等级（策略挂钩点）

### 2. `list_all()` — 全量清单

**意义**：系统想知道"我有哪些工具"，不需要逐个文件翻，一个函数全部返回。

```python
specs = registry.list_all()
# 返回：
# [
#   { id: "query_leave", desc: "...", schema: {...}, side_effect_level: "read" },
#   { id: "query_approval", desc: "...", schema: {...}, side_effect_level: "read" },
#   ...
# ]
```

**衍生**：按条件筛选的列表
- `list_by_side_effect("write")`：只要写操作的工具
- `list_by_tag("document_query")`：只要文档查询相关的工具

### 3. `list_specs(id)` — 按 ID 查询声明

**意义**：给定一个工具 ID，返回它的"能力声明"（不含执行函数）。

```python
spec = registry.get_spec("query_leave")
# 返回：
# {
#   id: "query_leave",
#   desc: "查询员工剩余年假天数",
#   schema: {"employee_id": "str"},
#   side_effect_level: "read"
# }
```

**不返回** `func` — 原因是有时只想看工具能做什么，不想执行。

### 4. `get_func(id)` — 按 ID 获取执行函数

**意义**：给定一个工具 ID，返回它的执行函数，可以被调用。

```python
func = registry.get_func("query_leave")
result = func("EMP_001")
# 返回：{ "employee_id": "EMP_001", "days_remaining": 12 }
```

**关键**：这是**从声明到执行的桥梁**——模型说"调这个工具"，系统从 registry 拿函数执行。

---

## 🔍 Investory 现有 ToolRegistry 分析

### 现状代码 (src/investory/agent_core/runtime/react_core/tool_registry.py)

```python
@dataclass(slots=True)
class ToolSpec:
    name: str
    args_model: type[BaseModel]           # ← 类似 schema
    requires_confirmation: bool = False
    allowed_task_names: frozenset[str] = ALL_TASKS_ALLOWED


class ToolRegistry:
    def __init__(self) -> None:
        self._specs: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._specs[spec.name] = spec

    def validate(self, tool_name, args, task_name) -> ToolValidationResult:
        # 检查工具是否注册、参数是否有效、任务是否允许
        # → 这是**验证**，不是**执行**
```

### 现有代码实现了什么

| 讲座 MVP 能力 | Investory 现状 | 对标度 |
|---|---|---|
| `register(spec)` | ✅ 有，但`ToolSpec`不含`func`和`desc` | 60% |
| `list_all()` | ❌ 没有。没有方法返回全部工具清单 | 0% |
| `get_spec(id)` | ✅ 有`get(name)`，但不返回 spec 的完整信息 | 50% |
| `get_func(id)` | ❌ 没有。`ToolSpec`根本不存`func` | 0% |
| **验证层** | ✅ 很强。`validate()` 做了权限、参数、确认检查 | — |
| **执行层** | ❌ 缺失。`ToolRegistry`只做检查，不执行 | — |

### 关键缺口

1. **`ToolSpec` 不存执行函数** — 只有元数据（名称、参数模型），没有 `func`
2. **没有查询 API** — `list_all()`, `list_by_tag()` 等全部缺失
3. **没有执行 API** — `call_func(id, args)` 也缺失
4. **现有 actions 是 Enum** — `investory_actions.py` 用硬编码的 enum，没注册到 registry

---

## 🔗 与 LangChain/LangGraph 的对比

### LangChain 怎么做

```python
from langchain_core.tools import tool

@tool
def query_leave(employee_id: str) -> dict:
    """查询员工剩余年假天数"""
    return {"employee_id": employee_id, "days_remaining": 12}

# 特点：
# - 用装饰器自动声明（desc 来自 docstring）
# - schema 自动推导（从类型注解）
# - 没有全局 registry，工具就是对象列表
tools = [query_leave, query_approval, ...]
llm_with_tools = llm.bind_tools(tools)
```

**缺点**：工具分散，要查一个工具得翻源码；没有统一的策略挂钩点（如副作用等级）。

### LangGraph 怎么做

```python
from langgraph.prebuilt import ToolNode

tool_node = ToolNode(tools)
# 内部维护 tools_by_name dict，dispatch 时按名字查表
```

**相当于**讲座 MVP 的 `get_func(id)` 部分。

### Investory 现在的位置

介于二者之间：
- ✅ 有统一的 registry（比 LangChain 好）
- ✅ 有验证和权限控制（LangGraph 没有）
- ❌ 但没有**执行函数的查询和调用**（都有，但不联动）
- ❌ 没有**发现接口**（工具清单查询）

---

## 🗺️ 缺口详解与补齐方案

### 缺口 1：ToolSpec 不存 func

**现在**：
```python
@dataclass
class ToolSpec:
    name: str
    args_model: type[BaseModel]
    requires_confirmation: bool
    allowed_task_names: frozenset[str]
    # ← 没有 func、desc、side_effect_level 等
```

**应该**：
```python
from typing import Callable

@dataclass
class ToolSpec:
    name: str
    args_model: type[BaseModel]
    func: Callable  # ← 执行函数
    desc: str = ""  # ← 工具描述
    side_effect_level: str = "read"  # ← 读/写等级
    tag: str = ""  # ← 业务标签
    requires_confirmation: bool = False
    allowed_task_names: frozenset[str] = ALL_TASKS_ALLOWED
```

**影响**：
- 现有代码都能用（新字段有默认值）
- 可以执行工具了（有 func）

### 缺口 2：没有查询 API

**现在**：
```python
# 没有这些方法
registry.list_all()
registry.list_by_tag("document_query")
registry.list_by_side_effect("write")
```

**应该加**：
```python
class ToolRegistry:
    def list_all(self) -> list[dict]:
        """返回所有工具的能力声明"""
        return [self._spec_to_dict(spec) for spec in self._specs.values()]
    
    def list_by_tag(self, tag: str) -> list[dict]:
        """按 tag 筛选"""
        return [self._spec_to_dict(s) for s in self._specs.values() if s.tag == tag]
    
    def list_by_side_effect(self, level: str) -> list[dict]:
        """按副作用等级筛选"""
        return [self._spec_to_dict(s) for s in self._specs.values() if s.side_effect_level == level]
```

### 缺口 3：没有执行 API

**现在**：registry 存了工具声明，但"怎么执行"是外部的事。

**应该加**：
```python
class ToolRegistry:
    def call_func(self, tool_name: str, args: dict[str, Any]) -> Any:
        """从这里执行工具，可以在这里挂审计/日志"""
        spec = self.get(tool_name)
        if spec is None:
            raise ToolNotFoundError(tool_name)
        
        # 可以在这里加审计日志、风控、限流等
        result = spec.func(**args)
        return result
```

### 缺口 4：现有 actions 没注册到 registry

**现在** (`investory_actions.py`)：
```python
class InvestoryAction(str, Enum):
    ASK_FOR_MISSING_INPUT = "ask_for_missing_input"
    REFUSE_AND_REDIRECT = "refuse_and_redirect"
    EXECUTE_LEARNING_TASK = "execute_learning_task"
    CALL_TOOL = "call_tool"
    FINALIZE = "finalize"
```

**问题**：这是 enum，没有与 registry 关联；不知道每个 action 的执行函数是什么。

**应该**：定义实际的工具函数，注册到 registry：

```python
def ask_for_missing_input(task_name: str, missing_fields: list[str]) -> dict:
    """请求用户补充缺失信息"""
    return {"action": "ask", "task": task_name, "fields": missing_fields}

def execute_learning_task(task_name: str, payload: dict) -> dict:
    """执行学习任务"""
    executor = get_task_executor(task_name)
    return executor.run(payload)

# 注册
registry.register(ToolSpec(
    name="ask_for_missing_input",
    desc="请求用户补充缺失信息",
    args_model=AskForMissingInputArgs,
    func=ask_for_missing_input,
    side_effect_level="read",
    tag="interaction"
))

registry.register(ToolSpec(
    name="execute_learning_task",
    desc="执行学习任务",
    args_model=ExecuteLearningTaskArgs,
    func=execute_learning_task,
    side_effect_level="write",
    tag="execution"
))
```

---

## 📋 分阶段补齐计划

### 阶段一：扩展 ToolSpec 和 Registry 的基础设施（对标现有 Phase 1）

**改动**：
1. 在 `ToolSpec` 加 `func`、`desc`、`side_effect_level`、`tag` 四个字段（都有默认值，向后兼容）
2. 在 `ToolRegistry` 加 `list_all()`、`list_by_tag()`、`list_by_side_effect()`、`get_func()`
3. 更新现有的 `register()` 调用（如果有的话）

**文件**：
- `src/investory/agent_core/runtime/react_core/tool_registry.py` (改)

**时间**：0.5 天

**验证**：
```bash
pytest tests/test_tool_registry_enhanced.py -v
```

---

### 阶段二：把现有 actions 改成真实工具函数，注册到 registry（对标现有 Phase 2）

**改动**：
1. 在 `investory_actions.py` 定义真实的工具函数（不再是 enum）
2. 给每个函数定义 Pydantic 参数模型（`args_model`）
3. 创建 registry 实例，注册所有工具
4. 导出工具列表供流程使用

**文件**：
- `src/investory/agent_core/runtime/flow/learning_entry/investory_actions.py` (改)
- `src/investory/agent_core/runtime/react_core/tools_registry_factory.py` (新)

**时间**：0.5 天

**验证**：
```bash
pytest tests/test_investory_actions_registry.py -v
```

---

### 阶段三：在流程中集成 registry 的执行 API（对标现有 Phase 3）

**改动**：
1. 在 `LoopEngine` 或相关地方，改成从 registry 调函数，而不是直接调用
2. 这样可以在中间层加审计、风控等

**文件**：
- `src/investory/agent_core/runtime/react_core/loop_engine.py` (改)

**时间**：0.5 天

**验证**：
```bash
pytest tests/test_loop_engine_with_registry.py -v
```

---

### 阶段四：补充查询 API 并集成到 routing 层（对标现有 Phase 4）

**改动**：
1. 在 `gateway/routing.py` 暴露 `list_by_tag()`、`list_by_side_effect()` 等查询函数
2. 可以让前端或管理页面查询"我有哪些工具、分别是读/写"

**文件**：
- `src/investory/gateway/routing.py` (改)

**时间**：0.5 天

**验证**：
```bash
pytest tests/test_tool_discovery_api.py -v
```

---

## 🎯 与现有 4-phase 计划的融合

现有的 4-phase 计划讲的是"能力台账、工具发现、访问控制、审计日志"。本文档讲的是"讲座 MVP 四个能力"如何在 Investory 落地。两者其实**不矛盾，而是互补**：

| 本文档的阶段 | 讲座 MVP 能力 | 现有 4-phase 的对标 | 收益 |
|---|---|---|---|
| 阶段一 | register + 查询 API 基础 | Phase 1 (能力台账) | ToolRegistry 有了完整的元数据和查询 |
| 阶段二 | register 具体工具函数 | Phase 1 续 (填充台账) | 每个 action 都有对应的函数和元数据 |
| 阶段三 | get_func + call_func 执行 | Phase 4 (审计) | 执行可被追踪和控制 |
| 阶段四 | list_all + list_by_* 查询 | Phase 2 (工具发现) | 工具对内外可查询 |

**实施建议**：
- **先做本文档的阶段一+二**（为 registry 打基础、填充工具）
- 然后可以并行做"现有 4-phase 的 Phase 1~2"（能力台账、工具发现）
- 最后做"阶段三+四"（执行、审计、查询）

---

## 📝 代码示例对比

### 讲座 MVP 风格

```python
# 讲座 MVP 的风格
registry = ToolRegistry()
registry.register("query_leave", "查询年假", {"employee_id": "str"}, 
                  query_leave, side_effect_level="read")
registry.register("query_approval", "查询审批", {"request_id": "str"}, 
                  query_approval, side_effect_level="read")

# 查询
specs = registry.list_all()
func = registry.get_func("query_leave")
result = func("EMP_001")
```

### Investory 改造后的风格

```python
# 参数模型
class QueryLeaveArgs(BaseModel):
    employee_id: str

class QueryApprovalArgs(BaseModel):
    request_id: str

# 工具函数
def query_leave(employee_id: str) -> dict:
    return {"employee_id": employee_id, "days_remaining": 12}

def query_approval(request_id: str) -> dict:
    return {"request_id": request_id, "status": "审批中"}

# 注册
registry = ToolRegistry()
registry.register(ToolSpec(
    name="query_leave",
    desc="查询员工剩余年假天数",
    args_model=QueryLeaveArgs,
    func=query_leave,
    side_effect_level="read",
    tag="query"
))

# 查询和执行
specs = registry.list_all()
result = registry.call_func("query_leave", {"employee_id": "EMP_001"})
```

---

## ✅ 完成标志

### 全部阶段完成后

- ✅ `ToolSpec` 有 `func`, `desc`, `side_effect_level`, `tag`
- ✅ `ToolRegistry` 有 `list_all()`, `list_by_tag()`, `list_by_side_effect()`, `call_func()`
- ✅ 所有 investory_actions 都注册到 registry，且有执行函数
- ✅ LoopEngine 从 registry 调函数（可追踪、可控制）
- ✅ gateway/routing 暴露查询 API，可查看工具清单
- ✅ 讲座 MVP 的四个核心能力在 Investory 完整实现

---

## 🚀 建议的开始方式

1. **先读本文档**（15 分钟）— 理解讲座 MVP 和现有代码的缺口
2. **做阶段一**（0.5 天）— 扩展 ToolSpec 和 Registry API
3. **做阶段二**（0.5 天）— 注册现有 actions 成工具函数
4. **反馈**后决定是否继续阶段三、四

---

## 📞 FAQ

### Q: 讲座 MVP 的 `side_effect_level` 和现有代码的 `requires_confirmation` 有什么区别？

**A**: 它们解决的是同一个问题（"工具是否需要确认"），但粒度不同：
- `requires_confirmation`：简单的是/否
- `side_effect_level`：分级的（read/write/exec），可以有更灵活的策略

建议：保留 `requires_confirmation`（用于权限检查），新增 `side_effect_level`（用于策略挂钩）。

### Q: 现有代码有没有地方已经在调用工具函数了？

**A**: 有。在各个流程里（如 `learning_entry_flow.py`, `document_review_flow.py`）直接调函数。阶段三会把这些改成通过 registry 调。

### Q: 是不是一定要改成 Pydantic 参数模型？

**A**: 是。因为现有 ToolRegistry 的 `args_model` 就是 Pydantic 的 `BaseModel`，这样才能统一验证。

---

**关键点**：讲座 MVP 不复杂，就四个能力。Investory 现有代码其实大部分都有了（registry、验证），只是**没有完整地连接起来**。按阶段补齐即可。
