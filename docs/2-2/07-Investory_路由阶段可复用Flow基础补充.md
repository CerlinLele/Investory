# Investory 路由阶段可复用 Flow 基础补充

这份补充文档对应 `docs/2-2/01-Investory_第2-2课_Routing内容提取与项目落点.md`，专门整理当前 routing 阶段里能跨不同 flow 复用的基础层。

## 1. 可以复用的部分

### 1.1 前置策略门

`InvestoryPolicyGate` 这一层适合放到所有 flow 的最前面，统一处理：

```text
缺字段
投资建议拒答
实时数据能力不足
用户确认要求
低置信度兜底
```

不同 flow 可以有自己的业务逻辑，但前置安全判断建议共享。

### 1.2 结构化路由合约

路由结果建议保持统一结构，而不是散落成字符串判断：

```text
route
confidence
reason
missing_fields
```

这类合约可以迁移到新的 flow，用于文档类型识别、任务分流、确认决策和澄清兜底。

### 1.3 分层顺序

当前 routing 形成的顺序本身就可以复用：

```text
1. 规则校验
2. 规则路由
3. LLM routing
4. 低置信度兜底
5. 执行任务
```

这个顺序的核心价值是，把能确定的判断前置，只把规则覆盖不到的边界输入交给 LLM。

### 1.4 执行边界

`TaskExecutionPipeline` 应继续只承担单任务执行：

```text
validate input -> build prompt -> call model -> validate output -> build result
```

不同 flow 只需要在它外面编排，不要把 routing、Plan、Reflection 混进执行器。

### 1.5 测试结构

这次 routing 已经形成了可迁移的测试模板：

```text
policy gate tests
flow tests
gateway tests
router tests
```

后续新 flow 可以沿用同样的分层方式，分别验证：

```text
前置拦截
路由分支
兜底行为
最终执行结果
```

## 2. 不建议复用的部分

以下内容不要抽成公共层：

```text
具体 route 名称
具体 prompt
具体 payload 结构
具体业务拒答规则
具体 completion criteria
```

这些应该留在各自 flow 里，否则公共层会越来越重，维护成本会很快上升。

## 3. 适合的新 Flow 复用方式

如果后续新增 `investment_document_review_flow` 之类的新 flow，推荐直接复用这几层：

```text
InvestoryPolicyGate
structured route decision
low-confidence fallback
TaskExecutor
TaskExecutionPipeline
shared testing pattern
```

业务差异只放在：

```text
document type router
review checklist
prompt
result model
reflection criteria
```

## 4. 简短结论

当前阶段真正值得公用的是：

```text
路由骨架
策略门
决策模型
兜底策略
执行边界
测试结构
```

不值得公用的是：

```text
具体业务语义
具体 prompt
具体 payload
具体 reject / criteria 规则
```

这条边界保持住，新的 flow 才会更容易扩展。
