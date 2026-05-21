# Investory 课纲模块 -> AWS / Azure 服务对照表

> 说明：这份对照表是按 `Investory` 这个“投资理财学习助手”项目编写的。`课程模块 -> 云服务组合` 是基于 2026-04-22 查到的 AWS / Azure 官方产品定位做的工程映射，不是课纲原文。

## 对照表

| 课纲模块 | Investory 落地 | AWS | Azure |
|---|---|---|---|
| 单次请求 / 模型接入 | 理财概念问答、财报摘要、学习计划生成 | `Amazon Bedrock` | `Azure OpenAI` |
| 规划、决策、结构化输出 | 判断是“问答 / 追问 / 查工具 / 生成计划 / 模拟复盘” | 应用内 `planner`，必要时配合 `Step Functions` 做外部编排 | 应用内 `planner`，必要时配合 `Durable Functions` 或 `Logic Apps` |
| 工具 / MCP 接入 | 接基金资料、ETF 数据、财经日历、新闻、你自己的投研接口 | `Lambda` 或 `ECS/Fargate` 承载工具；对外由 `API Gateway` 暴露；检索型可接 `Bedrock Knowledge Bases` | `Functions` 或 `Container Apps` 承载工具；对外由 `API Management` 暴露；检索型优先 `Azure AI Search` |
| 执行面 / 沙盒 | 受限执行爬取、文件解析、表格计算、规则脚本 | 隔离执行优先 `ECS/Fargate`；低风险任务可 `Lambda` | 隔离执行优先 `Container Apps Jobs` 或 `AKS`；低风险任务可 `Functions` |
| 消息入口 / Gateway | Web/API 入口、鉴权、限流、会话归属 | `API Gateway` + 后端 `ECS/App Runner/EKS` | `API Management` + 后端 `Container Apps/App Service/AKS` |
| Runtime 运行时引擎 | 上下文拼装、工具注入、失败重试、事件分发 | 核心运行时放 `ECS/App Runner/EKS` | 核心运行时放 `Container Apps/App Service/AKS` |
| Skills 供应与消费 | “基金分析 Skill”“财报阅读 Skill”“资产配置 Skill”“风险提示 Skill” | Skill 文件可放 `S3`，元数据放 `DynamoDB` | Skill 文件可放 `Blob Storage`，元数据放 `Cosmos DB` |
| 事件流 / 流式反馈 / 主动任务 | SSE 过程回传、定时晨报、财报提醒、复盘提醒 | `EventBridge` 做事件总线，`SQS` 做异步队列，`Step Functions` 做长流程；SSE 仍由应用服务提供 | `Service Bus` 做消息队列，`Event Grid` 做事件分发，`Durable Functions/Logic Apps` 做长流程；若以后走 WebSocket，可加 `Azure Web PubSub` |
| 状态管理 / 可控记忆 / 恢复 | 学习进度、风险偏好、已读文章、复盘记录、checkpoint/resume | `DynamoDB` 放 session/profile/checkpoint，`ElastiCache` 做短期缓存，`S3` 放附件与回放材料 | `Cosmos DB` 放 session/profile/checkpoint，`Azure Cache for Redis` 做短期缓存，`Blob Storage` 放附件与回放材料 |
| 知识检索 / RAG | 理财知识库、基金百科、术语解释、课程资料 | `Bedrock Knowledge Bases`，底层文档可接 `S3` | `Azure AI Search` + `Blob Storage` |
| Eval / 回归 / 可观测性 | 检查是否事实错误、是否越界成投资建议、是否漏风险提示 | `CloudWatch` + `X-Ray`；评测样例集放 `S3` | `Application Insights` + `Azure Monitor`；评测样例集放 `Blob Storage` |
| 成本 / 可靠性 / 安全 | token 预算、超时、重试、审计、密钥、最小权限 | `Secrets Manager` + `IAM` + `CloudWatch Alarms`，入口可再加 `WAF` | `Key Vault` + `Managed Identity / Entra ID` + `Azure Monitor Alerts`，入口可再加 `WAF` |

## 对 Investory 的具体建议

如果是先做 `MVP`，建议优先选下面两套之一。

### 方案一：Azure 版

`Azure OpenAI + API Management + Container Apps + Azure AI Search + Cosmos DB + Application Insights + Key Vault`

适合：更看重企业接入、API 治理、RAG、监控。

### 方案二：AWS 版

`Bedrock + API Gateway + ECS/Fargate + Bedrock Knowledge Bases + DynamoDB + EventBridge/SQS + CloudWatch + Secrets Manager`

适合：更看重事件驱动、异步任务、工作流编排、云原生解耦。

## 对项目选型的判断

如果 `Investory` 第一阶段重点是：

- 理财问答
- 财报或文章摘要
- 知识库检索
- 学习记录

更偏向 `Azure` 这套，原因是 `Azure OpenAI + API Management AI gateway + Azure AI Search + Application Insights` 这条链更顺。

如果后面更想做：

- 定时任务
- 大量异步流程
- 事件驱动提醒
- 更强的服务解耦

那 `AWS` 会更舒服。

## 金融学习助手默认要加的约束

- 所有行情、基金、新闻结果都带 `数据时间戳`
- 默认输出“学习与研究用途，不构成投资建议”
- 直接荐股、择时、仓位建议走强约束或拒答
- 把“风险提示是否出现”纳入 `eval`

## 官方来源

- AWS API Gateway: https://docs.aws.amazon.com/apigateway/latest/developerguide/welcome.html
- Amazon Bedrock: https://docs.aws.amazon.com/bedrock/latest/userguide/what-is-bedrock.html
- Bedrock Knowledge Bases: https://docs.aws.amazon.com/bedrock/latest/userguide/kb-how-it-works.html
- Amazon EventBridge: https://docs.aws.amazon.com/eventbridge/latest/userguide/eb-what-is.html
- AWS Step Functions: https://docs.aws.amazon.com/step-functions/latest/dg/sfn-prerequisites.html
- Amazon SQS: https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/Welcome.html
- Amazon DynamoDB: https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/Introduction
- Amazon CloudWatch: https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/WhatIsCloudWatch.html
- AWS Secrets Manager: https://docs.aws.amazon.com/secretsmanager/latest/userguide/intro.html
- Azure API Management gateway: https://learn.microsoft.com/en-us/azure/api-management/api-management-gateways-overview
- Azure API Management AI gateway: https://learn.microsoft.com/en-us/azure/api-management/genai-gateway-capabilities
- Azure OpenAI: https://learn.microsoft.com/en-us/azure/ai-services/openai/overview
- Azure Container Apps: https://learn.microsoft.com/en-us/azure/container-apps/
- Azure Container Apps ingress: https://learn.microsoft.com/en-us/azure/container-apps/ingress-overview
- Azure AI Search: https://learn.microsoft.com/en-us/azure/search/
- Azure Service Bus: https://learn.microsoft.com/en-us/azure/service-bus-messaging/service-bus-messaging-overview
- Azure Cosmos DB: https://learn.microsoft.com/en-us/azure/cosmos-db/nosql/
- Application Insights: https://learn.microsoft.com/en-us/azure/azure-monitor/app/opentelemetry-overview
- Azure Key Vault: https://learn.microsoft.com/en-us/azure/key-vault/general/basic-concepts
- Azure Web PubSub: https://learn.microsoft.com/en-us/azure/azure-web-pubsub/overview
