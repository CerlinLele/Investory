# Investory 是否需要自己定制 ReAct loop

## 结论
需要做“轻量定制” ReAct loop，不建议完全依赖现成默认 loop。

## 判断依据（结合当前 Investory）
当前状态对象（`src/investory/agent_core/contracts/flow_state.py`）已经是可扩展方向，但还不够支撑生产级回路控制：
- 目前主要是 `status/messages/model_result/error` 等基础字段。
- 缺少典型 ReAct 运营字段，例如：`step_count`、`max_steps`、`tool_budget`、`retry_count`、`timeout`、`approval_gate`、`audit_trail`。

## 什么时候可以先不定制
如果只做单工具、低风险 Demo，可以先沿用现成 loop。

## 什么时候应该定制
只要进入下面场景，就建议定制：
1. 输入不足时需要追问并继续执行。
2. 多工具串并行、失败重试与降级。
3. 成本/时延上限控制与强制收敛。
4. 权限与合规拦截（模型建议不等于允许执行）。
5. 可观测性与审计回放。

## 实施建议
先做“薄编排层”，而不是重写全部代理内核：
- 保留模型推理能力。
- 程序侧接管工具调度、终止策略和安全策略。

这样可以在复杂度可控的前提下，获得稳定性、可控性和可审计性。
