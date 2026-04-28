# Smoke Tests

This folder contains manual smoke checks for the Investory agent runtime.

Use smoke tests after unit tests pass and after local LLM provider environment
variables are configured. These checks may call the configured LLM provider.

## Entry Point

Preferred command after installing the package in editable mode:

```powershell
investory-smoke --help
```

Equivalent module command from the repository root:

```powershell
.\.venv\Scripts\python.exe -m investory.agent_core.runtime.smoke.cli --help
```

## Provider Smoke Test

Check provider configuration without sending a model request:

```powershell
investory-smoke provider --check-config-only
```

Run a minimal provider request:

```powershell
investory-smoke provider
```

Use a custom prompt:

```powershell
investory-smoke provider --prompt "Answer in one sentence: What is Investory?"
```

This command prints the selected provider, model, base URL, API key env name,
and whether the API key is configured.

## Task Smoke Test

Run the default task smoke test:

```powershell
investory-smoke task
```

Run a specific registered task:

```powershell
investory-smoke task --task finance_qa
investory-smoke task --task learning_material_summary
```

Task smoke tests run the full task executor path:

1. Validate the payload with the task input model.
2. Load prompts from `agent_core/prompts/`.
3. Build LangChain messages.
4. Invoke the configured model with structured output.
5. Print the resulting `TaskResult` JSON.

## Exit Codes

- `0`: smoke check passed.
- `1`: provider request or task execution failed.
- `2`: required configuration is missing, or the task name is unknown.

## Notes

- Run unit tests before smoke tests: `.\.venv\Scripts\python.exe -m pytest`.
- Smoke tests are not unit tests and should not be required for every local edit.
- Do not commit real API keys. Configure keys through local environment variables.
