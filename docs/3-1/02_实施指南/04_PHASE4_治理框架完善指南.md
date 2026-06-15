# Phase 4：治理框架完善 详细实施指南

## 目标
完善工具/任务管理的治理体系,统一任务调用日志,为多租户/角色权限控制、合规审计等奠基。

## 改动范围

### 4.1 新建 `runtime/execution/audited_task_executor.py`

```python
"""Audited task executor that wraps real executor with audit logging."""

import logging
import time
from typing import Any

from investory.agent_core.contracts.result_types import TaskResult
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.runtime.task_executor import TaskExecutor


logger = logging.getLogger(__name__)


class AuditedTaskExecutor(TaskExecutor):
    """
    Wrapper executor that logs all task calls for audit/compliance.
    
    Records:
    - Task name and execution time
    - Success/failure status
    - Input payload summary
    - Error details on failure
    
    Usage:
        real_executor = TaskExecutor()
        audited = AuditedTaskExecutor(real_executor, session_id="user-123")
        result = audited.run(spec, payload)
        # Logs audit event automatically
    """
    
    def __init__(self, executor: TaskExecutor, session_id: str | None = None):
        """
        Args:
            executor: the real TaskExecutor to wrap
            session_id: optional session identifier for audit correlation
        """
        super().__init__()
        self.executor = executor
        self.session_id = session_id or "unknown"
        self.audit_log: list[dict[str, Any]] = []
    
    def run(self, spec: TaskSpec, payload: dict[str, Any]) -> TaskResult:
        """Execute task and log audit event."""
        start_time = time.perf_counter()
        
        try:
            # Execute task
            result = self.executor.run(spec, payload)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log success
            audit_event = {
                "session_id": self.session_id,
                "timestamp": time.time(),
                "task_name": spec.name,
                "status": "success" if result.ok else "failed",
                "duration_ms": round(duration_ms, 2),
                "side_effect_level": spec.side_effect_level,
                "tag": spec.tag,
                "payload_keys": list(payload.keys()) if payload else [],
            }
            
            if not result.ok and result.error:
                audit_event["error_type"] = result.error.get("error_type")
                audit_event["error_message"] = result.error.get("message")
            
            self.audit_log.append(audit_event)
            
            # Log to standard logger
            self._log_task_execution(audit_event)
            
            return result
        
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            # Log exception
            audit_event = {
                "session_id": self.session_id,
                "timestamp": time.time(),
                "task_name": spec.name,
                "status": "exception",
                "duration_ms": round(duration_ms, 2),
                "side_effect_level": spec.side_effect_level,
                "tag": spec.tag,
                "exception_type": type(e).__name__,
                "exception_message": str(e),
            }
            
            self.audit_log.append(audit_event)
            self._log_task_execution(audit_event, is_error=True)
            
            raise
    
    def _log_task_execution(self, event: dict[str, Any], is_error: bool = False) -> None:
        """Log task execution to standard logger."""
        level = logging.WARNING if is_error else logging.INFO
        message_parts = [
            f"session_id={event['session_id']}",
            f"task={event['task_name']}",
            f"status={event['status']}",
            f"duration_ms={event['duration_ms']}",
            f"side_effect={event.get('side_effect_level', 'unknown')}",
        ]
        
        if "error_type" in event:
            message_parts.append(f"error={event['error_type']}")
        
        logger.log(
            level,
            "task_execution: " + " ".join(message_parts),
            extra={"audit_event": event}
        )
    
    def get_audit_log(
        self,
        task_name: str | None = None,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Query audit log.
        
        Args:
            task_name: filter by specific task (optional)
            status: filter by status (success/failed/exception, optional)
        
        Returns:
            list of matching audit events
        """
        filtered = self.audit_log
        
        if task_name:
            filtered = [e for e in filtered if e["task_name"] == task_name]
        
        if status:
            filtered = [e for e in filtered if e["status"] == status]
        
        return filtered
    
    def get_audit_summary(self) -> dict[str, Any]:
        """Get summary statistics of all recorded task executions."""
        if not self.audit_log:
            return {
                "total_tasks": 0,
                "by_status": {},
                "by_side_effect": {},
                "total_duration_ms": 0,
            }
        
        summary = {
            "total_tasks": len(self.audit_log),
            "by_status": {},
            "by_side_effect": {},
            "total_duration_ms": 0,
            "by_task": {},
        }
        
        for event in self.audit_log:
            # Count by status
            status = event["status"]
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            
            # Count by side_effect_level
            side_effect = event.get("side_effect_level", "unknown")
            summary["by_side_effect"][side_effect] = (
                summary["by_side_effect"].get(side_effect, 0) + 1
            )
            
            # Sum durations
            summary["total_duration_ms"] += event["duration_ms"]
            
            # Track per-task stats
            task = event["task_name"]
            if task not in summary["by_task"]:
                summary["by_task"][task] = {
                    "count": 0,
                    "total_duration_ms": 0,
                    "avg_duration_ms": 0,
                    "failures": 0,
                }
            
            summary["by_task"][task]["count"] += 1
            summary["by_task"][task]["total_duration_ms"] += event["duration_ms"]
            summary["by_task"][task]["avg_duration_ms"] = round(
                summary["by_task"][task]["total_duration_ms"]
                / summary["by_task"][task]["count"],
                2,
            )
            
            if event["status"] != "success":
                summary["by_task"][task]["failures"] += 1
        
        return summary
    
    def export_audit_log_csv(self, filepath: str) -> None:
        """Export audit log to CSV file for compliance/analysis."""
        import csv
        
        if not self.audit_log:
            return
        
        with open(filepath, "w", newline="") as f:
            fieldnames = list(self.audit_log[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.audit_log)
```

---

### 4.2 改动 `routing.py` — 扩展查询能力

```python
"""Enhanced task routing with governance metadata queries."""

from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.tasks import (
    FINANCE_QA_TASK,
    INSTRUMENT_BRIEF_TASK,
    LEARNING_MATERIAL_SUMMARY_TASK,
    TASKS,
)


TASK_ALIASES = {
    "qa": FINANCE_QA_TASK.name,
    "summary": LEARNING_MATERIAL_SUMMARY_TASK.name,
    "brief": INSTRUMENT_BRIEF_TASK.name,
}


class UnknownTaskTypeError(ValueError):
    """Raised when a public task type cannot be resolved to a registered task."""

    def __init__(self, task_type: str) -> None:
        self.task_type = task_type
        known_task_types = sorted({*TASK_ALIASES, *TASKS})
        known = ", ".join(known_task_types)
        super().__init__(
            f"Unknown task type '{task_type}'. Expected one of: {known}."
        )


# Existing functions (unchanged)
def resolve_task_name(task_type: str) -> str:
    """Resolve a public task type or internal task name to a registered task name."""
    normalized = task_type.strip()
    task_name = TASK_ALIASES.get(normalized, normalized)
    if task_name not in TASKS:
        raise UnknownTaskTypeError(task_type)
    return task_name


def resolve_task_spec(task_type: str) -> TaskSpec:
    """Resolve a public task type or internal task name to a TaskSpec."""
    return TASKS[resolve_task_name(task_type)]


# NEW: Governance metadata queries
def list_all_specs() -> list[TaskSpec]:
    """Return all registered TaskSpec objects."""
    return list(TASKS.values())


def list_specs_by_tag(tag: str) -> list[TaskSpec]:
    """
    Return all tasks with a specific tag.
    
    Args:
        tag: business domain tag (e.g. 'learning', 'document_review', 'risk')
    
    Returns:
        list of matching TaskSpec objects
    """
    return [spec for spec in TASKS.values() if spec.tag == tag]


def list_specs_by_side_effect(level: str) -> list[TaskSpec]:
    """
    Return all tasks with a specific side_effect_level.
    
    Args:
        level: 'read' (query only), 'write' (modifies state), or 'exec' (runs commands)
    
    Returns:
        list of matching TaskSpec objects
    """
    return [spec for spec in TASKS.values() if spec.side_effect_level == level]


def get_specs_for_tags(tags: list[str]) -> list[TaskSpec]:
    """
    Return all tasks matching any of the given tags.
    
    Args:
        tags: list of business domain tags
    
    Returns:
        list of matching TaskSpec objects (no duplicates)
    """
    result = {}
    for tag in tags:
        for spec in list_specs_by_tag(tag):
            result[spec.name] = spec
    return list(result.values())


def get_write_tasks() -> list[TaskSpec]:
    """Convenience: return all tasks that modify state."""
    return list_specs_by_side_effect("write")


def get_read_only_tasks() -> list[TaskSpec]:
    """Convenience: return all tasks that are pure queries."""
    return list_specs_by_side_effect("read")


def get_spec_metadata(task_name: str) -> dict:
    """
    Get governance metadata for a single task.
    
    Args:
        task_name: internal task name
    
    Returns:
        dict with name, side_effect_level, tag, desc
    
    Raises:
        UnknownTaskTypeError: if task not found
    """
    spec = TASKS.get(task_name)
    if spec is None:
        raise UnknownTaskTypeError(task_name)
    
    return {
        "name": spec.name,
        "prompt_name": spec.prompt_name,
        "side_effect_level": spec.side_effect_level,
        "tag": spec.tag,
        "desc": spec.desc,
        "input_model": spec.input_model.__name__,
        "output_model": spec.output_model.__name__,
    }


def validate_task_access(task_name: str, user_role: str) -> bool:
    """
    Validate if a user role can access a task (placeholder for future RBAC).
    
    Current implementation:
    - 'admin' can access all tasks
    - 'analyst' can only access 'read' tasks
    - 'unknown' role has no access
    
    Future: integrate with actual role/permission database
    """
    spec = TASKS.get(task_name)
    if spec is None:
        return False
    
    if user_role == "admin":
        return True
    
    if user_role == "analyst" and spec.side_effect_level == "read":
        return True
    
    return False


__all__ = [
    "TASK_ALIASES",
    "UnknownTaskTypeError",
    "resolve_task_name",
    "resolve_task_spec",
    "list_all_specs",
    "list_specs_by_tag",
    "list_specs_by_side_effect",
    "get_specs_for_tags",
    "get_write_tasks",
    "get_read_only_tasks",
    "get_spec_metadata",
    "validate_task_access",
]
```

---

### 4.3 新建 `docs/3-1/LoopEngine何时启用.md`

```markdown
# LoopEngine 何时启用 — 未来 MCP 工具接入路线

## 现状

`src/investory/agent_core/runtime/react_core/` 目录下有三个组件:
- `ToolRegistry`:工具注册中心
- `LoopEngine`:ReAct 循环引擎
- `StepPlanner`/`StepPolicy`/`StepExecutor`:流程分离接口

**目前状态**:这些是死代码,没有被任何 flow 导入使用。

## 为什么保留

1. **第 3-2 课(MCP 工具)的预埋**
   - MCP(Model Context Protocol)是外部工具的标准接口
   - 未来可能要接入「行情数据源」「PDF 抓取服务」「市场数据 API」
   - LoopEngine 的 Protocol 设计(`StepExecutor` 分离)正是为了支持多种执行器

2. **架构一致性**
   - 当前 Phase 3 抽出了 `ReviewPlanHandler`,目的是让规划可替换
   - LoopEngine 的设计思想相同:执行也应该可替换
   - 两者合在一起能支持「多种工具类型 × 多种规划策略」的组合

3. **技术债务低**
   - 代码在 core package 下,不会干扰现有业务流
   - 删除成本低,保留成本也低
   - 等到真正需要时再启用更安全

## 何时启用

### 触发条件(任选其一)

- **条件 A**:需要接入第一个外部工具(MCP 或其他)
  - 示例:「实时行情数据源」「PDF 抓取服务」
  - 此时用 `LoopEngine + MockExecutor` 做测试,再用 `MCP Executor` 上生产

- **条件 B**:任务规划层需要模型自由选择工具(从 LangGraph 确定性图升级)
  - 示例:用户问「给我这支基金的信息和实时行情对比」
  - 此时需要 ReAct 来动态决定「先查基金信息、再查行情数据」

- **条件 C**:审计/合规层要求工具调用完全可追踪和可控
  - 示例:「金融服务必须记录每一次数据查询、执行者、时间、结果」
  - 此时 `StepExecutor` 的包裹机制很有用

### 启用的 3 个阶段

#### 阶段 1:原型(1-2 周)
```python
# 目标:验证 LoopEngine 是否真的能承载新工具类型

from investory.agent_core.runtime.react_core.loop_engine import LoopEngine
from investory.agent_core.runtime.execution.mock_task_executor import MockExecutor

# 新增一个 real_time_market_data_executor.py(调真实 API)
market_executor = RealTimeMarketDataExecutor(api_key="...")

loop = LoopEngine(
    planner=ModelPlanner(...),     # 模型自主选工具
    policy=BasicPolicy(...),       # 基础校验
    executor=market_executor,      # 调用 API
)

# 测试:mock 行情数据,验证 loop 逻辑
loop = LoopEngine(
    planner=...,
    policy=...,
    executor=MockExecutor({"get_market_data": {...}})
)
```

#### 阶段 2:与现有 flow 集成(1-2 周)
```python
# 目标:让新工具的调用结果流入投资文档审查流程

# 当前结构:
# LearningEntryFlow / InvestmentDocumentReviewFlow
#   └─ uses: TaskExecutor(runs LLM tasks)

# 升级到:
# ReAct LoopEngine (for market data queries)
#   └─ executor: MCP Tools
#      → 结果流入 TaskExecutor context
#   ↓
# InvestmentDocumentReviewFlow (enriched with live data)
#   └─ uses: TaskExecutor
```

#### 阶段 3:生产(2-4 周)
- 审计日志完善(AuditedExecutor 已有)
- 角色权限控制(routing.validate_task_access 的扩展)
- 灰度发布(新工具限制到 beta 用户)

---

## 迁移清单

启用时按以下步骤进行:

- [ ] **了解阶段**
  - 理解 MCP 协议(阅读 anthropic/mcp 官方文档)
  - 确定第一个外部工具(e.g., 行情数据)
  - 设计 MCP adapter

- [ ] **实现阶段**
  - 实现 `MCPExecutor` 类(extends `StepExecutor`)
  - 在 LoopEngine 中集成 MCPExecutor
  - 写 mock 和集成测试

- [ ] **测试阶段**
  - 用 mock 工具验证 LoopEngine 逻辑
  - 用真实 MCP 工具做端到端测试
  - 压力测试(并发工具调用)

- [ ] **上线阶段**
  - 灰度:只给 10% 用户启用
  - 审计:完整记录每一次工具调用
  - 文档:用户指南、故障排查

---

## 设计参考

当启用时,参考这些代码位置了解现有设计:

- `loop_engine.py:LoopEngine` — 主循环逻辑
- `loop_engine.py:StepPlanner/StepPolicy/StepExecutor` — Protocol 定义
- `tool_registry.py:ToolRegistry` — 工具注册和查询
- `execution/mock_task_executor.py` — MockExecutor 参考实现
- `execution/audited_task_executor.py` — 审计包裹参考

---

## 常见问题

**Q: 为什么不现在启用?**
A: 没有真实需求。现在启用是过度工程。当用户明确需要「实时数据」或「模型自主选工具」时再启用。

**Q: 能和现有 flow 共存吗?**
A: 可以。LoopEngine 和当前的 LangGraph flow 是正交的。可以并行运行。

**Q: 删除 LoopEngine 会更简洁吗?**
A: 短期是。但长期看,Phase 3~4 做完后,整个系统有了统一的「可替换 handler」思路。LoopEngine 是这个思路在「多工具场景」下的体现。删除反而会在未来后悔。

**Q: MCP 一定要用 LoopEngine 吗?**
A: 不一定。MCP 工具也可以包裹成 LLM 任务直接塞进 TaskExecutor。但用 LoopEngine 的好处是「模型可以自主决定调哪个工具」,而不是人工在 flow 里写死。

---

## 总结

| 时间点 | 建议 | 原因 |
|--------|------|------|
| 现在(第 3-1 课) | 保留,不启用 | Phase 1~4 专注在"现有工具管理"优化 |
| 第 3-2 课(MCP 工具) | 学习,但仍保留 | 理解 MCP 但还不集成 |
| 真实需求出现 | 启用(2~4 周) | 有用户明确需要时启用 |
| 3~6 个月后 | 评估 | 根据使用情况决定是否深化 |

**关键:**不是"什么时候用 LoopEngine",而是"什么时候需要多工具编排"。当需要出现时,LoopEngine 已经在这里了。
```

---

### 4.4 新建测试 `tests/test_task_governance.py`

```python
"""Tests for task governance metadata and access control."""

import pytest

from investory.gateway.routing import (
    list_all_specs,
    list_specs_by_tag,
    list_specs_by_side_effect,
    get_write_tasks,
    get_read_only_tasks,
    get_spec_metadata,
    validate_task_access,
)


class TestTaskGovernanceQueries:
    """Test task governance metadata queries."""
    
    def test_list_all_specs_returns_9_tasks(self):
        """Should return all 9 registered tasks."""
        specs = list_all_specs()
        assert len(specs) == 9
    
    def test_list_specs_by_tag_learning(self):
        """Should return 3 learning tasks."""
        specs = list_specs_by_tag("learning")
        assert len(specs) == 3
        assert all(spec.tag == "learning" for spec in specs)
    
    def test_list_specs_by_tag_document_review(self):
        """Should return 5 document review tasks."""
        specs = list_specs_by_tag("document_review")
        assert len(specs) == 5
        assert all(spec.tag == "document_review" for spec in specs)
    
    def test_list_specs_by_tag_risk(self):
        """Should return 2 risk tasks."""
        specs = list_specs_by_tag("risk")
        assert len(specs) == 2
        assert all(spec.tag == "risk" for spec in specs)
    
    def test_list_specs_by_side_effect_read(self):
        """Should return 8 read-level tasks."""
        specs = list_specs_by_side_effect("read")
        assert len(specs) == 8
        assert all(spec.side_effect_level == "read" for spec in specs)
    
    def test_list_specs_by_side_effect_write(self):
        """Should return 1 write-level task."""
        specs = list_specs_by_side_effect("write")
        assert len(specs) == 1
        assert specs[0].name == "investment_document_risk_assessment"
    
    def test_get_write_tasks_shortcut(self):
        """Shortcut function should return write tasks."""
        tasks = get_write_tasks()
        assert len(tasks) == 1
        assert tasks[0].side_effect_level == "write"
    
    def test_get_read_only_tasks_shortcut(self):
        """Shortcut function should return read tasks."""
        tasks = get_read_only_tasks()
        assert len(tasks) == 8
        assert all(t.side_effect_level == "read" for t in tasks)
    
    def test_get_spec_metadata(self):
        """Should return complete metadata for a task."""
        metadata = get_spec_metadata("finance_qa")
        assert metadata["name"] == "finance_qa"
        assert metadata["side_effect_level"] == "read"
        assert metadata["tag"] == "learning"
        assert "desc" in metadata
        assert "Answer" in metadata["desc"]


class TestTaskAccessControl:
    """Test role-based access control."""
    
    def test_admin_can_access_all_tasks(self):
        """Admin role should access all tasks."""
        assert validate_task_access("finance_qa", "admin")
        assert validate_task_access("investment_document_risk_assessment", "admin")
    
    def test_analyst_can_access_read_tasks(self):
        """Analyst role should only access read-level tasks."""
        assert validate_task_access("finance_qa", "analyst")
        assert validate_task_access("investment_document_extract", "analyst")
    
    def test_analyst_cannot_access_write_tasks(self):
        """Analyst role should not access write-level tasks."""
        assert not validate_task_access("investment_document_risk_assessment", "analyst")
    
    def test_unknown_role_has_no_access(self):
        """Unknown role should have no access."""
        assert not validate_task_access("finance_qa", "unknown")
    
    def test_invalid_task_has_no_access(self):
        """Non-existent task should deny all access."""
        assert not validate_task_access("fake_task", "admin")


class TestAuditedTaskExecutor:
    """Test audited task executor."""
    
    def test_audited_executor_logs_calls(self):
        """Audited executor should track all task calls."""
        from investory.agent_core.runtime.execution.audited_task_executor import (
            AuditedTaskExecutor,
        )
        from investory.agent_core.runtime.execution.mock_task_executor import (
            MockTaskExecutor,
        )
        from investory.agent_core.contracts.result_types import TaskResult
        from investory.agent_core.contracts.task_spec import TaskSpec
        from pydantic import BaseModel
        
        # Create mock fixture
        class DummyInput(BaseModel):
            pass
        
        class DummyOutput(BaseModel):
            pass
        
        spec = TaskSpec(
            name="test_task",
            prompt_name="test",
            input_model=DummyInput,
            output_model=DummyOutput,
            side_effect_level="read",
            tag="test",
        )
        
        result = TaskResult(ok=True, task_name="test_task", result={})
        real_executor = MockTaskExecutor({"test_task": result})
        audited = AuditedTaskExecutor(real_executor, session_id="test-123")
        
        # Run task
        audited.run(spec, {})
        
        # Check audit log
        assert len(audited.audit_log) == 1
        assert audited.audit_log[0]["session_id"] == "test-123"
        assert audited.audit_log[0]["task_name"] == "test_task"
        assert audited.audit_log[0]["status"] == "success"
    
    def test_audited_executor_summary(self):
        """Audited executor should generate useful summary."""
        from investory.agent_core.runtime.execution.audited_task_executor import (
            AuditedTaskExecutor,
        )
        from investory.agent_core.runtime.execution.mock_task_executor import (
            MockTaskExecutor,
        )
        from investory.agent_core.contracts.result_types import TaskResult
        from investory.agent_core.contracts.task_spec import TaskSpec
        from pydantic import BaseModel
        
        class DummyInput(BaseModel):
            pass
        
        class DummyOutput(BaseModel):
            pass
        
        specs = {
            "task_read": TaskSpec(
                name="task_read",
                prompt_name="read",
                input_model=DummyInput,
                output_model=DummyOutput,
                side_effect_level="read",
                tag="test",
            ),
            "task_write": TaskSpec(
                name="task_write",
                prompt_name="write",
                input_model=DummyInput,
                output_model=DummyOutput,
                side_effect_level="write",
                tag="test",
            ),
        }
        
        result = TaskResult(ok=True, task_name="test", result={})
        real_executor = MockTaskExecutor({
            "task_read": result,
            "task_write": result,
        })
        audited = AuditedTaskExecutor(real_executor)
        
        # Run multiple tasks
        audited.run(specs["task_read"], {})
        audited.run(specs["task_write"], {})
        audited.run(specs["task_read"], {})
        
        # Check summary
        summary = audited.get_audit_summary()
        assert summary["total_tasks"] == 3
        assert summary["by_status"]["success"] == 3
        assert summary["by_side_effect"]["read"] == 2
        assert summary["by_side_effect"]["write"] == 1
        assert summary["by_task"]["task_read"]["count"] == 2
```

---

## 改动检查清单

- [ ] 新建 `src/investory/agent_core/runtime/execution/audited_task_executor.py`
- [ ] 改动 `src/investory/gateway/routing.py`:新增 8 个查询函数
- [ ] 新建 `docs/3-1/LoopEngine何时启用.md`
- [ ] 新建 `tests/test_task_governance.py`
- [ ] 运行 `pytest tests/test_task_governance.py -v`
- [ ] 运行 `pytest` 全量测试,无新增失败
- [ ] 验证 AuditedTaskExecutor 能正确生成日志和统计

---

## Commit Message

```
feat(governance): complete task governance framework

Add audit logging and access control to task execution layer.
Provides foundation for compliance, multi-tenancy, and audit trails.

New components:
- AuditedTaskExecutor: wraps TaskExecutor with audit logging
  - Records execution time, status, side_effect_level, tag
  - Generates summaries by task/status/side_effect
  - Exports audit logs to CSV for compliance
  - Tracks session_id for request correlation

- Enhanced routing.py queries:
  - get_specs_for_tags(tags): batch tag queries
  - get_write_tasks() / get_read_only_tasks(): shortcuts
  - get_spec_metadata(): complete metadata for single task
  - validate_task_access(task_name, user_role): role-based control

- LoopEngine enablement guide:
  - Documents why LoopEngine is preserved
  - When to enable (triggers: external tool integration, model autonomy, compliance)
  - 3-phase rollout plan (prototype → integration → production)
  - References for MCP tool integration (Phase 3-2 prerequisite)

Test coverage:
- test_task_governance.py: all governance queries tested
- Access control: role-based filtering for admin/analyst
- Audit logging: execution tracking, summary generation

Benefits:
- Complete audit trail for compliance/forensics
- Foundation for role-based access control
- Governance metrics (tasks by type, execution time, failure rates)
- Clear migration path for future MCP tool integration

Breaking changes: none (queries are additive)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## 预期时间投入

- 实现 AuditedTaskExecutor:30 分钟
- 扩展 routing.py 查询:15 分钟
- 写 LoopEngine 启用指南:30 分钟
- 写测试:30 分钟
- 验证:15 分钟
- **总计:1 天**

---

## 后续检查点

改完 Phase 4 后,应该:
1. ✅ `pytest tests/test_task_governance.py -v` 全通过
2. ✅ `AuditedTaskExecutor` 能正确追踪和汇总任务执行
3. ✅ `validate_task_access("task_name", "admin")` 返回 True
4. ✅ `validate_task_access("write_task", "analyst")` 返回 False
5. ✅ 全量 `pytest` 其它测试不新增失败
6. ✅ `docs/3-1/LoopEngine何时启用.md` 清晰说明了启用时机

---

## 后续工作(P3,不在 Phase 4 范围)

- 数据库集成:把 audit log 持久化到 PostgreSQL
- 权限系统:从硬编码规则升级到数据库驱动的 RBAC
- 审计 API:提供端点供运营查询任务执行历史
- 告警集成:失败率超过阈值时触发告警
- 文档完善:运营手册、故障排查、SOP
