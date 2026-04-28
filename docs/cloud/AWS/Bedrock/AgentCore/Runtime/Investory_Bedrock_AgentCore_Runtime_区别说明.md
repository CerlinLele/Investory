# Investory 本地 runtime 与 AWS Bedrock AgentCore Runtime 的区别

## 一句话结论

`src/investory/agent_core/runtime/` 是 **Investory 项目内部的任务执行层**。  
`AWS Bedrock AgentCore Runtime` 是 **AWS 提供的托管运行平台**。

两者不是同一个概念，也不是二选一关系，而是可以形成上下层关系：

```text
Investory task logic
-> Investory agent_core/runtime
-> FastAPI or AgentCore adapter
-> AWS Bedrock AgentCore Runtime
```

## 为什么容易混淆

当前项目里已经用了 `agent_core/runtime` 这个命名，而 AWS 又有一个正式产品名叫 `Bedrock AgentCore Runtime`。

两边都带有：

- `agent`
- `core`
- `runtime`

所以在讨论“runtime”时，必须先分清是在说：

- **项目内部运行层**
- 还是 **AWS 托管运行时**

## Investory 里的 runtime 是什么

当前项目中的 `src/investory/agent_core/runtime/` 负责把一次任务真正跑起来。

它的职责是：

- 根据配置创建模型客户端
- 加载 prompt 文件
- 校验任务输入
- 调用模型并要求结构化输出
- 把结果或错误统一收口

当前代码里对应的核心文件：

- `src/investory/agent_core/runtime/model_factory.py`
- `src/investory/agent_core/runtime/request_runner.py`
- `src/investory/agent_core/runtime/task_executor.py`
- `src/investory/agent_core/runtime/prompt_loader.py`

它回答的问题是：

> “Investory 的一条任务链路在代码内部怎么执行？”

## AWS Bedrock AgentCore Runtime 是什么

`AWS Bedrock AgentCore Runtime` 是 AWS 的托管运行平台。

它更关心的是：

- agent 代码如何部署
- 如何扩缩容
- 如何隔离会话和运行环境
- 如何暴露调用入口
- 如何处理托管基础设施

它回答的问题是：

> “这段 agent 代码在哪里运行、如何托管、如何扩缩容、如何对外暴露？”

所以它属于 **平台层 / 基础设施层**，不是你业务代码里的执行器实现。

## 两者的职责区别

### 1. 关注层级不同

Investory 本地 runtime：

- 位于应用内部
- 是业务执行链路的一部分
- 面向 `TaskSpec`、payload、prompt、schema、错误模型

Bedrock AgentCore Runtime：

- 位于云平台侧
- 是部署与托管能力
- 面向进程托管、入口协议、伸缩、安全与运行隔离

### 2. 解决的问题不同

Investory 本地 runtime 解决：

- 输入是否合法
- prompt 怎么拼
- 模型怎么调
- 输出如何做 structured output
- 错误如何归一化

Bedrock AgentCore Runtime 解决：

- agent 服务怎么启动
- AWS 如何调用它
- 运行实例如何扩缩
- 会话与执行环境如何隔离
- 托管环境如何承接你的 agent

### 3. 替换成本不同

Investory 本地 runtime：

- 是项目内部实现
- 可以随着业务演进重构
- 可以从 LangChain 换成别的模型接入层

Bedrock AgentCore Runtime：

- 是部署平台选型
- 影响部署方式、调用协议和运维路径
- 替换时会影响整条云上交付链路

## 在 Investory 里应该怎么理解它们的关系

更合理的理解是：

- `agent_core/runtime` 保留为 **业务执行内核**
- `Bedrock AgentCore Runtime` 作为 **云上托管运行环境**

也就是说：

- 项目自己的 runtime 决定“任务怎么执行”
- AWS 的 runtime 决定“任务执行器怎么被托管和调用”

这两层并不冲突。

## 你当前代码离 Bedrock AgentCore Runtime 还差什么

当前项目已经具备一部分可复用内核：

- 配置驱动的模型接入
- 独立的 task executor
- 独立的 prompt loader
- 结构化输出与错误收口

但是它还不能直接作为 `Bedrock AgentCore Runtime` 的部署对象，主要缺少：

- 对外服务入口
- 符合 AgentCore Runtime 的调用适配层
- 部署打包方式
- 云上运行配置

换句话说：

- **已有**：task execution core
- **未有**：AgentCore Runtime adapter

## 为什么当前代码不能直接上 Bedrock AgentCore Runtime

当前仓库里的入口更像本地 CLI 和 smoke test：

- `src/investory/main.py`
- `src/investory/agent_core/runtime/smoke/cli.py`

这说明当前形态更适合：

- 本地验证
- 手工 smoke test
- 作为后续服务层的被调用内核

但它还不是一个直接面向 AgentCore Runtime 的托管服务。

如果以后要接入 Bedrock AgentCore Runtime，通常还需要补一层：

- FastAPI 入口，或
- AWS AgentCore Python SDK 的入口适配

然后在适配层内部调用现有 `TaskExecutor`。

## 推荐的分层方式

建议保留现在的核心分层：

```text
task_models / contracts
-> agent_core/runtime
-> service adapter
-> AWS runtime platform
```

可以映射成：

```text
TaskSpec + payload
-> TaskExecutor
-> FastAPI or AgentCore adapter
-> Bedrock AgentCore Runtime
```

这样做的好处是：

- 业务逻辑不被云平台 SDK 污染
- 本地测试仍然简单
- 以后即使不跑在 AWS，也能复用同一套执行器

## 命名上的注意事项

当前项目使用 `agent_core/runtime`，在和 AWS 方案并行推进时会有天然歧义。

后续如果云上方案会长期落地在 Bedrock AgentCore Runtime，可以考虑把本地目录命名改得更明确，例如：

- `task_runtime`
- `execution_core`
- `task_execution`
- `orchestration_runtime`

这样以后讨论 “AgentCore Runtime” 时，不会混淆成：

- 项目自己的 runtime
- AWS 的 AgentCore Runtime 产品

## 当前阶段的建议

当前阶段最稳的做法不是立刻把业务内核改成 AWS 形状，而是：

1. 保持现有 `TaskExecutor` 作为业务核心。
2. 先增加一层服务入口适配。
3. 再决定部署到 ECS / App Runner / Bedrock AgentCore Runtime。

这样演进成本最低，也最容易保持本地开发体验。

## 参考资料

- AWS Bedrock AgentCore overview  
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html
- AWS Bedrock AgentCore Runtime  
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/agents-tools-runtime.html
- AWS Bedrock AgentCore Runtime how it works  
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/runtime-how-it-works.html
- AWS Bedrock AgentCore custom runtime getting started  
  https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/getting-started-custom.html
