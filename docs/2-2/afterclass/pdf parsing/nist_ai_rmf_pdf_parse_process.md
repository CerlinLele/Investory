# NIST AI RMF PDF 解析过程记录

## 目标

记录如果在 Codex 中解析 `data/NIST.AI.100-1.pdf`，我会采用的本地处理方式、实际观察结果，以及它对当前 Investory 文档审查与分块测试的意义。

## 输入文件

- 文件路径：`data/NIST.AI.100-1.pdf`
- 文件大小：`1,946,127` bytes
- 文档来源语义：NIST AI Risk Management Framework 1.0
- 适合的 Investory `document_type_hint`：`learning_material`

该 PDF 不是 ETF factsheet、fund prospectus、product brochure 或 earnings report。为了让 `/investment-document-review-file` 稳定进入审查链路，建议显式传入：

```text
document_type_hint=learning_material
```

## 我会采用的解析方式

优先使用仓库本地 `.venv` 中已经安装的 `pdfplumber`，原因是当前 gateway 的 PDF 上传接口本身也是用 `pdfplumber`：

- 代码位置：`src/investory/gateway/pdf_extractor.py`
- 入口函数：`extract_text_from_pdf(file_bytes: bytes) -> str`
- 行为：从内存中的 PDF bytes 打开文件，逐页 `extract_text()`，跳过空页，用空行拼接页面，并压缩 3 个以上连续换行。

我不会优先用全局 Python 或额外安装工具，因为本仓库规则要求 Python 行为使用 repo root 下的 `.venv`。

## 依赖检查

执行的检查命令：

```powershell
.\.venv\Scripts\python.exe -c "import importlib.util as u; print({m: bool(u.find_spec(m)) for m in ['pdfplumber','pypdf','fitz']})"
```

结果：

```text
{'pdfplumber': True, 'pypdf': False, 'fitz': False}
```

结论：

- `pdfplumber` 可用，可以按项目真实 PDF 上传链路解析。
- `pypdf` 和 `fitz` 当前不可用，因此不作为本次主路径。

## 页级解析统计

执行的解析统计命令：

```powershell
.\.venv\Scripts\python.exe -c "import pdfplumber, statistics; from pathlib import Path; p=Path('data/NIST.AI.100-1.pdf'); pdf=pdfplumber.open(p); texts=[page.extract_text() or '' for page in pdf.pages]; pdf.close(); counts=[len(t) for t in texts]; words=[len(' '.join(t.split()).split()) for t in texts]; empty=[i+1 for i,t in enumerate(texts) if not ' '.join(t.split())]; print('file=',p); print('size_bytes=',p.stat().st_size); print('pages=',len(texts)); print('total_chars=',sum(counts)); print('approx_words=',sum(words)); print('empty_pages=',empty); print('min_chars=',min(counts)); print('median_chars=',int(statistics.median(counts))); print('max_chars=',max(counts)); print('first_12_page_stats=',[(i+1,counts[i],words[i]) for i in range(min(12,len(texts)))]); print('last_5_page_stats=',[(len(texts)-5+i+1,counts[-5+i],words[-5+i]) for i in range(min(5,len(texts)))])"
```

结果摘要：

| Metric | Value |
|---|---:|
| Pages | `48` |
| Extracted characters | `101,186` |
| Approximate words | `10,656` |
| Empty pages | `[]` |
| Minimum page characters | `76` |
| Median page characters | `2,357` |
| Maximum page characters | `3,025` |

前 12 页页级统计：

```text
[(1, 76, 11), (2, 344, 18), (3, 1402, 108), (4, 1133, 112), (5, 1585, 211), (6, 2921, 285), (7, 3025, 400), (8, 1808, 223), (9, 2600, 271), (10, 1740, 134), (11, 2640, 295), (12, 2843, 318)]
```

最后 5 页页级统计：

```text
[(44, 2469, 223), (45, 2630, 331), (46, 2062, 207), (47, 2381, 299), (48, 81, 2)]
```

## 与项目分块逻辑对齐

当前项目真实分块逻辑位于：

- `src/investory/agent_core/runtime/flow/investment_document_review/document_chunker.py`

关键参数：

```python
CHUNK_SIZE = 500
CHUNK_OVERLAP = 50
CHUNK_SEPARATORS = ["\n\n", "\n", ". ", " ", ""]
```

该实现使用 LangChain 的 `RecursiveCharacterTextSplitter`，并保留分隔符。它更接近真实 flow 行为，比手动按字符硬切更适合作为测试结论来源。

执行的真实分块检查命令：

```powershell
.\.venv\Scripts\python.exe -c "import pdfplumber; from pathlib import Path; from investory.agent_core.runtime.flow.investment_document_review.document_chunker import split_into_chunks, CHUNK_SIZE, CHUNK_OVERLAP; p=Path('data/NIST.AI.100-1.pdf'); pdf=pdfplumber.open(p); text='\n\n'.join((page.extract_text() or '').strip() for page in pdf.pages if (page.extract_text() or '').strip()); pdf.close(); chunks=split_into_chunks(text); print('full_text_chars=',len(text)); print('chunk_size=',CHUNK_SIZE); print('chunk_overlap=',CHUNK_OVERLAP); print('chunk_count=',len(chunks)); print('first_chunk_chars=',len(chunks[0])); print('last_chunk_chars=',len(chunks[-1])); print('first_chunk_preview=', ' '.join(chunks[0].split())[:500]); print('chunk_10_preview=', ' '.join(chunks[9].split())[:500] if len(chunks) >= 10 else '')"
```

结果：

```text
full_text_chars= 101280
chunk_size= 500
chunk_overlap= 50
chunk_count= 239
first_chunk_chars= 422
last_chunk_chars= 81
```

结论：

- 这个 PDF 对当前 `CHUNK_SIZE=500` 来说非常长。
- 一次完整 `/investment-document-review-file` 可能生成约 `239` 个 extract chunk tasks，再进入 aggregate analyze 和 final synthesize。
- 它适合测试长文档分块能力，但不适合作为日常 smoke test，因为会触发大量 LLM 调用，成本和耗时都高。

## 文本质量观察

`pdfplumber` 能成功抽取所有页面文本，没有空页。第一页和目录页存在典型 PDF 排版抽取问题，例如单词之间空格缺失：

```text
Thispublicationisavailablefreeofchargefrom:
January2023
U.S.DepartmentofCommerce
```

这类问题不会阻止分块测试，但会影响模型阅读体验。对结构化审查而言，后续可以考虑增加轻量文本清理，例如：

- 修复过密的页眉页脚文本。
- 去除重复标题。
- 保留页码 metadata，便于结果引用来源页。
- 对目录页和参考文献页做低优先级处理。

## 在 Apifox 中测试的建议

文件上传接口：

```text
POST http://127.0.0.1:8000/investment-document-review-file
Content-Type: multipart/form-data
```

Body 字段：

| Key | Type | Value |
|---|---|---|
| `file` | File | `data/NIST.AI.100-1.pdf` |
| `review_goal` | Text | `Summarize the core AI risk management concepts and identify main implementation considerations` |
| `document_type_hint` | Text | `learning_material` |
| `session_id` | Text | `apifox-nist-pdf-learning-material` |

稳定断言：

- `ok == true`
- `task_name == "investment_document_review"`
- `result.action == "complete"`
- `result.document_type == "learning_material"`
- `result.review != null`

日志观察关键词：

```text
investment_document_review.todo_plan.generated
investment_document_review.todo_task.started
task_id=extract_chunk_
investment_document_review.todo_execution.completed
```

## 我的判断

如果目标是“测试 PDF 能不能被上传、提取、进入审查 flow”，这份 NIST PDF 可以用，但比较重。

如果目标是“稳定快速地手工 smoke test”，建议准备一个更短的 PDF 或只截取前几页生成测试 PDF。

如果目标是“压力测试 chunk map-reduce 路径”，这份 NIST PDF 很合适，因为它会真实触发大量 chunks，能暴露任务计划生成、逐 chunk extract、日志、失败恢复和最终 synthesize 的问题。
