# Investory 第2-2课：To-Do + 并发内容提取与项目适用性

## 1. To-Do + 并发的核心结论

课程里的 `To-Do + 并发` 模式解决的是：复杂任务进来后，先拆成可验证的子任务，再根据依赖关系决定哪些可以并发、哪些必须串行。

它不是让模型边想边随意执行，而是让模型先输出结构化任务清单，系统再负责依赖分析、并发调度、结果收集和后续汇总。

核心流程：

```text
用户复杂任务
  -> generate_todo_list(task)
  -> 输出 tasks[{id, title, description, depends_on}] + summary
  -> analyze_dependencies(tasks)
  -> independent: 无依赖，可并发
  -> dependent: 有依赖，等待前置任务完成后再执行
  -> collect_results
  -> 汇总结果
```

课程示例里的关键机制：

```text
for_each(concurrency=3)
  -> execute_one_task
  -> collect_results
```

其中 `concurrency=3` 是并发上限，不是无限并发。系统要控制并发度，避免资源、速率限制或外部 API 压力失控。

## 2. To-Do 任务清单应包含什么

课程示例要求模型输出：

```json
{
  "tasks": [
    {
      "id": "t1",
      "title": "子任务标题",
      "description": "具体要做什么",
      "depends_on": []
    }
  ],
  "summary": "整体拆解思路"
}
```

关键字段含义：

```text
id:
  子任务唯一标识，用于依赖引用和结果回填。

title:
  人类可读的任务标题。

description:
  具体执行内容。不能太抽象，否则 executor 无法稳定执行。

depends_on:
  当前任务依赖哪些前置任务。空列表表示无依赖，可以参与并发执行。
```

课程复习速记里强调的最低要求：

```text
先产出任务清单，再执行，减少遗漏。
depends_on 决定是否可并发。
无依赖并发，有依赖串行。
```

## 3. 常见错误

### 3.1 没有 depends_on 就直接并发

如果没有依赖分析就并发，容易产生顺序错误。

例如：

```text
t1: 提取材料事实
t2: 基于事实生成结论
```

如果 `t2` 没有声明依赖 `t1`，系统可能让两个任务同时执行，导致结论没有事实基础。

### 3.2 子任务没有完成条件

课程材料里说“每个子任务要具体、可验证”。这意味着任务不应只写：

```text
分析 ETF
```

更合理的是：

```text
从材料中提取 ETF 的跟踪指数、费用、风险、适用场景，并输出结构化字段。
```

没有完成条件，就无法可靠做 result collection 和后续 reflection。

### 3.3 把并发当成默认优化

并发只适合无依赖、无共享写入、无强顺序要求的任务。

不适合并发的情况：

```text
需要前一步结果才能继续的任务
共享同一状态并写入同一字段的任务
需要严格审计顺序的高风险动作
会触发外部 API 限流或成本失控的动作
```

## 4. 和 Routing、Plan、Reflection 的关系

第 07 课的顺序可以理解为：

```text
Routing:
  先判断任务应该交给哪条路径。

To-Do + 并发:
  进入某条复杂路径后，判断要拆成哪些子任务，哪些可以并发。

Plan:
  对高风险或不可逆任务先生成计划和风险评估。

Reflection:
  执行完成后检查结果是否合格，必要时修正。
```

所以 `To-Do + 并发` 不应该放在所有入口最前面。它应该放在 route 之后，用于“确实复杂到需要拆解”的任务。

## 5. Investory 当前项目状态

当前 Investory 主要链路是：

```text
/learning-entry
  -> InvestoryPolicyGate
  -> rule routing 或 LLM routing
  -> resolve_task_spec
  -> TaskExecutor
  -> TaskExecutionPipeline
```

当前已注册任务：

```text
finance_qa
learning_material_summary
instrument_brief
```

当前执行器仍是单任务线性链路：

```text
validate input
  -> build prompt
  -> call model
  -> validate output
  -> build result
```

这意味着当前项目还没有真正需要 `for_each(concurrency=N)` 的核心执行面。现在的请求通常只会被 route 到一个 `TaskSpec`，然后调用一次模型。

结论：

```text
当前不建议马上把 TaskExecutionPipeline 改成并发执行。
当前更适合先把 To-Do + 并发作为未来复合任务能力的设计文档和边界约束。
```

## 6. Investory 里适用 To-Do + 并发的情况

### 6.1 多材料学习包分析

适用程度：高，适合未来新增。

示例输入：

```text
我上传了 5 份 ETF 材料，帮我整理学习笔记、风险点和适合提问的问题。
```

可拆任务：

```text
t1: 总结材料 A
t2: 总结材料 B
t3: 总结材料 C
t4: 总结材料 D
t5: 总结材料 E
t6: 汇总共同概念和差异点，depends_on=[t1,t2,t3,t4,t5]
t7: 生成学习问题清单，depends_on=[t6]
```

其中 `t1` 到 `t5` 可以并发，`t6` 和 `t7` 必须串行。

这很符合课程里的模式：

```text
无依赖材料处理 -> 并发
跨材料汇总 -> 等待所有前置完成
```

### 6.2 多标的 brief 批量生成

适用程度：高，适合未来新增 batch 接口。

示例输入：

```text
根据这些材料，分别生成 VOO、QQQ、BND 的学习简报，再给一个横向对比。
```

可拆任务：

```text
t1: 生成 VOO instrument_brief
t2: 生成 QQQ instrument_brief
t3: 生成 BND instrument_brief
t4: 横向比较三个 brief，depends_on=[t1,t2,t3]
```

`t1`、`t2`、`t3` 可以并发。`t4` 必须等待三个结果完成。

这类任务不应该塞进单个巨大 prompt。拆开后更容易控制输出结构，也更容易失败重试。

### 6.3 单个 instrument_brief 内部多维度抽取

适用程度：中等，不建议现在拆。

当前 `instrument_brief` 是一个单独 `TaskSpec`，通过一次模型调用完成。

未来如果 brief 输出变复杂，可以拆成：

```text
t1: 提取基础信息
t2: 提取费用和结构
t3: 提取风险点
t4: 提取适用学习场景
t5: 组装最终 brief，depends_on=[t1,t2,t3,t4]
```

但当前阶段不建议这样做。原因是：

```text
当前单次结构化输出已经足够简单。
拆太早会增加编排复杂度。
多次模型调用会增加成本和失败面。
```

只有当 `instrument_brief` 的 prompt 明显过长、输出不稳定或需要独立重试时，才值得拆。

### 6.4 ReAct 工具调用后的并发收集

适用程度：中等偏未来。

当前 `react_core` 已有 `LoopEngine` 和 `ToolRegistry`，但还没有多工具并发执行器。

未来如果工具成熟，可以考虑：

```text
t1: 查询材料库
t2: 查询术语解释库
t3: 查询历史学习记录
t4: 汇总上下文，depends_on=[t1,t2,t3]
```

但要注意：工具并发必须经过 policy gate 和 tool registry 校验，不能让模型直接并发调用任意工具。

### 6.5 测试、评估和批量离线任务

适用程度：高，适合工程侧先落地。

并发不一定先用于用户在线请求。更实际的落点是离线评估：

```text
并发跑一组 fixture 请求
并发生成多个 prompt 版本结果
并发评估多个样本
最后收集结果生成报告
```

这类任务不影响用户请求路径，更容易控制风险，也更容易观察并发收益。

## 7. 当前不适用的情况

### 7.1 `/tasks` 单任务请求

当前 `/tasks` 请求已经明确传入：

```text
task_type
payload
```

它应该继续走：

```text
resolve_task_spec -> TaskExecutor.run()
```

不需要 todo 拆解。

### 7.2 `/learning-entry` 的普通单意图请求

例如：

```text
解释这段 ETF 材料
总结这段材料
根据这段材料生成一个 brief
```

这些请求 route 到一个任务即可，不需要拆成 todo。

### 7.3 投资建议、实时数据和确认类请求

这些首先属于 policy gate 范围：

```text
investment_advice_request
realtime_data_not_available
user_confirmation_required
```

在 policy 未放行前，不应该进入 todo 拆解，更不应该并发执行。

## 8. 推荐的 Investory To-Do 合约

如果未来落地，建议先新增合约，不直接改现有执行器。

### 8.1 子任务类型

```python
from enum import Enum


class TodoTaskKind(str, Enum):
    FINANCE_QA = "finance_qa"
    LEARNING_MATERIAL_SUMMARY = "learning_material_summary"
    INSTRUMENT_BRIEF = "instrument_brief"
    SYNTHESIZE_RESULTS = "synthesize_results"
    ASK_FOR_MISSING_INPUT = "ask_for_missing_input"
```

### 8.2 子任务规格

```python
from pydantic import BaseModel, Field


class TodoTaskSpec(BaseModel):
    id: str
    kind: TodoTaskKind
    title: str
    description: str
    payload: dict
    depends_on: list[str] = Field(default_factory=list)
    completion_criteria: list[str] = Field(default_factory=list)
```

### 8.3 执行计划

```python
class TodoExecutionPlan(BaseModel):
    tasks: list[TodoTaskSpec]
    summary: str
```

### 8.4 子任务结果

```python
class TodoTaskResult(BaseModel):
    id: str
    status: str
    result: dict | None = None
    error: dict | None = None
```

重点是 `completion_criteria`。课程里强调“具体、可验证”，这个字段能避免子任务描述太虚。

## 9. 推荐的执行策略

### 9.1 先规则拆解，再考虑 LLM 拆解

第一版不要直接让 LLM 拆任意任务。可以先支持明确 batch 结构：

```json
{
  "items": [
    {"instrument_name_or_code": "VOO", "source_material": "..."},
    {"instrument_name_or_code": "QQQ", "source_material": "..."}
  ],
  "final_synthesis": true
}
```

系统规则生成 todo：

```text
每个 item 一个 independent task
如果 final_synthesis=true，再新增一个 dependent synthesis task
```

这样更稳定、更好测。

### 9.2 并发只执行无依赖层

不要简单地把所有 `depends_on=[]` 的任务执行完，再把所有 dependent 顺序跑完。更通用的方式是按拓扑层执行：

```text
Layer 1: 无依赖任务，并发执行
Layer 2: 依赖 Layer 1 的任务，并发执行
Layer 3: 依赖 Layer 2 的任务，并发执行
```

课程示例是简化版：

```text
independent 并发
dependent 顺序
```

Investory 如果未来支持复杂任务，建议用拓扑排序。

### 9.3 并发上限要配置化

建议使用常量或配置项：

```text
DEFAULT_TODO_CONCURRENCY = 3
```

不要写死在业务 handler 中。

### 9.4 子任务失败要有策略

至少需要三种失败策略：

```text
fail_fast:
  任一子任务失败就停止。

best_effort:
  能完成多少收集多少，并在最终结果里说明缺失。

retry_then_fail:
  对可重试错误先重试，超过次数再失败。
```

学习场景更适合：

```text
retry_then_fail
best_effort
```

高风险动作更适合：

```text
fail_fast
```

## 10. 推荐落地顺序

### Step 1：先不改在线执行链路

当前 `TaskExecutionPipeline` 保持线性。不要为了课程模式而强行并发化。

### Step 2：新增文档和测试型合约

先新增：

```text
TodoTaskSpec
TodoExecutionPlan
TodoTaskResult
```

并写纯单元测试验证：

```text
depends_on 字段存在
completion_criteria 字段存在
非法依赖能被检测
循环依赖能被拒绝
```

### Step 3：实现拓扑分层，不接真实模型

先实现：

```text
plan -> layers
```

测试：

```text
t1,t2 无依赖 -> layer 1
t3 depends_on=[t1,t2] -> layer 2
t4 depends_on=[t3] -> layer 3
```

### Step 4：做离线 batch runner

不要先接 HTTP。先做内部 runner：

```text
TodoExecutionRunner.run(plan)
```

用 fake executor 验证：

```text
同一 layer 的任务会被并发调度
后续 layer 等待前置完成
结果能按 id 回填
```

### Step 5：再考虑接入具体业务

优先业务：

```text
多材料学习包分析
多标的 instrument brief 批处理
离线评估任务
```

不建议优先业务：

```text
普通 finance_qa
普通 summary
普通 instrument_brief
投资建议类请求
实时行情类请求
```

## 11. 一句话结论

`To-Do + 并发` 对 Investory 有价值，但当前最适合作为“未来复合学习任务、批量材料处理、离线评估”的结构化执行模式；现有 `/tasks` 和 `/learning-entry` 单任务链路应继续保持线性，等出现多材料、多标的或多工具的真实需求后，再按 `depends_on + completion_criteria + concurrency limit` 落地。
