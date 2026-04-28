from pathlib import Path


PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def load_prompt_text(*parts: str) -> str:
    return PROMPTS_DIR.joinpath(*parts).read_text(encoding="utf-8")
