# Investory 第 1-2 课适用场景（仅编排层）

## 场景名称

基金/ETF 学习卡片生成

## 为什么这个场景适合当前项目

- 已有输入输出模型可直接复用：`InstrumentBriefInput` -> `InstrumentBriefResult`。
- 已有稳定执行路径可复用：`TaskExecutor`、`RequestRunner`、`TaskResult`。
- 可以只改“编排层表达”，不动后续能力（模型调用、结构化输出、网关接口）。
- 节点名可以写成业务动作，符合第 1-2 课目标。

## 用户故事

用户粘贴一段基金/ETF 资料（招募说明、事实表、研报片段），希望系统返回一张可学习的“标的学习卡片”，包括：

- 这是什么标的（类型与概览）
- 关键事实（费率、跟踪对象、持仓特征等）
- 学习重点与风险提示
- 后续应该继续问什么

## 最小业务编排（建议）

```text
提炼标的关键信息
-> 生成学习卡片
-> 返回学习建议
```

说明：

- `提炼标的关键信息`：从用户提供资料中抽取可结构化事实与风险线索。
- `生成学习卡片`：组织概览、关键事实、学习重点、风险提示与不确定性说明。
- `返回学习建议`：统一封装为可直接消费的任务结果。

注意：这里的节点名是“对业务可读”的编排节点，不是技术函数名。

## 编排节点与实现映射（内部）

为保持当前代码兼容，业务节点可映射到现有最小流程实现：

- `提炼标的关键信息`：内部包含输入校验、payload 标准化、prompt 上下文准备。
- `生成学习卡片`：内部调用 `RequestRunner`，产出 `InstrumentBriefResult`。
- `返回学习建议`：内部统一成功/失败输出为 `TaskResult`。

结论：`整理资料上下文`、`call_model` 属于实现细节，不作为对外业务节点名。

## 最小状态（面向本场景）

```python
state = {
    "task_id": "run-xxx",
    "task_name": "instrument_brief",
    "input_payload": {...},
    "validated_input": None,
    "messages": None,
    "model_result": None,
    "output": None,
    "error": None,
}
```

## 本阶段边界（先不做）

- 不引入 planner、tool 调用、memory、checkpoint、多轮会话。
- 不改 `RequestRunner` 和 provider 配置逻辑。
- 不改 API 协议和 `TaskExecutor.run(spec, payload) -> TaskResult` 外部契约。

## 验收标准（仅编排层）

1. 对外节点命名为业务动作（不暴露技术步骤名）。
2. 仍能跑通单次任务执行，返回结构与当前兼容。
3. 错误阶段仍保持可区分：`input_validation` / `prompt_build` / `model_call` / `output_validation`。
4. `RequestRunner` 仍是唯一直接模型调用入口。

## 后续可扩展方向（不在本次实现）

1. 增加“缺失字段追问”分支（接到 `ask_missing_fields`）。
2. 增加“拒答投资建议”分支（接到 `refuse_investment_advice`）。
3. 增加“多任务路由”（`instrument_brief` / `finance_qa` / `learning_material_summary`）。
