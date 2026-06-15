# FastAPI File Upload and asyncio Knowledge Notes

## 背景

这份笔记解释的是当前 Investory 在 PDF 文件上传审查链路里遇到的一个典型问题：

```text
RuntimeError: asyncio.run() cannot be called from a running event loop
```

它出现在：

- `src/investory/gateway/api.py`
- 路由：`POST /investment-document-review-file`

这不是 PDF 提取本身的问题，而是 `FastAPI 异步请求上下文` 和 `内部同步 flow 实现` 的边界问题。

## 先说结论

一句话版：

- `asyncio.run()` 只能在“当前线程没有运行事件循环”时调用。
- FastAPI 的 `async def` endpoint 已经运行在事件循环里。
- 如果这个 endpoint 里直接调用一个内部会 `asyncio.run()` 的同步函数，就会报错。

当前修复方式是：

- 在异步 endpoint 中，用 `await asyncio.to_thread(...)`
- 把同步 review flow 挪到线程里执行
- 这样线程里没有正在运行的事件循环，内部的 `asyncio.run()` 就可以正常工作

## 相关代码位置

### 1. 异步文件上传入口

文件：

- `src/investory/gateway/api.py`

当前实现重点：

```python
@router.post(INVESTMENT_DOCUMENT_REVIEW_FILE_ROUTE, response_model=TaskResponse)
async def run_investment_document_review_file(...):
    file_bytes = await upload.file.read()
    ...
    return await asyncio.to_thread(
        execute_investment_document_review_request,
        review_request,
        flow=flow,
    )
```

这里有两个重要信号：

1. 这个 endpoint 是 `async def`
2. 它内部通过 `await upload.file.read()` 读取上传文件，说明它本身就在异步请求链路里

### 2. 内部同步 review flow

文件：

- `src/investory/gateway/api.py`
- `src/investory/agent_core/runtime/flow/investment_document_review/document_review_flow.py`

中间调用链：

```text
run_investment_document_review_file
  -> execute_investment_document_review_request
  -> resolved_flow.run(...)
  -> graph.invoke(...)
  -> execute_review_todo_plan(...)
```

而在 `execute_review_todo_plan(...)` 里，之前就有：

```python
todo_results = asyncio.run(
    runner.run(state.todo_plan, resume_state=resume_state)
)
```

这就是冲突点。

## 什么是事件循环

可以把事件循环理解成：

- 一个负责调度异步任务的运行环境
- 它让 `await`、异步 IO、并发任务在同一线程里协作执行

在 Python `asyncio` 里：

- `async def` 定义协程函数
- `await` 等待协程或 awaitable
- 事件循环负责真正驱动这些协程执行

FastAPI 的 `async def` endpoint 运行时，当前线程已经处于一个活动事件循环里。

## 为什么 `asyncio.run()` 会报错

`asyncio.run(coro)` 的语义不是“在当前循环里运行这个协程”，而是：

1. 创建一个新的事件循环
2. 在这个新循环里运行协程
3. 运行结束后关闭这个循环

因此它只能在“当前线程还没有正在运行的事件循环”时使用。

如果当前线程已经在跑 FastAPI 的事件循环，再执行：

```python
asyncio.run(...)
```

Python 会直接拒绝，因为这等于想在一个已经运行事件循环的线程里再开一个新的主运行循环。

所以错误才会是：

```text
asyncio.run() cannot be called from a running event loop
```

## 为什么 JSON endpoint 没炸，file upload endpoint 炸了

这是理解这个问题最关键的一点。

### JSON endpoint

当前 JSON 审查入口是：

```python
@router.post(INVESTMENT_DOCUMENT_REVIEW_ROUTE, response_model=TaskResponse)
def run_investment_document_review(...):
    return execute_investment_document_review_request(...)
```

注意它是：

```python
def
```

不是：

```python
async def
```

这意味着它走的是同步 endpoint 路径。对这类同步函数，FastAPI / Starlette 通常会在线程池里执行它，而不是直接放在事件循环线程里跑。

在线程池线程里：

- 当前线程通常没有运行中的事件循环
- 所以内部 `asyncio.run()` 可以工作

### File upload endpoint

文件上传入口是：

```python
async def run_investment_document_review_file(...)
```

它直接运行在事件循环线程里，因此一旦同步 flow 继续往下调到 `asyncio.run()`，就会冲突。

所以：

- 不是“file upload 特别特殊”
- 而是“file upload 这个 endpoint 恰好是异步的”
- 异步 endpoint 更容易暴露内部同步实现里潜藏的事件循环边界问题

## 为什么这里用了 `asyncio.to_thread`

修复方式很多，但当前这个项目里，`asyncio.to_thread(...)` 是一个很合适的小修复。

### 作用

`asyncio.to_thread(func, *args, **kwargs)` 会：

- 把一个同步函数丢到后台线程执行
- 返回一个可以 `await` 的结果

也就是说：

- 外层 endpoint 还是异步的
- 但重 CPU / 同步阻塞 / 内部会 `asyncio.run()` 的那段逻辑，被隔离到普通线程中

### 为什么这在这里成立

因为线程里没有已经运行的 FastAPI 事件循环，所以：

```python
asyncio.run(...)
```

又重新变成合法操作。

### 当前修复代码

```python
return await asyncio.to_thread(
    execute_investment_document_review_request,
    review_request,
    flow=flow,
)
```

这个修复的优点是：

- 改动小
- 不需要重写整个 flow 为 async
- 不影响现有同步 JSON endpoint
- 直接解决 file upload 入口的事件循环冲突

## 为什么不直接把 `execute_review_todo_plan()` 改成 async

这是一个自然会想到的问题。

理论上可以，但在当前项目里代价更高。

原因是：

- `document_review_flow.py` 里的 flow 构建、graph 节点、executor 调用基本都是同步风格
- `flow.run(...)` 也是同步接口
- `graph.invoke(...)` 这条链路当前是按同步方式组织的

如果强行把其中一个节点改成 async，通常会连带引出：

- graph 节点接口改造
- flow 调用链改造
- gateway 调用方式改造
- 测试大面积跟着改

所以对这个问题来说，`to_thread` 是一个很合理的边界修复。

## 这个问题体现了什么设计知识点

### 1. 异步边界要清楚

系统里要明确：

- 哪一层是 async
- 哪一层是 sync
- 二者在什么位置切换

如果边界不清楚，就会出现：

- 在 async 上下文里调用不该直接调用的 sync 实现
- 或者在 sync 实现里偷偷管理自己的事件循环

### 2. `asyncio.run()` 更像程序入口工具

`asyncio.run()` 最适合用在：

- CLI 程序入口
- 测试中的小型 async 驱动
- 当前线程明确没有事件循环时

它不太适合被深埋在：

- Web 请求处理链路内部
- 可能被 async 上下文调用的共享库内部

因为这样会把“事件循环管理权”藏在太深的位置。

### 3. Web 框架里的 sync / async endpoint 语义不同

在 FastAPI 里：

- `def endpoint(...)` 和 `async def endpoint(...)`
- 虽然看起来都能正常对外提供 HTTP 接口
- 但它们运行时所在的执行环境并不一样

这个差异会影响：

- 阻塞 IO 是否安全
- CPU 密集逻辑如何放置
- 能不能直接 `await`
- 能不能在内部再 `asyncio.run()`

### 4. 文件上传常常是边界问题放大器

文件上传接口常常会同时碰到：

- 异步读取文件
- 同步解析文件
- CPU 或 IO 较重的下游处理
- LLM / OCR / 分块等后续链路

所以它很容易成为“同步异步边界设计是否清楚”的试金石。

## 测试是怎么覆盖这个问题的

文件：

- `tests/test_investment_document_review_gateway_api.py`

新增的关键测试是：

```python
test_investment_document_review_file_endpoint_runs_flow_without_event_loop_error
```

这个测试做了两件有价值的事：

1. `patch("investory.gateway.api.extract_text_from_pdf", ...)`

这样测试不会依赖真实 PDF 解析质量，而是专注在 gateway 调用链本身。

2. 走真实的 multipart file upload endpoint

这样验证的是：

- `/investment-document-review-file`
- 异步 endpoint
- 文件字段解析
- flow 调用

这一整条路径不会再因为事件循环冲突报 500。

## 什么时候该继续重构

当前修复是好的，但它不是永远的最终形态。

如果未来出现这些信号，可以考虑更系统地重构：

- Flow 内部异步任务越来越多
- `asyncio.run()` 在多个共享模块里出现
- 同步 / 异步入口越来越混杂
- 线程切换开始变多，调试困难

那时候更理想的方向通常是：

- 明确一套 async-first 的 flow 执行模型
- 或者明确把异步部分集中到更高一层管理

但在当前阶段，这种大改不一定划算。

## 对当前项目的实用建议

### 1. 在共享库深处谨慎使用 `asyncio.run()`

如果一个函数可能被：

- CLI 调用
- 测试调用
- Web 同步入口调用
- Web 异步入口调用

那就要特别小心它是否自己创建事件循环。

### 2. 遇到 async endpoint + 重同步逻辑时，优先考虑线程隔离

像这次这样，如果：

- 外层必须是 async
- 内层暂时仍是同步体系

那 `asyncio.to_thread(...)` 是很实用的折中手段。

### 3. 测试不要只测 happy path 的 JSON endpoint

如果项目同时有：

- JSON endpoint
- multipart file upload endpoint

那么两者都应该有独立测试，因为它们的运行时语义可能不同。

## 一句话总结

这次问题的本质不是 PDF，也不是 FastAPI“有 bug”，而是：

```text
异步 HTTP 入口直接调用了一个内部会 asyncio.run() 的同步执行链
```

而当前修复的核心思想是：

```text
把同步执行链放到线程里跑，避开当前事件循环线程
```

这是一种非常典型、也非常值得记住的 Python Web 开发知识点。
