# ToolRegistry 云上架构设计

背景:[工具注册-Schema校验-确认门槛-云服务对比.md](./工具注册-Schema校验-确认门槛-云服务对比.md) 中确认了 AWS Bedrock Agents 的 Action Group / `functionSchema` 无法覆盖 `allowed_task_names`(任务级白名单)等业务定制逻辑。本文给出在这个前提下,`ToolRegistry` 上云的分层方案。

## AWS 中负责工具注册的组件名称

Amazon Bedrock Agents 里负责工具注册的具体组件叫 **Action Group(动作组)**。

- **Action Group** 挂在一个 Agent 下面,一个 agent 可以挂多个 action group。
- 若选择 "Define with function details" 方式(而非 OpenAPI schema 方式),会用到 **`functionSchema`** 字段——这是真正意义上"工具注册表"的载体,每个 function 就是一个可调用的工具,带 `name`、`description`、`parameters`、`requireConfirmation`。
- 创建方式:调 `CreateAgentActionGroup` API,或在控制台 Agent Builder 的 Action groups 面板操作。

对应关系:

| Bedrock 概念 | tool_registry.py 中的对应 |
|---|---|
| Action Group | 大致相当于按 `tag` 分组的工具集合 |
| `functionSchema` 里的每个 function | 一个 `ToolSpec` |
| `parameters` | `args_model` |
| `requireConfirmation` | `requires_confirmation` |

## 核心思路

不把 registry 塞进 Bedrock 的 action group 配置里,而是把 Bedrock(或任何 LLM API)只当作"工具调用协议层",`ToolRegistry` 继续作为独立的业务层跑在自己的服务里。

## 分层方案

### 1. LLM 协议层 = Bedrock Agents(用 Return control 模式)

不用 Lambda 直连模式,选 **Return control**——Bedrock 只负责让模型预测该调哪个工具、参数是什么,然后把预测原样返回给应用,不真正执行。这样 Bedrock 干的是它擅长的部分(tool use 协议 + 参数抽取),不掺和业务权限判断。

### 2. Registry/校验层 = 自建服务,不是云托管组件

`ToolRegistry.validate()` 这一整块(`task_name` 白名单、`side_effect_level`、confirmation 门槛)继续留在自己的代码里,部署方式二选一:

- 如果 agent runtime 本身是长驻服务(ECS/Fargate/EC2),registry 就是进程内的一个模块,跟现在一样。
- 如果想无服务器化,registry 校验逻辑可以包成一个 Lambda,agent runtime 调用它做"预检",通过了再决定要不要真的执行工具。

两种都行,registry 本身很轻(纯内存 dict + pydantic 校验),没有状态持久化需求,不需要数据库。

### 3. 工具执行层 = 每个工具各自的 Lambda/服务,按 side_effect_level 分权

`ToolSpec.func` 实际执行时,建议每个工具对应一个独立 Lambda(或内部微服务),IAM policy 按 `side_effect_level` 分级——`read` 级工具给只读权限的 role,`write`/危险级工具给单独的、权限更收紧的 role。这样即使 registry 层被绕过或有 bug,IAM 这层还有兜底。

### 4. 配置存放位置

`allowed_task_names`、`side_effect_level`、`tag` 这些如果想动态调整不用重新部署代码,可以放 DynamoDB 或 SSM Parameter Store,registry 启动时拉取。如果这些配置变动不频繁,留在代码里(现状)更简单,不用额外引入配置存储的运维成本。

### 5. 确认(confirmation)UI

因为用了 Return control,"需要用户确认"这个交互得自己做——比如在 chat 界面里弹出"是否执行 XX 操作",不能依赖 Bedrock 内置的确认弹窗(那个只在它直连 Lambda 的模式下生效)。

## Tradeoff

这套架构比"全部丢给 Bedrock 托管"多了几个自己要维护的组件(registry 服务、confirmation UI、IAM 分权),换来的是任务级权限逻辑保留在自己手上,不被云服务的通用能力锁死。
