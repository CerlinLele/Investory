# Step F-2 交付检查清单（3-1 HTTP Tooling）

## 1) 完整性检查

- Code: 完成
  - Tool Contract 扩展：`src/investory/agent_core/contracts/tool_contract.py`
  - `web_search` 工具实现：`src/investory/agent_core/tools/web_search.py`
  - Guard/配置治理：`src/investory/config.py`、`src/investory/agent_core/tools/net_guard.py`
  - 执行器与路由：`src/investory/agent_core/actions/executors.py`、`src/investory/agent_core/actions/router.py`、`src/investory/agent_core/actions/validator.py`
  - gateway/task 接线：`src/investory/gateway/routing.py`、`src/investory/agent_core/tasks.py`、`src/investory/agent_core/runtime/decision_planner.py`
- Tests: 部分完成（环境阻塞）
  - 已通过：`tests/test_web_search_tool.py`、`tests/test_gateway_routing.py`、`tests/test_tasks.py`
  - 阻塞：`langchain_core` 缺失导致 action 相关测试在 collection 阶段报错
- Docs: 完成
  - 执行计划：`docs/3-1/Investory_HTTP_工具补实现执行计划.md`
  - 定位文档（已更新为新实现）：`docs/3-1/Investory HTTP 工具调用逻辑代码定位.md`
  - 本清单与 PR 草稿：`docs/3-1/delivery-checklist.md`、`docs/3-1/PR_DESCRIPTION.md`
- Worklog: 完成
  - `docs/3-1/worklog/http-tooling-implementation.md` 覆盖 E-1 ~ F-2

## 2) 变更文件清单（按模块）

- Contracts
  - `src/investory/agent_core/contracts/tool_contract.py`
  - `src/investory/agent_core/contracts/action_contract.py`
- Tools
  - `src/investory/agent_core/tools/web_search.py`
  - `src/investory/agent_core/tools/__init__.py`
- Config / Guard
  - `src/investory/config.py`
- Actions / Runtime
  - `src/investory/agent_core/actions/executors.py`
  - `src/investory/agent_core/actions/router.py`
  - `src/investory/agent_core/actions/validator.py`
  - `src/investory/agent_core/runtime/decision_planner.py`
- Tasks / Gateway
  - `src/investory/agent_core/task_models/web_search_brief.py`
  - `src/investory/agent_core/tasks.py`
  - `src/investory/gateway/routing.py`
- Tests / Smoke
  - `tests/test_web_search_tool.py`
  - `tests/test_action_executors.py`
  - `tests/test_action_router.py`
  - `tests/test_action_validator.py`
  - `tests/test_decision_planner.py`
  - `tests/test_gateway_routing.py`
  - `tests/test_tasks.py`
  - `src/investory/agent_core/runtime/smoke/task.py`
- Docs
  - `docs/3-1/Investory HTTP 工具调用逻辑代码定位.md`
  - `docs/3-1/worklog/http-tooling-implementation.md`

## 3) 风险清单

- R1: 测试环境依赖不完整（`langchain_core` 缺失）
  - 影响：action 相关测试无法在当前环境执行全绿验证
  - 缓解：安装依赖后重跑 `test_action_executors.py` / `test_action_router.py` / `test_action_validator.py` / `test_decision_planner.py`
- R2: provider 当前为示例适配（`example_search` / `example_instruments`）
  - 影响：生产可用性取决于后续接入真实 provider
  - 缓解：保持 `web_search_provider_order` 可配置；后续仅需扩展 provider candidates/adapters
- R3: `run_web_search` 走 `requires_user_input` 失败回传路径
  - 影响：上层可能需要进一步细分失败语义
  - 缓解：现阶段保持与现有交互风格一致，后续可引入更细粒度 action status 策略

## 4) 评审结论

- 状态：可进入评审（带已知环境阻塞项说明）
- 必看项：
  - `web_search` 契约与工具实现
  - gateway task_type 新映射
  - `run_web_search` 路由执行链路
  - 测试阻塞说明及复跑计划
