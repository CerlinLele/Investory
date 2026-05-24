# Investory 最小编排适用场景

## 这份文档要回答什么

这一版不再把“最小编排”理解成一个完整 workflow。

结合第 1-1 课《最小任务执行说明》，更合适的定义是：

```text
在现有最小任务执行链路前，
增加一层很轻的入口分流。
```

也就是说：

- 任务执行仍然复用现有 `TaskExecutor`
- 编排层只负责判断“这次请求该怎么进”
- 不把 `TaskExecutor`、`RequestRunner`、`TaskExecutionPipeline` 拆进图里

## 现有最小能力边界

第 1-1 课已经明确，当前最小可执行链路是：

```text
TaskSpec
-> TaskExecutor
-> prompt_loader
-> RequestRunner
-> structured result
```

这条链路已经能稳定完成：

- `finance_qa`
- `learning_material_summary`
- `instrument_brief`

所以“最小编排”不应该重做这条链路，而应该只做它前面的入口判断。

## 推荐先做的 2 步

### 1. 入口判断

先把用户请求判成三类之一：

- 缺字段
- 投资建议请求
- 可执行学习任务

如果属于“可执行学习任务”，再补一个最小判断：

- 该进入 `qa`
- 或 `summary`
- 或 `brief`

这一步的职责只是“分流”，不是“生成最终内容”。

### 2. 统一收口

根据上一步的结果，走三种最短路径：

- 缺字段：直接返回补充信息提示
- 投资建议请求：直接拒答，并给学习替代方向
- 可执行学习任务：进入现有 `TaskExecutor`

可以写成：

```text
判断请求类型
-> [缺字段] 返回补充提示
-> [投资建议] 返回拒答与学习引导
-> [学习任务] 调用 TaskExecutor
```

这里的关键点是：

- 编排层负责“决定走哪条路”
- 任务层负责“把具体任务执行完”
- 最终仍统一返回 `TaskResult`

## 如果要保留第 3 步

第三步只建议做“工厂化封装”，不建议继续加复杂节点。

例如：

```python
build_learning_entry_flow(...) -> LearningEntryFlow
```

或者：

```python
LearningEntryFlow.run(input) -> TaskResult
```

这样 gateway 或调用方只需要拿一个入口对象，而不关心内部是否有判断分支。

## 对应到当前项目的理解

如果按现在的代码边界来看，最合理的职责分层是：

- 入口编排层：做请求判断与分流
- `TaskExecutor`：执行单个最小任务
- `RequestRunner` 及其下游：完成模型调用与结构化输出

所以这阶段最重要的不是“节点数量够不够完整”，而是：

- 不重复实现已有最小任务执行能力
- 不过早把简单分流做成重型 workflow
- 先把“入口判断 -> 直接返回 / 调 TaskExecutor”跑通

## 一句话结论

`Investory` 当前更合适的“最小编排”是：

```text
入口分流器
-> 直接返回，或
-> 复用现有 TaskExecutor
```

先做这 2 步已经足够；如果需要第 3 步，再补一个对外稳定的 flow 工厂即可。
