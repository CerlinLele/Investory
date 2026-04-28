# Investory

Investory is a local-first investment learning and task execution project.

## Local Setup

From the repository root, use the project virtual environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

If the virtual environment does not exist yet, create it first:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
```

## Run FastAPI

Start the local FastAPI service with Uvicorn:

```powershell
.\.venv\Scripts\python.exe -m uvicorn investory.main:app --reload
```

The service runs at:

```text
http://127.0.0.1:8000
```

Open the generated API docs at:

```text
http://127.0.0.1:8000/docs
```

The Chapter 0 gateway routes, including `/health` and `/tasks`, are added in the next setup steps.

## CLI Smoke Entry

The existing task runtime smoke command is still available:

```powershell
.\.venv\Scripts\python.exe -m investory.agent_core.runtime.smoke.cli
```

## Run Tests

Run the full test suite:

```powershell
.\.venv\Scripts\python.exe -m pytest
```

Run one test file:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_config.py
```

Run one test case:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_config.py::test_load_config_uses_openai_as_default_provider
```
