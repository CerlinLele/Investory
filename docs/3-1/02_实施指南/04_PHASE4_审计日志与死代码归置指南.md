# Phase 4：审计日志与死代码归置 详细实施指南

## 目标

完善工具治理体系的收尾工作：
1. **审计日志** — 记录每次工具调用，为合规审计、故障排查提供完整链路
2. **死代码归置** — 明确 `ToolRegistry`/`LoopEngine` 的去留，为未来 MCP 工具做准备

---

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
    包裹执行器,记录所有工具调用日志
    
    记录内容:
    - 工具名、执行时间、状态
    - 成功/失败/异常 情况
    - 输入输出概要
    - 副作用级别和业务标签
    """
    
    def __init__(self, executor: TaskExecutor, session_id: str | None = None):
        super().__init__()
        self.executor = executor
        self.session_id = session_id or "unknown"
        self.audit_log: list[dict[str, Any]] = []
    
    def run(self, spec: TaskSpec, payload: dict[str, Any]) -> TaskResult:
        """执行工具并记录审计日志"""
        start_time = time.perf_counter()
        
        try:
            result = self.executor.run(spec, payload)
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            audit_event = {
                "session_id": self.session_id,
                "timestamp": time.time(),
                "task_name": spec.name,
                "status": "success" if result.ok else "failed",
                "duration_ms": round(duration_ms, 2),
                "side_effect_level": spec.side_effect_level,
                "tag": spec.tag,
            }
            
            if not result.ok and result.error:
                audit_event["error_type"] = result.error.get("error_type")
            
            self.audit_log.append(audit_event)
            self._log_event(audit_event)
            return result
        
        except Exception as e:
            duration_ms = (time.perf_counter() - start_time) * 1000
            
            audit_event = {
                "session_id": self.session_id,
                "timestamp": time.time(),
                "task_name": spec.name,
                "status": "exception",
                "duration_ms": round(duration_ms, 2),
                "side_effect_level": spec.side_effect_level,
                "tag": spec.tag,
                "exception_type": type(e).__name__,
            }
            
            self.audit_log.append(audit_event)
            self._log_event(audit_event, is_error=True)
            raise
    
    def _log_event(self, event: dict[str, Any], is_error: bool = False) -> None:
        """输出审计日志到标准 logger"""
        level = logging.WARNING if is_error else logging.INFO
        msg_parts = [
            f"session_id={event['session_id']}",
            f"task={event['task_name']}",
            f"status={event['status']}",
            f"duration_ms={event['duration_ms']}",
        ]
        if "error_type" in event:
            msg_parts.append(f"error={event['error_type']}")
        
        logger.log(level, "audit: " + " ".join(msg_parts), extra={"audit": event})
    
    def get_audit_log(self, task_name: str | None = None) -> list[dict]:
        """查询审计日志,可选按工具名筛选"""
        if task_name:
            return [e for e in self.audit_log if e["task_name"] == task_name]
        return self.audit_log
    
    def get_audit_summary(self) -> dict[str, Any]:
        """生成审计统计摘要"""
        if not self.audit_log:
            return {"total": 0, "by_status": {}, "by_side_effect": {}}
        
        summary = {
            "total": len(self.audit_log),
            "by_status": {},
            "by_side_effect": {},
            "by_task": {},
        }
        
        for event in self.audit_log:
            status = event["status"]
            summary["by_status"][status] = summary["by_status"].get(status, 0) + 1
            
            side_effect = event.get("side_effect_level", "unknown")
            summary["by_side_effect"][side_effect] = (
                summary["by_side_effect"].get(side_effect, 0) + 1
            )
            
            task = event["task_name"]
            if task not in summary["by_task"]:
                summary["by_task"][task] = {"count": 0, "failures": 0}
            summary["by_task"][task]["count"] += 1
            if event["status"] != "success":
                summary["by_task"][task]["failures"] += 1
        
        return summary
```

### 4.2 扩展 `routing.py` 的查询能力

在 Phase 2/3 的基础上，补充以下函数（用于分析和治理）：

```python
def get_write_tasks() -> list[TaskSpec]:
    """返回所有需要审批的工具"""
    return list_specs_by_side_effect("write")


def get_read_only_tasks() -> list[TaskSpec]:
    """返回所有纯查询工具"""
    return list_specs_by_side_effect("read")
```

### 4.3 新建 `docs/3-1/LoopEngine何时启用.md`

这是一个关键文档，明确 `ToolRegistry`/`LoopEngine` 的去向：

```markdown
# LoopEngine 何时启用 — 为 MCP 工具集成做准备

## 现状

`src/investory/agent_core/runtime/react_core/` 下的代码（ToolRegistry、LoopEngine、StepPlanner 等）**目前是死代码**，没有被任何生产流程使用。

## 为什么保留

1. **第 3-2 课(MCP 工具)的预埋**
   - MCP(Model Context Protocol) 是外部工具的标准接口
   - 未来可能需要接入「行情数据」「PDF 抓取」「市场数据 API」
   - LoopEngine 的 Protocol 设计(StepExecutor 分离) 正是为此设计

2. **架构一致性**
   - Phase 3 抽出了 ReviewPlanHandler，让规划可替换
   - LoopEngine 思想相同：执行也应该可替换
   - 两者合在一起支持「多种工具 × 多种规划策略」的组合

3. **技术债务低**
   - 保留成本很低，删除也不会解锁什么
   - 等到真正需要时再启用更安全

## 何时启用

触发条件（任选其一）：
- 需要接入真实外部工具（MCP 或 API）
- 任务规划层需要模型自由选工具（从确定性 LangGraph 升级为 ReAct）
- 审计/合规需要完全可追踪的工具调用链

启用后的演进路线：
1. **原型阶段**(1-2 周) — 集成 MCPExecutor 到 LoopEngine
2. **测试阶段**(1-2 周) — mock 测试 + 真实工具集成测试
3. **上线阶段**(2-4 周) — 灰度发布 + 审计日志完善

## 关键决策

| 时间 | 行动 | 原因 |
|------|------|------|
| 现在(3-1 课) | 保留,不启用 | Phase 1~4 专注"现有工具管理" |
| 3-2 课(MCP) | 学习,但不集成 | 理解 MCP 但还无真实需求 |
| 真实需求出现 | 启用(2-4 周) | 有用户需要时启用 |

**关键**：不是"什么时候用 LoopEngine"，而是"什么时候需要多工具编排"。当需要出现时，基础已经在这里了。
```

---

## 验证清单

### 4.4 创建 `tests/test_task_audit_logging.py`

```python
import pytest
from investory.agent_core.runtime.execution.audited_task_executor import AuditedTaskExecutor
from investory.agent_core.runtime.execution import MockTaskExecutor, get_investment_document_review_fixtures
from investory.agent_core.contracts.task_spec import TaskSpec
from investory.agent_core.contracts.result_types import TaskResult
from pydantic import BaseModel


class DummyInput(BaseModel):
    pass


class DummyOutput(BaseModel):
    pass


class TestAuditedTaskExecutor:
    """验证审计日志功能"""

    def test_audited_executor_logs_success(self):
        """审计执行器应记录成功的工具调用"""
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
        
        audited.run(spec, {})
        
        assert len(audited.audit_log) == 1
        assert audited.audit_log[0]["session_id"] == "test-123"
        assert audited.audit_log[0]["task_name"] == "test_task"
        assert audited.audit_log[0]["status"] == "success"

    def test_audited_executor_summary(self):
        """审计执行器应生成统计摘要"""
        specs = {
            "read_task": TaskSpec(
                name="read_task",
                prompt_name="read",
                input_model=DummyInput,
                output_model=DummyOutput,
                side_effect_level="read",
                tag="test",
            ),
            "write_task": TaskSpec(
                name="write_task",
                prompt_name="write",
                input_model=DummyInput,
                output_model=DummyOutput,
                side_effect_level="write",
                tag="test",
            ),
        }
        
        result = TaskResult(ok=True, task_name="test", result={})
        real_executor = MockTaskExecutor({
            "read_task": result,
            "write_task": result,
        })
        audited = AuditedTaskExecutor(real_executor)
        
        audited.run(specs["read_task"], {})
        audited.run(specs["write_task"], {})
        audited.run(specs["read_task"], {})
        
        summary = audited.get_audit_summary()
        assert summary["total"] == 3
        assert summary["by_status"]["success"] == 3
        assert summary["by_side_effect"]["read"] == 2
        assert summary["by_side_effect"]["write"] == 1
        assert summary["by_task"]["read_task"]["count"] == 2
```

**运行**:
```bash
pytest tests/test_task_audit_logging.py -v
```

---

## 改动检查清单

- [ ] 新建 `src/investory/agent_core/runtime/execution/audited_task_executor.py`
- [ ] 在 `routing.py` 新增 `get_write_tasks()` 和 `get_read_only_tasks()`
- [ ] 新建 `docs/3-1/LoopEngine何时启用.md`
- [ ] 新建 `tests/test_task_audit_logging.py`
- [ ] 运行 `pytest tests/test_task_audit_logging.py -v`
- [ ] 全量 `pytest` 无新增失败

---

## Commit Message

```
feat(governance): add audit logging and dead-code disposition

Add audit logging layer to task execution for compliance and troubleshooting.
Document LoopEngine/ToolRegistry preservation strategy for future MCP integration.

New components:
- AuditedTaskExecutor: wraps executor with audit logging
  - Records execution time, status, side_effect_level, tag
  - Generates audit summary by task/status/side_effect
  - Session correlation for request tracing

- Enhanced routing.py:
  - get_write_tasks(): convenience function for write-level tools
  - get_read_only_tasks(): convenience function for read-level tools

- Documentation:
  - LoopEngine何时启用.md: explains preservation rationale
  - When to enable (triggers: external tool integration, model autonomy)
  - 3-phase rollout plan for future MCP integration

Benefits:
- Complete audit trail for compliance/forensics
- Foundation for role-based access control
- Clear migration path for future MCP tool integration

Breaking changes: none (all additions are opt-in)

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## 预期时间投入

- 实现 AuditedTaskExecutor：20 分钟
- 写 LoopEngine 启用指南：30 分钟
- 写测试：20 分钟
- 验证：10 分钟
- **总计：1 天**

---

## 后续检查点

改完 Phase 4 后，应该：
1. ✅ `pytest tests/test_task_audit_logging.py -v` 全通过
2. ✅ AuditedTaskExecutor 能正确追踪和汇总任务执行
3. ✅ 全量 `pytest` 无新增失败
4. ✅ `docs/3-1/LoopEngine何时启用.md` 清晰说明启用时机
