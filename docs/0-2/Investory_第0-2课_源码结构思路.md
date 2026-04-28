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

## Python venv 操作说明

项目根目录建议使用本地虚拟环境 `.venv/`，不要把依赖直接装进全局 Python。

### 1. 创建虚拟环境

在项目根目录执行：

```powershell
python -m venv .venv
```

如果本机同时有多个 Python 版本，优先确认版本符合 `pyproject.toml` 里的要求：

```powershell
python --version
```

当前项目要求：

```text
Python >= 3.10
```

### 2. 激活虚拟环境

Windows PowerShell：

```powershell
.\.venv\Scripts\Activate.ps1
```

激活成功后，命令行前面通常会出现：

```text
(.venv)
```

如果 PowerShell 阻止脚本执行，可以只给当前终端会话放开权限：

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

macOS / Linux：

```bash
source .venv/bin/activate
```

### 3. 升级 pip

激活虚拟环境后执行：

```powershell
python -m pip install --upgrade pip
```

### 4. 安装项目和开发依赖

当前项目使用 `pyproject.toml` 管理包信息。开发时建议用 editable 模式安装：

```powershell
python -m pip install -e ".[dev]"
```

这一步会让 `src/investory/` 里的源码可以被当前虚拟环境直接导入，同时安装 `dev` 依赖，例如 `pytest`。

### 5. 验证环境

```powershell
python -c "import investory; print('investory import ok')"
pytest
```

如果只想确认命令行入口是否可用：

```powershell
investory
```

### 6. 退出虚拟环境

```powershell
deactivate
```

### 7. 重建虚拟环境

如果依赖装乱了，最简单的方式是删除 `.venv/` 后重新创建：

```powershell
Remove-Item -Recurse -Force .venv
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

`.venv/` 是本机环境目录，不应该提交到 Git。后续如果新增依赖，优先更新 `pyproject.toml`，再重新执行安装命令。

## 一句话结论

`Investory` 在第 `0-2` 课的重点，是先定义一个最小但可继续扩展的运行底座，而不是急着堆功能代码；在目录命名上，优先用 `src/investory/`，而不是根级 `app/`。
