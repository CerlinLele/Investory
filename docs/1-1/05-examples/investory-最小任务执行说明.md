# Investory 第 1-1 课：最小任务执行说明

## 目标

这一份说明只回答一个问题：`Investory` 当前最小可执行的任务有哪些，以及它们在项目里怎么进入执行链路。

项目里所谓“最小任务执行”，不是完整 agent、不是多轮规划、也不是工具回路，而是：

```text
TaskSpec
-> TaskExecutor
-> prompt_loader
-> RequestRunner
-> structured result
```

这条链路的特点是：

- 一次请求完成一次任务
- 只处理当前输入
- 不依赖 planner、memory、tool loop
- 输出固定结构化结果，便于测试和前端展示

## 当前任务

`src/investory/agent_core/tasks.py` 里当前注册了 3 个任务。

### 1. `finance_qa`

用途：根据金融学习材料回答一个具体问题。

输入字段：

- `material_text`
- `question`

适合场景：

- 解释概念
- 针对一段材料做问答
- 帮助用户理解投资/理财知识

### 2. `learning_material_summary`

用途：对金融学习材料做结构化总结。

输入字段：

- `material_text`

适合场景：

- 摘要整理
- 提炼关键概念
- 生成后续学习待办

### 3. `instrument_brief`

用途：根据标的资料生成一个结构化简报。

输入字段：

- `instrument_name_or_code`
- `source_material`

适合场景：

- ETF、基金、股票、债券等标的说明
- 从材料里提炼事实、风险点和学习点

## 对外别名

HTTP 网关层会把更短的 `task_type` 映射到内部任务名。

`src/investory/gateway/routing.py` 里的别名是：

- `qa` -> `finance_qa`
- `summary` -> `learning_material_summary`
- `brief` -> `instrument_brief`

所以 `/tasks` 接口可以接受这 6 种值：

- `qa`
- `summary`
- `brief`
- `finance_qa`
- `learning_material_summary`
- `instrument_brief`

## 最小执行路径

当前最小执行器的职责是把一次请求串起来，而不是做复杂决策。

```text
TaskSpec + payload
-> task_executor
-> input_model validation
-> prompt_loader
-> request_runner
-> model.with_structured_output
-> TaskResult
```

这意味着：

- 输入先做 schema 校验
- prompt 从 `agent_core/prompts/` 加载
- 模型返回结构化结果
- 成功或失败都统一收口成 `TaskResult`

## 示例请求

### `qa`

```json
{
  "task_type": "qa",
  "payload": {
    "material_text": "ETF is a basket of assets.",
    "question": "What is ETF?"
  }
}
```

### `summary`

```json
{
  "task_type": "summary",
  "payload": {
    "material_text": "Maximum drawdown is the largest decline from a peak to a trough over a period of time."
  }
}
```

### `brief`

```json
{
  "task_type": "brief",
  "payload": {
    "instrument_name_or_code": "VOO",
    "source_material": "VOO tracks the S&P 500 and holds large U.S. companies."
  }
}
```

## 备注

- `smoke` 入口目前已经覆盖 `finance_qa` 和 `learning_material_summary` 的默认 payload。
- `instrument_brief` 已注册在任务表里，但 smoke 默认样例里还没有单独补一份 payload。
- 如果后续要扩展，优先继续保持“单次请求、单次输出”的结构，不要一开始就引入复杂 workflow。

## 结论

`Investory` 当前最小任务集就是这 3 个：

- `finance_qa`
- `learning_material_summary`
- `instrument_brief`

对外使用时，它们分别可以通过 `qa`、`summary`、`brief` 这 3 个别名进入网关。
