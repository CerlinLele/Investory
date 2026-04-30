# Investory

Investory is a local-first investment learning and task execution project.

## Local Setup

From the repository root, create the virtual environment if it does not exist yet:

```powershell
python -m venv .venv
```

Activate the virtual environment before running the remaining commands:

```powershell
.\.venv\Scripts\Activate.ps1
```

Install the project in the activated environment:

```powershell
python -m pip install -e .
```

## Run FastAPI

Start the local FastAPI service with Uvicorn:

```powershell
python -m uvicorn investory.main:app --reload
```

The service runs at:

```text
http://127.0.0.1:8000
```

Open the generated API docs at:

```text
http://127.0.0.1:8000/docs
```

Check service health:

```powershell
Invoke-RestMethod -Method Get -Uri http://127.0.0.1:8000/health
```

Run the minimal task gateway:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/tasks `
  -ContentType "application/json" `
  -Body '{"task_type":"qa","payload":{"material_text":"ETF is a basket of assets.","question":"What is ETF?"}}'
```

## CLI Smoke Entry

The existing task runtime smoke command is still available:

```powershell
python -m investory.agent_core.runtime.smoke.cli
```

## Run Tests

Run the full test suite:

```powershell
python -m pytest
```

Run one test file:

```powershell
python -m pytest tests\test_config.py
```

Run one test case:

```powershell
python -m pytest tests\test_config.py::test_load_config_uses_openai_as_default_provider
```
