# MVP 能力实现指南 — 阶段四：查询 API 暴露

> 基于 [阶段三](./07_MVP能力实现指南_阶段三.md) 已完成  
> 本阶段：在 routing 层暴露查询 API，让工具对内外可查询

## 🎯 阶段四目标

让外部（前端、管理页面、其他系统）可以通过 HTTP API 查询：
- 有哪些工具
- 工具的元数据
- 工具按分类的分布

---

## 🛠️ 具体改动

### 步骤 4.1：在 routing 层添加查询函数

**文件**：`src/investory/gateway/routing.py`

**添加以下函数**：

```python
"""工具查询和发现 API

这个模块提供工具清单查询接口，供前端和管理系统使用。
"""
from typing import Any
from investory.agent_core.runtime.tools_factory import get_action_tools_registry


def list_all_action_tools() -> list[dict]:
    """列出所有可用的 action 工具
    
    Returns:
        list: 工具清单，每个工具包含 name, desc, side_effect_level, tag
        
    Example:
        >>> tools = list_all_action_tools()
        >>> print(tools[0])
        {
            'name': 'ask_for_missing_input',
            'desc': '请求用户补充缺失信息',
            'side_effect_level': 'read',
            'tag': 'interaction'
        }
    """
    registry = get_action_tools_registry()
    return registry.list_all()


def list_action_tools_by_tag(tag: str) -> list[dict]:
    """按业务标签筛选 action 工具
    
    Args:
        tag: 业务标签，如 'interaction', 'execution', 'control'
    
    Returns:
        list: 符合条件的工具清单
        
    Example:
        >>> interaction_tools = list_action_tools_by_tag('interaction')
        >>> len(interaction_tools)  # 返回交互类工具数量
    """
    registry = get_action_tools_registry()
    return registry.list_by_tag(tag)


def list_action_tools_by_side_effect(level: str) -> list[dict]:
    """按副作用等级筛选 action 工具
    
    Args:
        level: 副作用等级，可选值：'read', 'write', 'exec'
    
    Returns:
        list: 符合条件的工具清单
        
    Example:
        >>> read_tools = list_action_tools_by_side_effect('read')
        >>> write_tools = list_action_tools_by_side_effect('write')
    """
    registry = get_action_tools_registry()
    return registry.list_by_side_effect(level)


def get_action_tool_metadata(tool_name: str) -> dict | None:
    """获取单个工具的元数据
    
    Args:
        tool_name: 工具名称
    
    Returns:
        dict: 工具元数据，包含 name, desc, side_effect_level, tag, args_schema
        None: 如果工具不存在
        
    Example:
        >>> meta = get_action_tool_metadata('finalize')
        >>> meta['desc']
        '完成流程'
    """
    registry = get_action_tools_registry()
    return registry.get_spec_dict(tool_name)


def get_action_tools_summary() -> dict:
    """获取工具清单统计摘要
    
    Returns:
        dict: 包含工具总数、按 tag 分类、按 side_effect_level 分类的统计
        
    Example:
        >>> summary = get_action_tools_summary()
        >>> summary['total']
        5
        >>> summary['by_tag']['interaction']
        2
    """
    registry = get_action_tools_registry()
    all_tools = registry.list_all()
    
    summary = {
        "total": len(all_tools),
        "by_tag": {},
        "by_side_effect": {}
    }
    
    # 统计按 tag
    for tool in all_tools:
        tag = tool.get("tag", "unknown")
        summary["by_tag"][tag] = summary["by_tag"].get(tag, 0) + 1
        
        level = tool.get("side_effect_level", "unknown")
        summary["by_side_effect"][level] = summary["by_side_effect"].get(level, 0) + 1
    
    return summary
```

### 步骤 4.2：在 FastAPI 中暴露查询端点

**文件**：`src/investory/gateway/api.py`

**添加端点**：

```python
from fastapi import APIRouter, HTTPException
from investory.gateway import routing

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


@router.get("/actions", summary="列出所有 action 工具")
def list_action_tools_endpoint():
    """列出所有可用的 action 工具
    
    Returns:
        list: 工具清单
        
    Example:
        GET /api/v1/tools/actions
        
        Response:
        [
            {
                "name": "ask_for_missing_input",
                "desc": "请求用户补充缺失信息",
                "side_effect_level": "read",
                "tag": "interaction"
            },
            ...
        ]
    """
    return routing.list_all_action_tools()


@router.get("/actions/by-tag/{tag}", summary="按 tag 筛选 action 工具")
def list_action_tools_by_tag_endpoint(tag: str):
    """按业务标签筛选 action 工具
    
    Args:
        tag: 业务标签，如 'interaction', 'execution', 'control'
    
    Returns:
        list: 符合条件的工具清单
        
    Example:
        GET /api/v1/tools/actions/by-tag/interaction
    """
    tools = routing.list_action_tools_by_tag(tag)
    if not tools:
        raise HTTPException(
            status_code=404,
            detail=f"No tools found with tag '{tag}'"
        )
    return tools


@router.get("/actions/by-side-effect/{level}", summary="按副作用等级筛选 action 工具")
def list_action_tools_by_side_effect_endpoint(level: str):
    """按副作用等级筛选 action 工具
    
    Args:
        level: 副作用等级，可选值：'read', 'write', 'exec'
    
    Returns:
        list: 符合条件的工具清单
        
    Example:
        GET /api/v1/tools/actions/by-side-effect/write
    """
    if level not in ["read", "write", "exec"]:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid side_effect_level: {level}. Must be one of: read, write, exec"
        )
    
    tools = routing.list_action_tools_by_side_effect(level)
    if not tools:
        raise HTTPException(
            status_code=404,
            detail=f"No tools found with side_effect_level '{level}'"
        )
    return tools


@router.get("/actions/{tool_name}", summary="获取单个 action 工具的元数据")
def get_action_tool_metadata_endpoint(tool_name: str):
    """获取单个工具的元数据
    
    Args:
        tool_name: 工具名称
    
    Returns:
        dict: 工具元数据
        
    Example:
        GET /api/v1/tools/actions/finalize
        
        Response:
        {
            "name": "finalize",
            "desc": "完成流程",
            "side_effect_level": "read",
            "tag": "control",
            "args_schema": {...}
        }
    """
    metadata = routing.get_action_tool_metadata(tool_name)
    if metadata is None:
        raise HTTPException(
            status_code=404,
            detail=f"Tool '{tool_name}' not found"
        )
    return metadata


@router.get("/actions/summary", summary="获取工具清单统计摘要")
def get_action_tools_summary_endpoint():
    """获取工具清单统计摘要
    
    Returns:
        dict: 统计信息
        
    Example:
        GET /api/v1/tools/actions/summary
        
        Response:
        {
            "total": 5,
            "by_tag": {
                "interaction": 2,
                "execution": 2,
                "control": 1
            },
            "by_side_effect": {
                "read": 3,
                "write": 2
            }
        }
    """
    return routing.get_action_tools_summary()


# 在应用启动时注册路由
# 在 main.py 或 app.py 中添加：
# app.include_router(router)
```

### 步骤 4.3：为新 API 写测试

**新文件**：`tests/test_tools_discovery_api.py`

```python
import pytest
from investory.gateway import routing


class TestToolsDiscoveryAPI:
    """测试工具发现 API"""
    
    def test_list_all_action_tools(self):
        """测试列出所有工具"""
        tools = routing.list_all_action_tools()
        
        assert isinstance(tools, list)
        assert len(tools) == 5  # 应该有 5 个 action 工具
        
        # 验证每个工具都有必要的字段
        for tool in tools:
            assert "name" in tool
            assert "desc" in tool
            assert "side_effect_level" in tool
            assert "tag" in tool
    
    def test_list_action_tools_by_tag(self):
        """测试按 tag 筛选"""
        interaction_tools = routing.list_action_tools_by_tag("interaction")
        
        assert len(interaction_tools) > 0
        for tool in interaction_tools:
            assert tool["tag"] == "interaction"
        
        execution_tools = routing.list_action_tools_by_tag("execution")
        assert len(execution_tools) > 0
        for tool in execution_tools:
            assert tool["tag"] == "execution"
    
    def test_list_action_tools_by_side_effect(self):
        """测试按 side_effect_level 筛选"""
        read_tools = routing.list_action_tools_by_side_effect("read")
        
        assert len(read_tools) > 0
        for tool in read_tools:
            assert tool["side_effect_level"] == "read"
        
        write_tools = routing.list_action_tools_by_side_effect("write")
        assert len(write_tools) > 0
        for tool in write_tools:
            assert tool["side_effect_level"] == "write"
    
    def test_get_action_tool_metadata(self):
        """测试获取单个工具元数据"""
        meta = routing.get_action_tool_metadata("finalize")
        
        assert meta is not None
        assert meta["name"] == "finalize"
        assert meta["desc"] == "完成流程"
        assert meta["side_effect_level"] == "read"
        assert "args_schema" in meta
    
    def test_get_action_tool_metadata_not_found(self):
        """测试获取不存在的工具"""
        meta = routing.get_action_tool_metadata("nonexistent")
        
        assert meta is None
    
    def test_get_action_tools_summary(self):
        """测试获取统计摘要"""
        summary = routing.get_action_tools_summary()
        
        assert "total" in summary
        assert summary["total"] == 5
        
        assert "by_tag" in summary
        assert "interaction" in summary["by_tag"]
        assert summary["by_tag"]["interaction"] == 2
        
        assert "by_side_effect" in summary
        assert "read" in summary["by_side_effect"]
        assert "write" in summary["by_side_effect"]
```

**运行**：
```bash
pytest tests/test_tools_discovery_api.py -v
```

### 步骤 4.4：集成端点到应用

**文件**：`src/investory/main.py` 或 `src/investory/gateway/api.py`

确保路由被注册：

```python
from fastapi import FastAPI
from investory.gateway import api

app = FastAPI()

# 注册工具查询路由
app.include_router(api.router)

# 其他路由...
```

### 步骤 4.5：验证所有改动

**命令**：
```bash
# 运行所有测试
pytest tests/ -v

# 启动应用并手动测试
uvicorn investory.main:app --reload

# 在另一个终端测试 API
curl http://localhost:8000/api/v1/tools/actions
curl http://localhost:8000/api/v1/tools/actions/by-tag/interaction
curl http://localhost:8000/api/v1/tools/actions/by-side-effect/write
curl http://localhost:8000/api/v1/tools/actions/finalize
curl http://localhost:8000/api/v1/tools/actions/summary
```

---

## 📋 阶段四完成检查清单

```
Commit: feat(routing): expose tool discovery APIs

[ ] src/investory/gateway/routing.py
    - Add list_all_action_tools()
    - Add list_action_tools_by_tag()
    - Add list_action_tools_by_side_effect()
    - Add get_action_tool_metadata()
    - Add get_action_tools_summary()

[ ] src/investory/gateway/api.py
    - Add APIRouter for /api/v1/tools
    - Add GET /api/v1/tools/actions
    - Add GET /api/v1/tools/actions/by-tag/{tag}
    - Add GET /api/v1/tools/actions/by-side-effect/{level}
    - Add GET /api/v1/tools/actions/{tool_name}
    - Add GET /api/v1/tools/actions/summary

[ ] src/investory/main.py
    - Include tools router in app

[ ] tests/test_tools_discovery_api.py (new)
    - test_list_all_action_tools
    - test_list_action_tools_by_tag
    - test_list_action_tools_by_side_effect
    - test_get_action_tool_metadata
    - test_get_action_tool_metadata_not_found
    - test_get_action_tools_summary

[ ] pytest tests/test_tools_discovery_api.py -v
    => all pass

[ ] pytest tests/ -v
    => no regressions

[ ] Manual API testing
    - curl http://localhost:8000/api/v1/tools/actions
    - curl http://localhost:8000/api/v1/tools/actions/summary
    - All endpoints respond with valid data

[ ] Code review:
    - 错误处理完善（404, 400 等）
    - API 文档清晰（docstring、example）
    - 向后兼容
```

---

## 🎯 收益验收

### 全部四个阶段完成后，你有了什么

✅ **讲座 MVP 的四个核心能力完整实现**

| 能力 | 实现位置 | 使用方式 |
|---|---|---|
| `register()` | ToolRegistry | 在 tools_factory.py 中注册所有工具 |
| `list_all()` | ToolRegistry | routing.list_all_action_tools() |
| `get_spec()` | ToolRegistry | routing.get_action_tool_metadata() |
| `get_func()` | ToolRegistry | LoopEngine._execute_action() |

✅ **工具管理完整体系**

```
registry (定义 + 存储)
    ↓
routing (查询 API)
    ↓
api (HTTP 端点)
    ↓
前端/管理页面 (可查询工具清单)

registry (查询函数)
    ↓
LoopEngine (执行工具)
    ↓
audit_callback (记录日志)
```

✅ **生产级工具治理**

- 工具有明确的元数据（描述、标签、副作用等级）
- 执行层统一（必须通过 registry）
- 可追踪（审计回调）
- 可查询（HTTP API）

---

## 📊 四阶段总结

| 阶段 | 核心改动 | 文件 | 时间 | 收益 |
|---|---|---|---|---|
| **一** | 扩展 ToolSpec 和 Registry | tool_registry.py | 0.5天 | 有了查询 API 基础 |
| **二** | 注册 action 工具函数 | tools_factory.py | 0.5天 | 工具完整化，有了执行函数 |
| **三** | LoopEngine 从 registry 调函数 | loop_engine.py | 0.5天 | 执行统一，可审计 |
| **四** | 暴露 HTTP 查询 API | routing.py, api.py | 0.5天 | 工具对外可查，运营可用 |
| **总计** | — | — | **2天** | **讲座 MVP 在 Investory 完整落地** |

---

## 🚀 后续方向

### 短期（完成后立即可做）

1. **Mock Executor** — 测试时用 MockExecutor 替换真实执行
2. **审计日志持久化** — 把审计回调的日志保存到数据库
3. **权限控制** — 在 LoopEngine 加入权限检查

### 中期（第 3-2 课）

1. **MCP 工具集成** — 外部工具怎么接入 registry
2. **工具版本管理** — 同一个工具的不同版本怎么管理

### 长期

1. **动态工具注入** — 根据意图动态决定给哪些工具给模型
2. **工具市场** — 用户可以发布、订阅工具

---

## 📚 文档导航

- **映射分析** → [02_讲座MVP与现有代码的映射与迁移.md](../01_课程参考/02_讲座MVP与现有代码的映射与迁移.md)
- **阶段一** → [05_MVP能力实现指南_阶段一.md](./05_MVP能力实现指南_阶段一.md)
- **阶段二** → [06_MVP能力实现指南_阶段二.md](./06_MVP能力实现指南_阶段二.md)
- **阶段三** → [07_MVP能力实现指南_阶段三.md](./07_MVP能力实现指南_阶段三.md)
- **阶段四** → 本文档

**下一步**：选择执行路线（A/B/C 之一），开始阶段一！
