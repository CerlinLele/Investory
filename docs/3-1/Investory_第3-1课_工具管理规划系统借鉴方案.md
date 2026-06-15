# Investory × 第3-1课：工具管理和规划体系借鉴方案

## 📋 项目现状分析

你的项目已经有了好的基础：
- ✓ `ToolRegistry` 做了验证和权限控制
- ✓ `LoopEngine` 分离了规划、验证、执行三个阶段（对应课程的 Plan/Policy/Exec）
- ✓ 用 LangGraph 做流程编排（learning_entry_flow、investment_document_review）

但还缺少课程讲的 **4 个关键模块** 的完整实现。

---

## 🎯 四个需要完善的地方

### 1️⃣ 注册中心升级：从验证器 → 工具目录

**现在** `ToolRegistry` 只能：
```python
validate(tool_name, args, task_name)  # ← 只做校验
```

**应该** 加入课程的完整能力：

```python
class ToolRegistry:
    def register(self, tool_id: str, desc: str, input_schema: dict, 
                 func: Callable, side_effect_level: str, tag: str):
        """集中注册工具：名称、描述、参数、执行函数、副作用级别、业务标签"""
        # 存储完整的工具元数据 + 执行函数
        pass
    
    def list_all(self, side_effect_level: str = None):
        """按副作用级别筛选返回全量工具
        
        side_effect_level 可选值：
        - "read"：纯查询，可直接暴露给模型
        - "write"：状态修改，需要谨慎审批
        - "exec"：脚本执行，需要单独管控
        """
        pass
    
    def get_specs_by_tag(self, tag: str):
        """按业务标签查询，供动态注入用
        
        tag 示例：
        - "document_query"：文档查询类
        - "risk_assessment"：风险评估类
        - "synthesis"：综合分析类
        """
        pass
    
    def search_specs(self, query: str):
        """模糊查找，工具增多时有用"""
        pass
    
    def call_func(self, tool_id: str, args: dict):
        """从这里执行，可以挂审计/日志/风控"""
        pass
```

**现有代码对标**：
- 当前 `tool_registry.py` 的 `ToolSpec` 只有 `name`, `args_model`, `requires_confirmation`, `allowed_task_names`
- 需要扩展：加 `func`, `desc`, `side_effect_level`, `tag`

**落地步骤**：
1. 扩展 `ToolSpec` 数据类，加入 `func`、`desc`、`side_effect_level`、`tag`
2. 在 `investory_actions.py` 改成通过注册中心注册 action，而不是枚举
3. 给每个 action 加 `tag`（query / write / exec）和 `side_effect_level`
4. 测试时可以通过 `call_func` 拦截和 mock

---

### 2️⃣ 动态注入层：从"全量工具给模型" → "按场景给子集"

**现在的问题**：
- 工具声明散落在各处（investory_actions.py、各个 Flow 里）
- 没有"先分类意图 → 再激活工具子集"的机制
- 每次请求都可能把全量工具 token 给模型

**应该** 加这一层：

```python
# 在 LoopEngine 或 StepPlanner 前面加这一层
def prepare_tools_for_step(state: ReactLoopState) -> list[str]:
    """根据当前步骤的意图，动态决定给模型看哪些工具"""
    
    # 第一步：分类意图（可以让 LLM 分类，也可以规则）
    intent = classify_intent(state.current_context)
    # intent 可能是: "query_document", "validate_risk", "synthesize"
    
    # 第二步：从注册中心按 tag 取工具子集
    if intent == "query_document":
        return registry.get_specs_by_tag("read")
    elif intent == "validate_risk":
        return registry.get_specs_by_tag("write")
    elif intent == "synthesize":
        return registry.get_specs_by_tag("read")  # 综合不需要写入
    
    # 这样模型每次只看到最相关的工具，降低 token，减少误选
```

**投资文档审查流程的具体应用**：

```python
INTENT_TOOL_MAP = {
    # 投资文档审查路由阶段
    "investment_router": {
        "tags": ["document_query"],
        "description": "判断是否为投资文档、路由到对应处理流程"
    },
    
    # 投资文档提取阶段
    "document_extract": {
        "tags": ["document_query", "text_processing"],
        "description": "提取关键信息：标的、估值、风险因素"
    },
    
    # 风险评估阶段
    "risk_assessment": {
        "tags": ["document_query", "risk_write"],
        "description": "评估市场风险、财务风险、政策风险"
    },
    
    # 综合反思阶段
    "synthesis": {
        "tags": ["document_query"],
        "description": "综合分析前面阶段的结果，生成最终建议"
    },
}
```

**落地步骤**：
1. 在 `LoopEngine.plan_next_step()` 或 `StepPlanner` 的前置钩子里调用 `prepare_tools_for_step()`
2. 投资文档审查的各个阶段各对应一组工具标签
3. 根据当前所处阶段，从注册中心筛选激活工具集
4. 只把激活工具的 spec 注入到模型的 system prompt

---

### 3️⃣ Plan Handler 可替换：从"只能模型规划" → "规则/配置/A/B 随意切"

**现在**：
- `LoopEngine` 里的 `planner: StepPlanner` 是一个协议
- 但只有一个实现，没有多个变体给不同场景选

**应该** 实现这些变体：

```python
# 默认：模型自主规划
class ModelPlanner(StepPlanner):
    """让 LLM structured output 决定下一步
    
    适用场景：生产环境、探索性任务
    """
    def plan_next_step(self, state: ReactLoopState) -> PlannedStep:
        response = self.llm.generate(
            state.context,
            output_schema={
                "action_type": "tool_call | finalize",
                "tool_name": "str | null",
                "tool_args": "dict | null",
            }
        )
        return PlannedStep(
            action_type=response.action_type,
            summary=response.reasoning,
            metadata={"tool": response.tool_name, "args": response.tool_args}
        )


# 审计模式：固定流程，只准查不准写
class AuditModePlanner(StepPlanner):
    """严格按审计规则规划
    
    适用场景：测试验证、审计流程、灰度发布
    规则示例：
    - 只允许调 read 类工具
    - 达到指定步数后立即 finalize
    - 同一工具不重复调用
    """
    def plan_next_step(self, state: ReactLoopState) -> PlannedStep:
        # 如果已经查询完成，直接结束
        if state.tool_call_count > 3:
            return PlannedStep(action_type=ReactActionType.FINALIZE)
        
        # 如果上一步已经查询了文档，下一步不再查询
        if state.last_tool_name == "query_document":
            return PlannedStep(action_type=ReactActionType.FINALIZE)
        
        # 否则继续查询
        return PlannedStep(
            action_type=ReactActionType.CALL_TOOL,
            metadata={"tool_name": "query_document"}
        )


# 配置驱动：从配置中心下发规划逻辑
class ConfigDrivenPlanner(StepPlanner):
    """从配置中心下发规划逻辑
    
    适用场景：灰度实验、A/B 测试、动态切换策略
    """
    def plan_next_step(self, state: ReactLoopState) -> PlannedStep:
        plan_config = self.config_center.get_plan_config(
            flow_type=state.flow_type,
            user_segment=state.user_segment,
            experiment_id=state.experiment_id
        )
        return plan_config.get_next_step(state)


# 规则引擎：支持复杂的条件规划
class RuleEnginePlanner(StepPlanner):
    """基于规则引擎的规划
    
    适用场景：业务逻辑复杂、需要灵活调整的场景
    """
    def plan_next_step(self, state: ReactLoopState) -> PlannedStep:
        # 从规则库匹配应该执行的 action
        matched_rule = self.rule_engine.match(state)
        if matched_rule:
            return matched_rule.get_planned_step()
        # 规则不匹配则降级到模型规划
        return self.default_planner.plan_next_step(state)
```

**投资文档审查的版本对标**：

| 版本 | Planner 选择 | 用途 |
|------|-------------|------|
| v0 | `ModelPlanner` | 基础版，模型自主规划 |
| v1 | `ModelPlanner` + todo 并发 | 并发执行优化版 |
| v2 | `AuditModePlanner` | 风险审批版，严格控制流程 |
| v3 | `RuleEnginePlanner` | 反思优化版，支持复杂规则 |
| 灰度 | `ConfigDrivenPlanner` | A/B 测试不同策略 |

**落地步骤**：
1. 当前的 `StepPlanner` 协议保持不变，只需多实现几个类
2. 在 `LoopEngine.__init__()` 时注入 planner，不同流程版本传不同实现
3. v1/v2/v3 各对应一个 planner 实现
4. 灰度和测试时动态选择 planner 实现

---

### 4️⃣ Execution Handler 可替换：从"直接执行" → "真实/mock/审计/远程选一个"

**现在**：
- `LoopEngine` 里的 `executor: StepExecutor` 执行时直接调真函数
- 没有 mock、审计、远程等变体

**应该** 提供多个实现：

```python
# 真实执行：直接调用工具
class RealExecutor(StepExecutor):
    """真实执行工具函数
    
    适用场景：生产环境、真实任务执行
    """
    def execute_step(self, state: ReactLoopState, planned_step: PlannedStep):
        if planned_step.action_type != ReactActionType.CALL_TOOL:
            return StepExecutionResult(finalize=True)
        
        tool_name = planned_step.metadata.get("tool_name")
        tool_args = planned_step.metadata.get("args", {})
        
        try:
            result = self.registry.call_func(tool_name, tool_args)
            return StepExecutionResult(
                details={"result": result},
                tool_call_record=ReactToolCallRecord(
                    tool_name=tool_name,
                    args=tool_args,
                    result=result,
                    status="success"
                )
            )
        except Exception as e:
            return StepExecutionResult(
                retryable_error=True,
                error_message=str(e)
            )


# Mock 执行：模拟执行，不调真函数
class MockExecutor(StepExecutor):
    """模拟执行工具函数
    
    适用场景：单元测试、集成测试、验证流程逻辑
    优点：不依赖外部系统、速度快、可控制返回值
    """
    def execute_step(self, state: ReactLoopState, planned_step: PlannedStep):
        if planned_step.action_type != ReactActionType.CALL_TOOL:
            return StepExecutionResult(finalize=True)
        
        tool_name = planned_step.metadata.get("tool_name")
        tool_args = planned_step.metadata.get("args", {})
        
        # 从 mock 数据库取预定义的返回值
        mock_result = self.mock_data.get(tool_name, {})
        
        return StepExecutionResult(
            details={"result": mock_result, "is_mock": True},
            tool_call_record=ReactToolCallRecord(
                tool_name=tool_name,
                args=tool_args,
                result=mock_result,
                status="mock_success"
            )
        )


# 审计日志包裹：真实执行 + 完整日志记录
class AuditedExecutor(StepExecutor):
    """真实执行 + 审计日志
    
    适用场景：生产审计、合规要求、故障排查
    记录：工具名、参数、返回值、执行时间、调用者等
    """
    def execute_step(self, state: ReactLoopState, planned_step: PlannedStep):
        tool_name = planned_step.metadata.get("tool_name")
        tool_args = planned_step.metadata.get("args", {})
        
        # 执行前日志
        self.audit_logger.log_tool_call_start(
            session_id=state.session_id,
            tool_name=tool_name,
            args=tool_args,
            timestamp=datetime.now()
        )
        
        # 调用真实 executor
        start_time = time.time()
        result = self.real_executor.execute_step(state, planned_step)
        duration = time.time() - start_time
        
        # 执行后日志
        self.audit_logger.log_tool_call_end(
            session_id=state.session_id,
            tool_name=tool_name,
            status=result.tool_call_record.status,
            duration=duration,
            result_preview=str(result.details)[:100]
        )
        
        return result


# 远程执行：通过 RPC/HTTP 调用远程工具服务
class RemoteExecutor(StepExecutor):
    """远程调用工具
    
    适用场景：微服务架构、工具服务化、流量分散
    """
    def execute_step(self, state: ReactLoopState, planned_step: PlannedStep):
        tool_name = planned_step.metadata.get("tool_name")
        tool_args = planned_step.metadata.get("args", {})
        
        try:
            response = self.rpc_client.call(
                service=self.tool_service_map.get(tool_name),
                method=tool_name,
                args=tool_args,
                timeout=30
            )
            return StepExecutionResult(details={"result": response})
        except RemoteCallError as e:
            return StepExecutionResult(
                retryable_error=True,
                error_message=f"Remote call failed: {e}"
            )
```

**Executor 组合矩阵**：

```python
# 这个表展示了不同场景下的搭配方案
combine_scenarios = {
    "生产环境": {
        "planner": "ModelPlanner",
        "executor": "RealExecutor",
        "audit": "AuditedExecutor"
    },
    "单元测试": {
        "planner": "ModelPlanner",
        "executor": "MockExecutor",
        "audit": None
    },
    "审计流程": {
        "planner": "AuditModePlanner",
        "executor": "AuditedExecutor",
        "audit": "AuditedExecutor"
    },
    "集成测试": {
        "planner": "RuleEnginePlanner",
        "executor": "MockExecutor",
        "audit": None
    },
    "灰度发布": {
        "planner": "ConfigDrivenPlanner",
        "executor": "RealExecutor",
        "audit": "AuditedExecutor"
    },
}
```

**落地步骤**：
1. 现有 `RealExecutor` 逻辑保持不变
2. 新增 `MockExecutor`、`AuditedExecutor`、`RemoteExecutor`
3. 在 `LoopEngine.__init__()` 时可选注入不同 executor
4. FastAPI 的 `/tasks` 端点加参数 `?execution_mode=mock|audit|real` 动态切换
5. 投资文档审查的测试用 `MockExecutor`，生产用 `AuditedExecutor`

---

## 🗺️ 具体实施路线

基于你的分支 `feature/3-1-tool-management-planning-system`，建议这样做：

| 优先级 | 任务 | 文件改动 | 说明 |
|--------|------|--------|------|
| **P0** | 扩展 `ToolSpec`：加 `func`、`desc`、`side_effect_level`、`tag` | `tool_registry.py` | 支撑其他三个模块的基础 |
| **P0** | 扩展 `ToolRegistry` 方法：`register()`、`list_all(level)`、`get_specs_by_tag()`、`call_func()` | `tool_registry.py` | 完整的注册中心 |
| **P0** | 重构 `investory_actions.py`：从 enum 改成注册到注册中心 | `investory_actions.py` | 管理工具的统一入口 |
| **P1** | 给每个 action 加 `tag` 和 `side_effect_level` | `investory_actions.py` | 为动态注入做准备 |
| **P1** | 新增 `DynamicToolInjector` 类，实现意图分类和工具激活 | 新文件 `tool_injection.py` | 降低 token，减少误选 |
| **P1** | 在 `LoopEngine.plan_next_step()` 前加动态注入钩子 | `loop_engine.py` | 集成动态注入 |
| **P2** | 新增 `ModelPlanner`、`AuditModePlanner`、`ConfigDrivenPlanner` | 新文件 `planners.py` | 为 v1/v2/v3 分版本奠基 |
| **P2** | 新增 `MockExecutor`、`AuditedExecutor`、`RemoteExecutor` | 新文件 `executors.py` | 支持多种执行模式 |
| **P3** | FastAPI 端点改造：支持 `?execution_mode` 参数 | `gateway/api.py` | 动态切换执行模式 |

---

## 💡 和现有代码的融合点

你项目里已经有了很好的分离：

```python
LoopEngine:
  - planner: StepPlanner       ← 现在只有模型规划，应该支持多种实现
  - policy: StepPolicy         ← 验证已做好（ToolRegistry.validate）
  - executor: StepExecutor     ← 现在只有真实执行，应该支持 mock/审计/远程
```

**只需要**：
1. **补齐 `ToolRegistry` 的完整能力** ← 目前只有验证，缺少执行函数和查询接口
2. **在 planner 前加一层动态激活** ← 根据意图从注册中心选工具
3. **提供多个 planner 实现** ← 而不是只有模型规划一种
4. **提供多个 executor 实现** ← mock / 审计 / 真实选一个

这四个模块正好对应课程讲的架构，不需要大改，只是**填补空白** 和 **完善现有设计**。

---

## 📝 总结对照表

| 课程模块 | 项目现状 | 需要完善 | 收益 |
|---------|---------|--------|------|
| **工具注册中心** | ToolRegistry 只做验证 | 加 register/list_all/call_func | 工具有处可查、执行可控 |
| **动态注入工具** | 没有 | 新增 DynamicToolInjector | 每次激活最相关工具，降低 token |
| **Plan Handler** | 只有 ModelPlanner | 加 AuditModePlanner 等变体 | v1/v2/v3 可切换策略 |
| **Execution Handler** | 只有 RealExecutor | 加 MockExecutor/AuditedExecutor | 测试、审计、灰度都能支持 |

这些改进都是**水平扩展**（加新实现），不需要改变现有的 LoopEngine 骨架。

---

## 🚀 后续课程预告

- **第 3-2 课**：MCP 工具标准化协议 → 外部工具怎么被发现、调用、适配
- **第 3-3 课**：沙盒 + 命令行执行 → 代码执行、文件操作、受限环境

本课奠定的架构是后续两课的前提——执行层有了统一接口，新工具类型的接入就是插件式的。
