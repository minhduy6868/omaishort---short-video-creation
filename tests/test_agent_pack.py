from pathlib import Path

from sync_agent_skills import TARGETS, cursor_skills, write_pointers

ROOT = Path(__file__).resolve().parents[1]


def test_cursor_skills_have_matching_codex_and_claude_pointers():
    skills = cursor_skills()
    names = {name for name, _desc in skills}
    assert names == {
        "backend-api",
        "character-bible",
        "frontend-ui",
        "refactor",
        "render-short",
        "scene-planner",
        "source-research",
        "story-analyzer",
        "test",
    }
    for dest in TARGETS:
        for name, description in skills:
            text = (dest / name / "SKILL.md").read_text(encoding="utf-8")
            assert f"name: {name}" in text
            assert description in text
            assert f".cursor/skills/{name}/SKILL.md" in text


def test_sync_agent_skills_is_idempotent():
    skills = cursor_skills()
    written = write_pointers(skills)
    before = {path: path.read_text(encoding="utf-8") for path in written}
    write_pointers(skills)
    after = {path: path.read_text(encoding="utf-8") for path in written}
    assert before == after


def test_shared_entry_files_point_at_agents_md():
    agents = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert ".cursor/rules/" in agents
    assert ".cursor/skills/" in agents
    assert "scripts/sync_agent_skills.py" in agents
    claude = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "@AGENTS.md" in claude
    assert "@.cursor/rules/pipeline.mdc" in claude
    gemini = (ROOT / ".gemini" / "settings.json").read_text(encoding="utf-8")
    assert "AGENTS.md" in gemini
    for name in ("GROK.md", "DEEPSEEK.md", "GEMINI.md"):
        text = (ROOT / name).read_text(encoding="utf-8")
        assert "AGENTS.md" in text
    copilot = (ROOT / ".github" / "copilot-instructions.md").read_text(encoding="utf-8")
    assert "AGENTS.md" in copilot
    assert "Pexels" in copilot
