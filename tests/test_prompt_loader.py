from pathlib import Path

import pytest

from investory.agent_core.runtime import prompt_loader


def test_load_prompt_text_reads_utf8_prompt(monkeypatch, tmp_path: Path):
    prompt_dir = tmp_path / "prompts"
    prompt_file = prompt_dir / "base" / "system.md"
    prompt_file.parent.mkdir(parents=True)
    prompt_file.write_text("You are an investment learning assistant.", encoding="utf-8")
    monkeypatch.setattr(prompt_loader, "PROMPTS_DIR", prompt_dir)

    prompt = prompt_loader.load_prompt_text("base", "system.md")

    assert prompt == "You are an investment learning assistant."


def test_load_prompt_text_raises_for_missing_prompt(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(prompt_loader, "PROMPTS_DIR", tmp_path)

    with pytest.raises(FileNotFoundError):
        prompt_loader.load_prompt_text("tasks", "missing.md")
