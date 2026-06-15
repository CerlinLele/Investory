# 长文档处理问题分析

## 当前状态

`document_text` 字段会被 `json.dumps` 序列化后直接塞进 prompt，整个 payload 原封不动发给 LLM。`message_builder.py` 里没有任何 token 计数、截断、分段或分批处理机制。

```text
src/investory/agent_core/runtime/message_builder.py
build_prompt_messages()
  -> json.dumps(payload)         # 直接序列化，无长度限制
  -> ChatPromptTemplate.invoke() # 直接发给 LLM
```

**实际影响**

| 文档类型 | 典型提取文字量 | 风险 |
|---|---|---|
| ETF factsheet（1-3 页） | 500-2000 字 | 基本安全 |
| 基金招募说明书 | 5000-30000 字 | 可能超出 prompt 有效范围 |
| Prospectus / N-1A | 50000-200000 字 | 大概率超出 context window |

超出 context window 时视 provider 而定：OpenAI gpt-4o 是 128k tokens，但整个 prompt 还包含 system prompt + task instructions，实际可用给 `document_text` 的空间约 100k tokens（约 75000 字），超出会报错。

---

## 三条处理路线

### 路线 A：接口层硬拒绝（推荐用于 v1）

在 policy gate 里加字符数检查，超过阈值返回 `ask_for_missing_input`，明确告知用户需要截取关键段落。

优点：实现简单，边界清晰，用户知道限制在哪。  
缺点：用户体验有摩擦，不支持真实完整文档审查。

建议阈值：**8000 字符**（约 6000 英文词 / 4000 汉字，覆盖 ETF factsheet 全文有余）。

实现位置：`document_review_rules.py` 的 policy gate 检查逻辑。

### 路线 B：静默截断 + warning 字段

接收任意长度，进入 flow 前截断到安全范围，result 里带 `document_truncated: true`。

优点：不拒绝用户输入。  
缺点：截断位置难以保证语义完整；用户可能不注意 warning，误以为整篇文档都被审查了。

### 路线 C：接 To-Do DAG 做分段审查

Phase 5 的 `generate_review_todo_plan` + `execute_review_todo_plan` 把文档审查拆成 extract → analyze → synthesize 多个子任务，让每个 LLM 调用的任务范围更窄，输出更专注，结果可追溯。

**但路线 C 不解决 token 量问题。** 查看 `InvestmentDocumentReviewExtractInput` 和 `InvestmentDocumentReviewAnalyzeInput`，两者都有 `document_text: str = Field(description="Full text of ...")` ——每个子任务拿到的仍是原封不动的全文，token 总量不减少。

| 路线 | 解决了什么 | 没解决什么 |
|---|---|---|
| A（硬拒绝） | token 超限 | 用户体验差，不支持长文档 |
| B（静默截断） | token 超限 | 截断破坏语义，用户误以为全文被审查 |
| C（To-Do DAG） | 审查逻辑模块化、结果可追溯性 | token 总量，每子任务仍传完整文档 |

### 路线 D：To-Do DAG + 按 focus 检索/切片（长期方向）

真正解决长文档 token 问题需要在分发子任务时做 retrieval：`execute_review_todo_plan` 分配 extract 子任务时，按该任务的 `extract_focus` 从全文里切出相关段落，而不是把全文都传进去。路线 C 的 DAG 结构为这一步提供了自然接入点，但目前没有实现。

---

## v1 建议

采用**路线 A**，等 To-Do DAG + retrieval 方案成熟后升级到路线 D。

在测试计划和文档里明确标注：`document_text` 建议控制在 **8000 字符以内**，对应约 1-2 页 factsheet 的有效内容密度。超长内容请截取核心段落（费率表、风险披露、关键条款）后提交。

---

## 与真实 PDF 提取的关系

PDF 本身不是问题，问题在于提取质量和文字量：

- ETF factsheet：用 `pdfplumber` 提取，通常 1-2 页，提取后清理页眉页脚即可直接用
- Prospectus：不适合 v1 single-pass 模式，需要 To-Do DAG 分段处理

```python
import pdfplumber
with pdfplumber.open("factsheet.pdf") as pdf:
    text = "\n".join(p.extract_text() for p in pdf.pages if p.extract_text())
# 提取后人工扫一眼，去掉页眉页脚、ISIN 编号等噪音
```