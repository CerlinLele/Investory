# LangChain Chunking 方法概览

LangChain 常见 chunking / text splitting 方法大致分为以下几类。

## 1. 固定长度切分

代表实现：

- `CharacterTextSplitter`

特点：

- 按字符数切分，简单直接。
- 适合结构不重要、只想快速控制长度的文本。
- 缺点是可能切断句子、表格或段落。

## 2. 递归结构切分

代表实现：

- `RecursiveCharacterTextSplitter`

特点：

- 按优先级递归尝试分隔符，例如段落 `\n\n`、换行 `\n`、空格、字符。
- 这是最常用的默认方案。
- 比固定长度切分更能保留段落和句子边界。
- 与当前 `document_chunker.py` 的实现思路最接近。

## 3. Token-based 切分

代表实现：

- `TokenTextSplitter`
- `CharacterTextSplitter.from_tiktoken_encoder(...)`
- `RecursiveCharacterTextSplitter.from_tiktoken_encoder(...)`

特点：

- 按模型 token 预算切分，而不是按字符数切分。
- 适合严格控制 LLM context 成本和输入长度。
- 对生产 LLM 调用更可靠。

## 4. Markdown / HTML / 代码结构切分

代表实现：

- `MarkdownHeaderTextSplitter`
- `HTMLHeaderTextSplitter`
- `HTMLSectionSplitter`
- `PythonCodeTextSplitter`
- `RecursiveJsonSplitter`

特点：

- 保留文档结构语义。
- 适合技术文档、网页、JSON、代码等结构化文本。
- 不是 PDF factsheet 的首选方案。

## 5. 语义切分

代表实现：

- `SemanticChunker`

特点：

- 基于 embedding 判断语义断点。
- 适合自然语言长文档，希望 chunk 语义更完整的场景。
- 缺点是引入 embedding 成本、额外依赖和不可完全确定性。
- 对当前项目短期不建议优先引入。

## 6. 按文档格式加载器产生的天然分块

常见方式：

- PDF loader 先按页返回 documents，再进行二次 split。

特点：

- 对 PDF 很常见。
- 可以先 page-level，再 paragraph-level 或 token-level。
- 如果要保留页码引用，这是重要方案。

## 对 Investory 当前 PDF review 的建议

### 短期：采用 `RecursiveCharacterTextSplitter` 思路

- 不引入额外复杂 RAG。
- 保留段落边界。
- 可以替代当前手写 `split_into_chunks()`，也可以继续手写以保持轻依赖。

### 中期：token-aware recursive splitting

- 用 token 预算控制每个 LLM 子任务输入。
- 更适合真实模型上下文限制。

### 长期：page-aware + hybrid RAG

- PDF 按页提取并保留 metadata。
- 全文 map-reduce 保证覆盖。
- RAG 只做专题补强。