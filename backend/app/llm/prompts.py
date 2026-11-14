"""Load and render versioned prompt files from app/prompts/<name>.v<N>.md.

File format: `## system`, `## user` and optional `## repair` sections; `{{var}}`
placeholders. Rendering fails loudly on a missing or unused variable.
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"
_SECTION = re.compile(r"^## (system|user|repair)\s*$", re.MULTILINE)
_VAR = re.compile(r"\{\{(\w+)\}\}")


@dataclass(frozen=True)
class Prompt:
    version: str  # e.g. "jd_parse.v1"
    system: str
    user: str
    repair: str | None


def render(template: str, variables: dict[str, str]) -> str:
    wanted = set(_VAR.findall(template))
    missing = wanted - variables.keys()
    if missing:
        raise KeyError(f"prompt variables not provided: {sorted(missing)}")
    unused = variables.keys() - wanted
    if unused:
        raise KeyError(f"prompt variables not used by template: {sorted(unused)}")
    return _VAR.sub(lambda m: variables[m.group(1)], template)


@cache
def load_prompt(version: str) -> Prompt:
    path = PROMPTS_DIR / f"{version}.md"
    text = path.read_text(encoding="utf-8")
    parts = _SECTION.split(text)
    sections = {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}
    if "system" not in sections or "user" not in sections:
        raise ValueError(f"{path.name} must have '## system' and '## user' sections")
    return Prompt(
        version=version,
        system=sections["system"],
        user=sections["user"],
        repair=sections.get("repair"),
    )
