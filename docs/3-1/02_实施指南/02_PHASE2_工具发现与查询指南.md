# Phase 2：工具发现与查询 详细实施指南

## 目标

在 Phase 1 的元数据基础上，给 `routing.py` 补充查询接口，让系统能够：
- 按业务分类（tag）发现工具
- 按影响范围（side_effect_level）筛选工具
- 统一查询工具能力清单

这是"工具对内可查"的基础。

---

## 改动范围

### 2.1 扩展 `routing.py` 的查询函数

现有的 `routing.py` 只有 `resolve_task_spec()` 做精确查询。需要新增以下查询函数：

```python
def list_all_specs() -> list[TaskSpec]:
    """返回全量工具 TaskSpec"""
    return list(TASKS.values())


def list_specs_by_tag(tag: str) -> list[TaskSpec]:
    """按业务标签筛选工具"""
    return [spec for spec in TASKS.values() if spec.tag == tag]


def list_specs_by_side_effect(level: str) -> list[TaskSpec]:
    """按副作用级别筛选工具"""
    return [spec for spec in TASKS.values() if spec.side_effect_level == level]


def get_spec_metadata(task_name: str) -> dict:
    """获取单个工具的完整元数据"""
    spec = TASKS.get(task_name)
    if spec is None:
        raise UnknownTaskTypeError(task_name)
    return {
        "name": spec.name,
        "side_effect_level": spec.side_effect_level,
        "tag": spec.tag,
        "desc": spec.desc,
    }


# 便利函数
def list_read_only_tasks() -> list[TaskSpec]:
    """返回所有纯查询工具"""
    return list_specs_by_side_effect("read")


def list_write_tasks() -> list[TaskSpec]:
    """返回所有需要审批的工具"""
    return list_specs_by_side_effect("write")


def get_specs_for_tags(tags: list[str]) -> list[TaskSpec]:
    """获取多个标签的工具并集"""
    result = {}
    for tag in tags:
        for spec in list_specs_by_tag(tag):
            result[spec.name] = spec
    return list(result.values())
```

---

## 验证清单

### 2.2 创建 `tests/test_tool_discovery.py`

```python
import pytest
from investory.agent_core.tasks import TASKS, FINANCE_QA_TASK
from investory.gateway.routing import (
    list_all_specs,
    list_specs_by_tag,
    list_specs_by_side_effect,
    get_spec_metadata,
    list_read_only_tasks,
    list_write_tasks,
    get_specs_for_tags,
)


class TestToolDiscovery:
    """验证工具发现和查询接口"""

    def test_list_all_specs_returns_9_tasks(self):
        """list_all_specs 应返回全部 9 个工具"""
        specs = list_all_specs()
        assert len(specs) == 9
        spec_names = {spec.name for spec in specs}
        assert spec_names == set(TASKS.keys())

    def test_list_specs_by_tag_learning(self):
        """list_specs_by_tag("learning") 应返回 3 个学习类工具"""
        learning_specs = list_specs_by_tag("learning")
        assert len(learning_specs) == 3
        assert all(spec.tag == "learning" for spec in learning_specs)

    def test_list_specs_by_tag_document_review(self):
        """list_specs_by_tag("document_review") 应返回 5 个文档审查工具"""
        doc_specs = list_specs_by_tag("document_review")
        assert len(doc_specs) == 5

    def test_list_specs_by_tag_risk(self):
        """list_specs_by_tag("risk") 应返回 2 个风险相关工具"""
        risk_specs = list_specs_by_tag("risk")
        assert len(risk_specs) == 2

    def test_list_specs_by_side_effect_read(self):
        """list_specs_by_side_effect("read") 应返回 8 个纯查询工具"""
        read_specs = list_specs_by_side_effect("read")
        assert len(read_specs) == 8

    def test_list_specs_by_side_effect_write(self):
        """list_specs_by_side_effect("write") 应返回 1 个需审批工具"""
        write_specs = list_specs_by_side_effect("write")
        assert len(write_specs) == 1

    def test_get_spec_metadata_existing(self):
        """get_spec_metadata 应返回已注册工具的完整元数据"""
        metadata = get_spec_metadata(FINANCE_QA_TASK.name)
        assert metadata["name"] == FINANCE_QA_TASK.name
        assert metadata["side_effect_level"] == "read"
        assert metadata["tag"] == "learning"

    def test_get_specs_for_tags_union(self):
        """get_specs_for_tags 应返回多个标签的并集"""
        specs = get_specs_for_tags(["learning", "risk"])
        assert len(specs) == 5  # 3 learning + 2 risk

    def test_list_read_only_tasks_shortcut(self):
        """list_read_only_tasks() 应返回所有纯查询工具"""
        tasks = list_read_only_tasks()
        assert len(tasks) == 8

    def test_list_write_tasks_shortcut(self):
        """list_write_tasks() 应返回所有需审批工具"""
        tasks = list_write_tasks()
        assert len(tasks) == 1
```

**运行**:
```bash
pytest tests/test_tool_discovery.py -v
```

---

## 改动检查清单

- [ ] `src/investory/gateway/routing.py`
  - 新增 `list_all_specs()`
  - 新增 `list_specs_by_tag(tag)`
  - 新增 `list_specs_by_side_effect(level)`
  - 新增 `get_spec_metadata(task_name)`
  - 新增 `list_read_only_tasks()`
  - 新增 `list_write_tasks()`
  - 新增 `get_specs_for_tags(tags)`

- [ ] `tests/test_tool_discovery.py` (新建)
  - 9+ 条测试全过

- [ ] 现有测试不失败：`pytest` 通过

---

## Commit Message

```
feat(routing): add tool discovery and query APIs

Extends routing.py with comprehensive tool discovery functions:

Query Functions:
- list_all_specs(): get all 9 registered tools
- list_specs_by_tag(tag): filter by business category
- list_specs_by_side_effect(level): filter by impact level
- get_spec_metadata(task_name): get complete metadata for one tool

Convenience Functions:
- list_read_only_tasks(): alias for side_effect_level="read"
- list_write_tasks(): alias for side_effect_level="write"
- get_specs_for_tags(tags): union query for multiple tags

These APIs enable internal systems to discover and categorize
tools based on Phase 1 metadata. Foundation for Phase 3 (access
control) and operational monitoring.

Co-Authored-By: Claude Haiku 4.5 <noreply@anthropic.com>
```

---

## 预期时间投入

- 改代码：10 分钟
- 写测试：15 分钟
- 验证：5 分钟
- **总计：0.5 天**

---

## 后续检查点

改完 Phase 2 后，应该：
1. ✅ `pytest tests/test_tool_discovery.py -v` 9/9 通过
2. ✅ `list_specs_by_side_effect("write")` 能查出 risk_assessment
3. ✅ `list_specs_by_tag("document_review")` 能查出 5 个文档审查工具
4. ✅ `get_specs_for_tags(["learning", "risk"])` 返回 5 个工具
5. ✅ 全量 `pytest` 无新增失败
