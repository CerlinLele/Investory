# web_search vs instrument_profile 工具差异说明

## 1. 目标不同

- `web_search.search_web`：做网页检索，返回结果列表。
- `instrument_profile.fetch_instrument_profile`：做单个标的资料提取，返回单份 `source_material`。

## 2. 输入不同

- `search_web(query, top_k, provider_hint)`
- `fetch_instrument_profile(instrument_name_or_code)`

## 3. 候选构造不同

- `web_search`：按 provider 顺序构造（支持 `provider_hint` + 配置顺序）。
- `instrument_profile`：按固定 source URL 列表构造。

## 4. 解析成功判定不同

- `web_search`：`snippet` 为空即 `parse_error`。
- `instrument_profile`：提取文本长度 `< MIN_SOURCE_MATERIAL_CHARS` 即 `parse_error`。

## 5. 成功返回结构不同

- `web_search` 返回：
  - `query`
  - `results`（`title/url/snippet/source/provider`）
  - `provider_attempt_order`
- `instrument_profile` 返回：
  - `instrument_name_or_code`
  - `source_material`
  - `sources`
  - `as_of`

## 6. 默认错误文案不同

- `web_search`：
  - `No reachable search provider found.`
  - `Web search failed.`
- `instrument_profile`：
  - `No reachable source found for '<code>'.`
  - `Failed to fetch instrument profile.`

## 7. 共用部分

两者已复用同一套 HTTP 执行框架：

- `src/investory/agent_core/tools/http_runner.py`
- `src/investory/agent_core/tools/http_tooling_common.py`

当前主要差异保留在业务层（候选构造、解析阈值、payload 结构与错误文案）。
