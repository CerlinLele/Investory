import pytest
from investory.agent_core.tasks import TASKS, FINANCE_QA_TASK, INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK
from investory.gateway.routing import (
    list_specs_by_tag,
    list_specs_by_side_effect,
    get_spec_metadata,
)


class TestTasksMetadata:
    """Verify all tasks have valid governance metadata."""

    def test_all_tasks_have_side_effect_level(self):
        """Every task must have a side_effect_level."""
        valid_levels = {"read", "write", "exec"}
        for spec in TASKS.values():
            assert spec.side_effect_level in valid_levels, (
                f"{spec.name} has invalid side_effect_level: {spec.side_effect_level}"
            )

    def test_all_tasks_have_desc(self):
        """Every task should have a description."""
        for spec in TASKS.values():
            assert spec.desc and len(spec.desc) > 0, (
                f"{spec.name} has no description"
            )

    def test_write_tasks_are_tagged(self):
        """All side_effect_level=write tasks should have a corresponding tag."""
        write_tasks = list_specs_by_side_effect("write")
        assert len(write_tasks) > 0, "Should have at least one write task"
        for spec in write_tasks:
            assert spec.tag, f"{spec.name} is write-level but has no tag"

    def test_list_specs_by_tag(self):
        """Querying by tag should return the correct task set."""
        learning_tasks = list_specs_by_tag("learning")
        assert len(learning_tasks) == 3, "Should have 3 learning tasks"
        assert all(spec.tag == "learning" for spec in learning_tasks)

        document_review_tasks = list_specs_by_tag("document_review")
        assert len(document_review_tasks) == 5, "Should have 5 document_review tasks"

        risk_tasks = list_specs_by_tag("risk")
        assert len(risk_tasks) == 2, "Should have 2 risk tasks"

    def test_list_specs_by_side_effect(self):
        """Querying by side_effect_level should return the correct task set."""
        read_tasks = list_specs_by_side_effect("read")
        assert len(read_tasks) == 9, "Should have 9 read-level tasks"
        assert all(spec.side_effect_level == "read" for spec in read_tasks)

        write_tasks = list_specs_by_side_effect("write")
        assert len(write_tasks) == 1, "Should have 1 write-level task"
        assert write_tasks[0].name == INVESTMENT_DOCUMENT_RISK_ASSESSMENT_TASK.name

    def test_get_spec_metadata(self):
        """Should correctly retrieve a single task's metadata."""
        metadata = get_spec_metadata(FINANCE_QA_TASK.name)
        assert metadata["side_effect_level"] == "read"
        assert metadata["tag"] == "learning"
        assert "Answer" in metadata["desc"]
