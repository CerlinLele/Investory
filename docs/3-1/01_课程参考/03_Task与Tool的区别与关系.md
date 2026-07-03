# Task 与 Tool 的区别与关系

## 核心答案：Task 本身不是 Tool，但"执行 Task"被建模为一个 Tool

这是一个**架构设计选择**，而不是代码bug。

---

## 两个不同的概念

### TaskSpec（任务规范）

- 定义 **单个可执行工作单元**
- 字段：name, prompt_name, input_model, output_model, side_effect_level, tag, desc
- 执行方式：`TaskExecutor.run(spec, payload)` 调用 LLM，获取结构化输出
- 例子：finance_qa, investment_document_review_single_pass

### ToolSpec（工具规范）

- 定义 **ReAct 循环中的可调用工具**
- 字段：name, args_model, func, side_effect_level, tag, desc
- 执行方式：`ToolRegistry.call_func(tool_name, args)` 调用 Python 函数
- 例子：ask_for_missing_input, execute_learning_task

---

## 为什么要这样设计？

从[讲座MVP与现有代码的映射与迁移](./02_讲座MVP与现有代码的映射与迁移.md)文档中的**缺口4**可以看到，设计想要把这个变成工具：

```python
def execute_learning_task(task_name: str, payload: dict) -> dict:
    """执行学习任务"""
    executor = get_task_executor(task_name)
    return executor.run(payload)

# 注册为工具
registry.register(ToolSpec(
    name="execute_learning_task",
    desc="执行学习任务",
    args_model=ExecuteLearningTaskArgs,
    func=execute_learning_task,
    side_effect_level="write",  # ← 关键：把任务执行标记为"写"操作
    tag="execution"
))
```

---

## 这样做的好处

1. **统一的权限/审计框架** — 所有操作（调用API、执行任务、等待用户输入）都通过一个 ToolRegistry 管理
2. **按 side_effect_level 分权** — 任务执行被标记为 `write`，可以在其他工具之前做风险审核
3. **细粒度的 allow-list** — `allowed_task_names` 能限制某个任务在特定场景下是否可被调用
4. **可审计** — 所有工具调用可被记录和追踪

---

## 当前状态 vs 目标状态

| 阶段 | TaskSpec | ToolRegistry | 进展 |
|---|---|---|---|
| **现在** | ✅ 完全实现 | ⚠️ 只有 metadata，没有 func/执行 | Phase 1 完成 |
| **Phase 2目标** | 不变 | ✅ 补充 list_by_tag/side_effect | 工具发现 |
| **Phase 3/4目标** | 不变 | ✅ 把 actions 注册成真实工具函数 | 统一执行/审计 |

---

## 关键点

**它不是 bug，而是未来规划的一部分**。当前 Phase 1 给 TaskSpec 补充了治理元数据（side_effect_level, tag, desc），为的就是后续能把"执行任务"也注册成工具，纳入统一的框架中。

这是**分层架构**的体现：
- **下层**：TaskSpec = 单个 LLM 调用的编排
- **上层**：ToolRegistry = ReAct 循环中的所有操作（包括任务执行）
