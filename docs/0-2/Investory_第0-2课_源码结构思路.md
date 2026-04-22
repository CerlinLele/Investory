# 映射回 Investory：第 0-2 课在项目里的源码结构应该怎么想

如果把这节课的源码思路映射到 `Investory`，你现在最少应该先想清楚这几个文件角色，即使先不写代码：

```text
investory/
  src/
    investory/
      main.py
      config.py
      gateway/
      runtime/
      memory/
      eval/
  .env.example
  config.example.yaml
  tests/
  logs/
  data/
```

## 这些位置在第 0-2 课里的职责

- `.env.example`
  - 放模型 key、provider key、工具 key

- `config.example.yaml`
  - 放默认模型、任务开关、日志目录、data 目录、mock tool 开关

- `src/investory/main.py`
  - 定义最小运行入口

- `src/investory/config.py`
  - 统一解析配置，不让代码到处 `os.getenv`

- `logs/`
  - 预留运行日志

- `data/`
  - 预留 session / eval / task records

- `tests/`
  - 预留 smoke test 和后续 regression 位置

## 这部分真正想表达什么

第 `0-2` 课在 `Investory` 里不是“先做功能”，而是：

**先把未来会反复扩展的壳搭出语义。**

也就是说，现在最重要的不是功能多少，而是先明确：

- 配置从哪里进系统
- 运行入口在哪里
- 日志和数据放在哪里
- 测试将来放在哪里
- 后续章节往哪个源码目录里继续长

这里对 `Investory` 来说，建议采用：

- `src/`
  - 作为仓库级源码根目录

- `src/investory/`
  - 作为项目主包目录，后续章节里的模块都往这里继续长

## 一句话结论

`Investory` 在第 `0-2` 课的重点，是先定义一个最小但可继续扩展的运行底座，而不是急着堆功能代码；在目录命名上，优先用 `src/investory/`，而不是根级 `app/`。
