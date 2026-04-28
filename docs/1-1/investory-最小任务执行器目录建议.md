# Investory 第 1-1 课：最小任务执行器目录建议

基于当前 `src/investory` 的结构，我建议先建立一个清楚的 `agent_core`，把“最小任务执行器”放进 `agent_core/runtime`，并在 `agent_core` 下面单独放一个 `prompts` 目录。不要先在 `investory` 根下再起一个平级的 `agents` 或 `llm` 大目录，这个阶段边界会变散。

这里的命名含义是：

- `agent_core/`
  表示 Investory 的 agent 核心能力，包括任务定义、执行入口、prompt、结果结构。
- `agent_core/runtime/`
  表示 agent core 内部真正把一次任务跑起来的运行层。

## OpenClaw 中 runtime 的含义

这里借用了 OpenClaw 对 `runtime` 的语义：`runtime` 不是 Python 解释器的运行环境，也不是单纯的模型 API 封装，而是负责把一次已经准备好的 agent/model 任务真正执行起来的底层执行层。

在 OpenClaw 的概念里，可以粗略理解成：

```text
Channel  -> 消息从哪里来，比如 Telegram / Slack
Provider -> 使用哪家模型服务，比如 OpenAI / Anthropic
Model    -> 使用哪个具体模型
Runtime  -> 真正执行这一轮 agent/model loop
```

所以 `runtime` 主要关心：

- 接收准备好的 prompt 和上下文
- 驱动模型完成一次或多次输出
- 处理中途的 tool call
- 维护本轮执行状态
- 返回结构化结果或错误

放到 Investory 里，`agent_core/runtime/` 的含义就是：

```text
Investory agent core 内部负责执行一次任务的运行层
```

它比 `llm/` 更宽，因为它不只负责调用模型；它比 `agents/` 更窄，因为它不负责定义整个 agent 体系，只负责“把任务跑起来”。

## 推荐目录

```text
src/investory/
  config.py
  main.py
  gateway/
  memory/
  eval/
  agent_core/
    __init__.py
    task_spec.py
    result_types.py
    runtime/
      __init__.py
      task_executor.py
      prompt_loader.py
    prompts/
      base/
        system.md
        common_rules.md
      tasks/
        meeting_minutes.md
        policy_qa.md
```

## 每个文件负责什么

- `task_executor.py`
  放在 `agent_core/runtime/`，作为最小执行器本体：组 prompt、发请求、收结果、做错误收口。
- `task_spec.py`
  放在 `agent_core/`，保存 `TaskSpec` 这种任务定义，避免执行器和任务定义混在一起。
- `prompt_loader.py`
  放在 `agent_core/runtime/`，专门负责从 `prompts/*.md` 读模板，不要把文件读取逻辑塞进执行器。
- `result_types.py`
  放在 `agent_core/`，保存统一返回结构，比如 `TaskResult`、`TaskError`。
- `prompts/base/`
  放在 `agent_core/prompts/` 下，保存所有任务共享的系统提示和共通规则。
- `prompts/tasks/`
  放在 `agent_core/prompts/` 下，保存每个任务自己的 prompt 模板。

## 更贴近课程路线的版本

如果你想更贴近“单次请求 -> request runner -> TriggerFlow”的路线，我更推荐这个命名：

```text
src/investory/
  agent_core/
    __init__.py
    task_spec.py
    result_types.py
    runtime/
      __init__.py
      request_runner.py
      task_executor.py
      prompt_loader.py
    prompts/
      base/
        system.md
        common_rules.md
      tasks/
        meeting_minutes.md
        policy_qa.md
```

这里的职责关系是：

```text
TaskSpec + payload
-> task_executor
-> request_runner
-> model
-> structured result
```

区别是：

- `request_runner.py`
  放在 `agent_core/runtime/`，更偏底层的一次模型请求。
- `task_executor.py`
  放在 `agent_core/runtime/`，更偏面向业务任务的最小执行器。

## 为什么建议单独放 prompts 文件夹

我建议你把 prompt 放成 `.md` 文件，而不是先用 `.py` 常量文件，原因是：

- 调 prompt 时更直观。
- 非程序同学也能读。
- 以后做 prompt 版本化和评测对照更容易。

但不要一开始拆得太碎。第一个版本只要两层：

- `base/system.md`
- `tasks/<task_name>.md`

例如：

`base/system.md`

```md
你是一个严格按要求执行任务的投资学习助手。
```

`tasks/policy_qa.md`

```md
请根据提供的制度文本回答问题。

要求：
1. 只能根据输入材料回答
2. 不足时明确说明不确定性
3. 输出 answer、evidence、uncertainty
```

然后 `agent_core/runtime/prompt_loader.py` 负责拼：

```text
system.md
+ task prompt
+ rendered payload
```

## 不建议现在就做的事

当前阶段不建议直接做这些：

- 很多 prompt fragments 小文件
- 多级模板继承
- 通用 prompt registry
- 动态 prompt pipeline

这些都适合任务数明显增加以后再做。

## 当前最小可落地版本

你现在的目标应该是：

1. 先有一个清楚的 `agent_core/runtime/task_executor.py`
2. 先有一个清楚的 `agent_core/prompts/`
3. 先把 2 个任务跑通
4. 统一结果结构和错误收口

如果要马上开工，我建议先新增：

```text
src/investory/agent_core/
  __init__.py
  task_spec.py
  result_types.py
  runtime/
    __init__.py
    task_executor.py
    prompt_loader.py
  prompts/
    base/system.md
    tasks/meeting_minutes.md
    tasks/policy_qa.md
```

## 一句话结论

现阶段最好的安排不是再起一个宽泛的 `agents` 或 `llm` 顶层目录，而是先建立 `agent_core`，把最小任务执行器落在 `agent_core/runtime` 里，并把 `prompts` 作为 `agent_core` 的一类核心资产来管理。
