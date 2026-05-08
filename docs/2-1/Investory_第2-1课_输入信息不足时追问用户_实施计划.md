# Investory 第 2-1 课：先引入 instrument brief 与缺字段追问实施计划

## 一、调整后的目标

本次不先写代码，先调整实施计划。

新的落地顺序是：

```text
先引入 instrument_brief 这个新 task
-> 暂时只基于用户提供的材料生成投资标的学习简报
-> 不接入查询规则、实时数据或外部工具
-> 再为这个 task 引入输入信息不足时追问用户
```

也就是说，本次计划的核心不是“查询规则”，而是先把第 2-1 课里的业务链路压缩成当前项目可落地的最小版本：

```text
补齐投资标的字段
-> 基于用户提供材料生成学习简报
```

暂不实现：

```text
查询规则
实时行情查询
基金数据库查询
自动补全基金资料
个性化投资建议
自动交易或下单
```

## 二、为什么先引入 instrument_brief

当前 Investory 已经有两个 task：

```text
finance_qa
learning_material_summary
```

它们分别适合：

```text
finance_qa:
用户有明确问题，希望基于材料回答。

learning_material_summary:
用户给一段材料，希望生成学习笔记和待办。
```

但“帮我看看这只 ETF / 基金”这类输入不完全等同于 QA，也不只是摘要。它更像是：

```text
把一个投资标的整理成结构化学习简报
```

所以建议新增第三个 task：

```text
instrument_brief
```

中文语义可以叫：

```text
投资标的学习简报
```

它的边界是：

```text
解释这个标的是什么
整理用户提供材料中的关键信息
指出学习者应该关注的概念
提示风险和不确定性
明确不构成投资建议
```

## 三、instrument_brief 的任务边界

### 适合处理的输入

```text
帮我整理一下 VOO 这个 ETF。

这是某只基金的说明书，帮我生成一份学习简报。

帮我看看这个 REITs 的基础信息，适合从哪些维度理解？
```

### 不适合处理的输入

```text
现在能不能买？

这只基金未来会涨吗？

帮我和我的资产配置匹配一下。

帮我自动查一下最新持仓和费率。
```

这些输入后续可以进入风险收束、追问或工具查询流程，但不属于第一版 `instrument_brief`。

## 四、建议的最小输入 schema

第一版建议保守一点，要求用户提供标的名称和材料。

```python
class InstrumentBriefInput(BaseModel):
    instrument_name_or_code: str
    source_material: str
```

字段含义：

| 字段 | 作用 |
| --- | --- |
| `instrument_name_or_code` | 用户要了解的投资标的名称或代码 |
| `source_material` | 用户提供的基金说明、ETF factsheet、新闻、研报摘录或其他材料 |

为什么 `source_material` 第一版建议必填：

- 当前还没有查询规则和外部数据源；
- 避免模型凭空补全标的信息；
- 保持回答基于用户提供材料；
- 更符合 Investory 的学习助理定位。

## 五、建议的最小输出 schema

第一版输出应该是学习简报，而不是投资建议。

建议结构：

```python
class InstrumentKeyFact(BaseModel):
    label: str
    value: str


class InstrumentBriefResult(BaseModel):
    instrument_name_or_code: str
    instrument_type: str
    overview: str
    key_facts: list[InstrumentKeyFact]
    learning_points: list[str]
    risk_notes: list[str]
    follow_up_questions: list[str]
    risk_notice: str
    uncertainty: str
```

字段含义：

| 字段 | 作用 |
| --- | --- |
| `instrument_name_or_code` | 标的名称或代码 |
| `instrument_type` | ETF、基金、股票、债券、REITs，无法判断则写 unknown |
| `overview` | 面向学习者的简短说明 |
| `key_facts` | 从材料中提取的结构化事实 |
| `learning_points` | 学习者应该关注的概念 |
| `risk_notes` | 材料中体现的风险点或常见误解 |
| `follow_up_questions` | 后续可以继续追问的问题 |
| `risk_notice` | 不构成投资建议的提示 |
| `uncertainty` | 材料不足或无法确认的信息 |

## 六、prompt 设计原则

`instrument_brief` 的 prompt 应明确约束：

```text
只基于用户提供的 source_material
不要假设没有提供的数据
不要补充实时行情、最新费率、最新持仓
不要给买卖建议
不要评价是否值得买
输出必须是学习导向的结构化简报
```

建议任务说明：

```text
Generate an educational brief for the investment instrument based only on the provided source material.
```

重点输出：

```text
1. Instrument overview
2. Key facts grounded in the source material
3. Learning points
4. Risk notes
5. Follow-up questions
6. Risk notice
7. Uncertainty
```

## 七、和缺字段追问的关系

引入 `instrument_brief` 后，“输入信息不足时追问用户”就有了一个更自然的目标场景。

例如用户输入：

```text
帮我看看这只 ETF。
```

如果系统已经决定这是 `instrument_brief`，但缺少必要字段，则应该输出：

```json
{
  "action": "ask_missing_fields",
  "task_name": "instrument_brief",
  "missing_fields": ["instrument_name_or_code", "source_material"],
  "user_message": "请提供 ETF 的名称或代码，并贴出你希望我基于其整理的材料，例如基金说明、factsheet、新闻或研报摘录。",
  "reason": "当前请求表达了投资标的学习需求，但缺少标的名称或可依据的材料。"
}
```

这比直接让 `finance_qa` 报 `material_text` / `question` 缺失更贴合业务语义。

## 八、建议实现顺序

### Step 1：注册 instrument_brief task

新增内容：

```text
src/investory/agent_core/task_models/instrument_brief.py
src/investory/agent_core/prompts/tasks/instrument_brief.md
src/investory/agent_core/tasks.py
src/investory/gateway/routing.py
```

目标：

```text
新增 InstrumentBriefInput
新增 InstrumentBriefResult
新增 INSTRUMENT_BRIEF_TASK
TASKS 注册 instrument_brief
TASK_ALIASES 增加 brief -> instrument_brief
```

这一阶段不做缺字段追问，仍沿用现有执行链路。

### Step 2：补 task 注册和路由测试

新增或更新：

```text
tests/test_tasks.py
tests/test_gateway_routing.py
```

覆盖：

```text
instrument_brief task spec 绑定正确 input/output model
TASKS 包含 instrument_brief
resolve_task_name("brief") == "instrument_brief"
resolve_task_spec("instrument_brief") 返回新 task
```

### Step 3：再做缺字段追问

新增：

```text
src/investory/agent_core/contracts/action_decision.py
src/investory/agent_core/runtime/input_requirements.py
```

目标：

```text
读取 TaskSpec.input_model 的 required fields
判断 payload 中缺少哪些字段
生成 ask_missing_fields action
```

对 `instrument_brief` 来说，第一版需要追问：

```text
instrument_name_or_code
source_material
```

### Step 4：在 gateway 执行器前拦截

目标流程：

```text
TaskRequest
-> resolve_task_spec(task_type)
-> get_missing_required_fields(spec, payload)
-> if missing_fields:
     return ask_missing_fields response
-> else:
     executor.run(spec, payload)
```

建议把 action 放进现有 `TaskResponse.result`，保持外层 response schema 不变：

```json
{
  "ok": true,
  "task_name": "instrument_brief",
  "session_id": "...",
  "result": {
    "action": "ask_missing_fields",
    "task_name": "instrument_brief",
    "missing_fields": ["source_material"],
    "user_message": "请贴出你希望我基于其整理的材料，例如基金说明、factsheet、新闻或研报摘录。",
    "reason": "当前请求缺少执行 instrument_brief 所需字段。"
  },
  "error": null
}
```

## 九、测试计划

### 1. instrument_brief task 测试

覆盖：

```text
InstrumentBriefInput 必填 instrument_name_or_code 和 source_material
InstrumentBriefResult 输出结构可校验
INSTRUMENT_BRIEF_TASK 注册正确
TASKS 包含 instrument_brief
```

### 2. routing 测试

覆盖：

```text
brief -> instrument_brief
instrument_brief -> instrument_brief
未知 task 仍返回 UnknownTaskTypeError
错误消息包含 brief / instrument_brief
```

### 3. prompt 构造测试

覆盖：

```text
instrument_brief prompt 文件可加载
build_messages 能把 instrument_name_or_code 和 source_material 放进 input_data_block
```

### 4. 缺字段追问测试

覆盖：

```text
instrument_brief payload={}
-> missing_fields 包含 instrument_name_or_code 和 source_material

instrument_brief payload={"instrument_name_or_code": "VOO"}
-> missing_fields 包含 source_material

instrument_brief payload 字段齐全
-> 不返回 ask_missing_fields
-> 进入原执行链路
```

## 十、建议提交拆分

建议拆成两个提交或两个 PR。

### Commit 1：新增 instrument_brief task

建议 commit message：

```text
feat: add instrument brief task
```

范围：

```text
task model
task prompt
task registry
routing alias
task/routing tests
```

### Commit 2：新增缺字段追问 action

建议 commit message：

```text
feat: ask for missing task input fields
```

范围：

```text
action schema
required field detection
gateway preflight
missing field tests
```

## 十一、一句话总结

先引入 `instrument_brief` 是合理的，但第一版必须限定为“基于用户提供材料的投资标的学习简报”。查询规则和实时数据能力先不做，缺字段追问围绕 `instrument_name_or_code` 和 `source_material` 这两个最小输入展开。
