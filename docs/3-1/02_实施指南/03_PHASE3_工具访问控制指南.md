# Phase 3：工具访问控制 详细实施指南

## 目标

基于 Phase 1 的元数据（side_effect_level）和 Phase 2 的查询接口，在 `routing.py` 补充访问控制函数，明确"哪些角色可以调用哪些工具"。

这是"工具对外可控"的基础，为未来的多租户、角色权限、合规审计做准备。

---

## 改动范围

### 3.1 在 `routing.py` 新增访问控制函数

```python
def validate_task_access(task_name: str, user_role: str) -> bool:
    """
    验证用户角色是否可以调用指定工具
    
    当前实现(示意):
    - admin: 所有工具都可访问
    - analyst: 只能访问 read 级工具(纯查询)
    - 其他角色: 无访问权限
    
    Args:
        task_name: 工具名称
        user_role: 用户角色(admin/analyst/...)
    
    Returns:
        True 表示有权限,False 表示无权限
    
    未来扩展:
    - 从数据库读取权限配置
    - 支持更细粒度的 tag 级权限
    - 支持时间窗口限制(如灰度期间只开放给部分用户)
    """
    spec = TASKS.get(task_name)
    if spec is None:
        return False
    
    # admin 全部允许
    if user_role == "admin":
        return True
    
    # analyst 只允许 read 级
    if user_role == "analyst" and spec.side_effect_level == "read":
        return True
    
    return False


def require_task_access(task_name: str, user_role: str) -> None:
    """
    验证用户权限,无权限时抛异常(供 API 端点使用)
    
    Args:
        task_name: 工具名称
        user_role: 用户角色
    
    Raises:
        PermissionError: 当用户无权访问该工具时
    """
    if not validate_task_access(task_name, user_role):
        spec = TASKS.get(task_name)
        spec_level = spec.side_effect_level if spec else "unknown"
        raise PermissionError(
            f"User role '{user_role}' cannot access task '{task_name}' "
            f"(side_effect_level='{spec_level}')"
        )
```

### 3.2 改动 `routing.py` 的导出清单

```python
__all__ = [
    # 原有
    "TASK_ALIASES",
    "UnknownTaskTypeError",
    "resolve_task_name",
    "resolve_task_spec",
    # Phase 2 新增(工具发现)
    "list_all_specs",
    "list_specs_by_tag",
    "list_specs_by_side_effect",
    "get_specs_for_tags",
    "get_write_tasks",
    "get_read_only_tasks",
    "get_spec_metadata",
    # Phase 3 新增(访问控制)
    "validate_task_access",
    "require_task_access",
]
```

---

## 验证清单

### 3.3 创建 `tests/test_task_access_control.py`

```python
import pytest
from investory.gateway.routing import (
    validate_task_access,
    require_task_access,
    list_read_only_tasks,
    list_write_tasks,
)


class TestTaskAccessControl:
    """验证角色权限控制"""

    def test_admin_can_access_all_tasks(self):
        """Admin 角色应能访问所有工具"""
        assert validate_task_access("finance_qa", "admin")
        assert validate_task_access("investment_document_risk_assessment", "admin")
        
        # 验证全量工具
        all_tasks = list_read_only_tasks() + list_write_tasks()
        for spec in all_tasks:
            assert validate_task_access(spec.name, "admin"), f"Admin should access {spec.name}"

    def test_analyst_can_access_read_tasks(self):
        """Analyst 角色应只能访问 read 级工具"""
        for spec in list_read_only_tasks():
            assert validate_task_access(spec.name, "analyst"), (
                f"Analyst should access read task {spec.name}"
            )

    def test_analyst_cannot_access_write_tasks(self):
        """Analyst 角色不应能访问 write 级工具"""
        for spec in list_write_tasks():
            assert not validate_task_access(spec.name, "analyst"), (
                f"Analyst should NOT access write task {spec.name}"
            )

    def test_unknown_role_has_no_access(self):
        """未知角色应无访问权限"""
        assert not validate_task_access("finance_qa", "unknown_role")
        assert not validate_task_access("investment_document_risk_assessment", "unknown_role")

    def test_invalid_task_has_no_access(self):
        """非存在的工具对所有角色都无权限"""
        assert not validate_task_access("fake_task", "admin")
        assert not validate_task_access("fake_task", "analyst")

    def test_require_task_access_success(self):
        """有权限时 require_task_access 应不抛异常"""
        # 应成功(不抛异常)
        require_task_access("finance_qa", "admin")
        require_task_access("finance_qa", "analyst")

    def test_require_task_access_failure(self):
        """无权限时 require_task_access 应抛 PermissionError"""
        with pytest.raises(PermissionError, match="cannot access"):
            require_task_access("investment_document_risk_assessment", "analyst")
        
        with pytest.raises(PermissionError, match="cannot access"):
            require_task_access("finance_qa", "unknown_role")
```

**运行**:
```bash
pytest tests/test_task_access_control.py -v
```

---

## 改动检查清单

- [ ] `src/investory/gateway/routing.py`
  - 新增 `validate_task_access(task_name, user_role)`
  - 新增 `require_task_access(task_name, user_role)`
  - 更新 `__all__` 导出清单

- [ ] `tests/test_task_access_control.py` (新建)
  - 6+ 条测试全过

- [ ] 现有测试不失败：`pytest` 通过

---

## Commit Message

```
feat(routing): add task access control (RBAC foundation)

Add role-based access control foundation for task execution:

- validate_task_access(task_name, role): check if role can call task
- require_task_access(task_name, role): validate and raise PermissionError if denied

Current implementation:
- admin: full access to all tasks
- analyst: read-only tasks only (side_effect_level="read")
- other roles: no access

This foundation enables:
- FastAPI endpoints to check permissions before task dispatch
- Future expansion to more granular RBAC (tag-level, time-based, etc.)
- Audit trail integration (record access attempts in Phase 4)
- Multi-tenant isolation when user_role is per-tenant

Backward compatible: no existing code changes needed.

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

改完 Phase 3 后，应该：
1. ✅ `pytest tests/test_task_access_control.py -v` 6/6 通过
2. ✅ `validate_task_access("finance_qa", "admin")` 返回 True
3. ✅ `validate_task_access("investment_document_risk_assessment", "analyst")` 返回 False
4. ✅ `require_task_access()` 在无权限时抛 PermissionError
5. ✅ 全量 `pytest` 无新增失败
