# Investory Coding Rules

These rules apply to all AI coding assistants working in this repository.

## Use The Repository `.venv`

Python environment actions in this repository should use the local `.venv` at the repo root.

- When installing new packages, use the `.venv` interpreter and package manager, not a global Python or user-level environment.
- When checking whether a dependency exists, check from `.venv`.
- When running tests, run them from `.venv`.
- If `.venv` is missing or broken, do not silently fall back to a global environment. Call that out explicitly and wait for direction or repair the local environment in a scoped way.

## Typed Constants Over Raw Strings

Fixed business strings should not be scattered inline through the codebase.

- Use `str, Enum` for closed sets that represent state, route decisions, task categories, or externally meaningful options.
- Use module-level constants for stable identifiers such as task names, prompt names, registry keys, and aliases.
- Use one constant when two fields intentionally share the same value, instead of creating duplicated constants.

Example:

```python
class LearningEntryDecision(str, Enum):
    ASK_FOR_MISSING_INPUT = "ask_for_missing_input"
    REFUSE_AND_REDIRECT = "refuse_and_redirect"
    EXECUTE_LEARNING_TASK = "execute_learning_task"
```

```python
FINANCE_QA_NAME = "finance_qa"

FINANCE_QA_TASK = TaskSpec(
    name=FINANCE_QA_NAME,
    prompt_name=FINANCE_QA_NAME,
    ...
)
```

## Plan Step Worklog Discipline

When executing a user-approved plan step, updating the corresponding worklog is part of completing the step, not an optional follow-up.

- Do not treat a plan step as complete until the step's worklog entry has been added or updated.
- Before switching to commit-message, staging, or other housekeeping-only requests for the same step, first ensure the worklog is up to date.
- If code or tests for a plan step are already finished but the worklog is missing, prioritize repairing the worklog gap before continuing to the next step.
- For step-based execution, use this closeout order: implementation, verification, worklog update, then next-step/commit support.

## Save Document Requests

When the user asks to save a plan, analysis, or other markdown to a docs path (for example under `docs/` or `afterclass/`), treat that as a documentation-only task.

- Write or update only the requested file(s).
- Do not start implementing the plan, install dependencies, or change application code unless the user explicitly asks to implement or execute the plan in the same message or a clear follow-up.
- After saving, confirm the path briefly; do not proceed to todos, commits, or code changes on your own.