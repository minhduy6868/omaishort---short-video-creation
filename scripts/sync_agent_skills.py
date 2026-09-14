"""Rewrite Codex/Claude skill pointers from .cursor/skills.

Canonical skill bodies stay in .cursor/skills/<name>/SKILL.md.
Codex discovers .agents/skills; Claude Code discovers .claude/skills.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANON = ROOT / ".cursor" / "skills"
TARGETS = (ROOT / ".agents" / "skills", ROOT / ".claude" / "skills")
POINTER = """\
---
name: {name}
description: {description}
---

# {name}

Canonical skill: [`{rel}`]({rel})

Read that file now and follow it exactly. Do not invent a second workflow.
"""
_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def _field(block: str, key: str) -> str:
    match = re.search(rf"^{key}:\s*(.+)$", block, flags=re.M)
    if not match:
        raise SystemExit(f"missing {key} in skill frontmatter")
    return match.group(1).strip()


def cursor_skills() -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for path in sorted(CANON.glob("*/SKILL.md")):
        text = path.read_text(encoding="utf-8")
        front = _FRONT.match(text)
        if not front:
            raise SystemExit(f"no YAML frontmatter: {path}")
        block = front.group(1)
        name = _field(block, "name")
        if name != path.parent.name:
            raise SystemExit(f"name {name!r} != folder {path.parent.name}")
        rows.append((name, _field(block, "description")))
    if not rows:
        raise SystemExit(f"no skills under {CANON}")
    return rows


def write_pointers(skills: list[tuple[str, str]]) -> list[Path]:
    written: list[Path] = []
    for dest_root in TARGETS:
        dest_root.mkdir(parents=True, exist_ok=True)
        for name, description in skills:
            folder = dest_root / name
            folder.mkdir(parents=True, exist_ok=True)
            rel = f"../../.cursor/skills/{name}/SKILL.md"
            path = folder / "SKILL.md"
            path.write_text(
                POINTER.format(name=name, description=description, rel=rel),
                encoding="utf-8",
                newline="\n",
            )
            written.append(path)
    return written


def main() -> int:
    written = write_pointers(cursor_skills())
    print(f"wrote {len(written)} pointer skills")
    return 0


if __name__ == "__main__":
    sys.exit(main())
