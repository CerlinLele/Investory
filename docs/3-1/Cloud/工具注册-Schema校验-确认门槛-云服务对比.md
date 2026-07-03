# tool_registry.py 与云上 Agent 工具服务的对比

对象文件:[src/investory/agent_core/runtime/react_core/tool_registry.py](../../../src/investory/agent_core/runtime/react_core/tool_registry.py)

该文件实现的是"工具注册 + Schema 校验 + 任务级白名单 + 人工确认门槛"这一整套逻辑。云上没有一个服务刚好覆盖这四件事,但拆开看每一块都有对应的云能力可以参考或借力。

## 各部分对应的云能力

- **Schema 校验/工具声明**:本质是 LLM 提供商 function calling / tool use 协议(Anthropic tool_use、OpenAI function calling)已经内置的能力,自己写 pydantic model 校验是在补 SDK 没管的那一层。
- **任务级 allow-list + confirmation_granted 门槛**:AWS Bedrock Agents 有 human-in-the-loop 的确认机制,Azure AI Foundry Agent Service 也有类似 approval 流程,思路上和本文件的 `requires_confirmation` 类似,但云服务提供的都是通用开关,不支持按 `task_name` 精细化允许/禁止的逻辑。
- **多工具接入/鉴权托管**:如果核心痛点是"接入很多外部工具太麻烦",Composio、Arcade.dev 这类工具即服务平台可以托管 OAuth 和执行,但权限/确认策略仍需自己写。

## AWS Bedrock Agents 的具体机制(核实后)

Bedrock Agents 的 action group 里有 `functionSchema`,是实际存在的工具注册表机制:

```json
"functionSchema": [
    {
        "name": "string",
        "description": "string",
        "requireConfirmation": "ENABLED" | "DISABLED",
        "parameters": {
            "paramName": {
                "type": "string" | "number" | "integer" | "boolean" | "array",
                "description": "string",
                "required": true
            }
        }
    }
]
```

**Bedrock 覆盖到的部分:**

- **工具声明/schema**:每个 function 有 `name`、`description`、`parameters`(带 type/required),对应本文件的 `ToolSpec.args_model` + `to_spec_dict()`。
- **requireConfirmation**:function 级别可设 `ENABLED`/`DISABLED`,调用前要求用户确认,目的是防 prompt injection 导致的误操作。对应本文件的 `requires_confirmation` + `CONFIRMATION_GRANTED_ARG` 机制。
- **执行分发**:配置 Lambda ARN 作为 `actionGroupExecutor`,Bedrock 校验完参数后自动转发调用,对应 `call_func`。
- **Return control 模式**:可以不让 Bedrock 直接调 Lambda,而是把预测的 action + 参数原样返回给应用自己处理,这个模式更贴近本文件目前的用法(自己的 ReAct loop 里调 `validate` 再决定要不要执行)。

**Bedrock 没有,本文件独有的部分:**

- `allowed_task_names`——按任务/场景做工具白名单。Bedrock 的 confirmation 是全局开关,不区分"这个工具在任务 A 里能用、任务 B 里不能用"。
- `side_effect_level` / `tag` 这种业务分类维度,Bedrock 没有对应字段。
- Bedrock 有硬限制:每个 function 最多 5 个参数、每个 agent 最多 11 个 function;本文件的 registry 没有这种数量天花板。

## 结论

- Schema 校验 + 确认门槛这两部分,云服务(如 Bedrock Agents 的 function schema + requireConfirmation)基本能覆盖,如果切换过去可以省掉自己维护这部分的心力。
- `allowed_task_names`(任务级白名单)+ `side_effect_level`/`tag` 是强绑定业务语义的定制逻辑,目前没有云托管服务能替代——这也是 Claude Code 自己也自建 permission 层的原因。
- 即使未来切到 Bedrock 之类的云服务,这层 registry 也不会完全消失,只是校验和确认那部分可以交给云,任务级权限逻辑仍需自己维护。
