from investory.agent_core.contracts.todo_execution import TodoExecutionPlan, TodoTaskSpec
from investory.agent_core.runtime.todo_core.plan_validator import ensure_valid_todo_plan


def build_dependency_layers(plan: TodoExecutionPlan) -> list[list[TodoTaskSpec]]:
    ensure_valid_todo_plan(plan)

    tasks_by_id = {task.id: task for task in plan.tasks}
    task_order = {task.id: index for index, task in enumerate(plan.tasks)}

    # Edge direction: dependency -> dependent task.
    children_map: dict[str, list[str]] = {task.id: [] for task in plan.tasks}
    unresolved_dependency_count: dict[str, int] = {}

    for task in plan.tasks:
        unresolved_dependency_count[task.id] = len(task.depends_on)
        for dependency_task_id in task.depends_on:
            children_map[dependency_task_id].append(task.id)

    current_layer_ids = [
        task.id
        for task in plan.tasks
        if unresolved_dependency_count[task.id] == 0
    ]

    layers: list[list[TodoTaskSpec]] = []
    resolved_count = 0

    while current_layer_ids:
        current_layer_ids.sort(key=lambda task_id: task_order[task_id])
        current_layer = [tasks_by_id[task_id] for task_id in current_layer_ids]
        layers.append(current_layer)
        resolved_count += len(current_layer_ids)

        next_layer_candidates: set[str] = set()
        for task_id in current_layer_ids:
            for child_task_id in children_map[task_id]:
                unresolved_dependency_count[child_task_id] -= 1
                if unresolved_dependency_count[child_task_id] == 0:
                    next_layer_candidates.add(child_task_id)

        current_layer_ids = list(next_layer_candidates)

    if resolved_count != len(plan.tasks):
        raise ValueError(
            "Todo dependency layering failed: unresolved tasks remain after topological layering."
        )

    return layers
