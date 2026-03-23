"""Tests for bundled skills functionality."""

import json
from argparse import Namespace

from menard.cli import cmd_skills


class TestBundledSkills:
    """Tests for bundled skills shipped with menard package."""

    def test_bundled_skills_found_without_local_dir(self, tmp_path, monkeypatch, capsys):
        """Bundled skills are listed even when no .claude/skills directory exists."""
        monkeypatch.chdir(tmp_path)

        result = cmd_skills(Namespace(format="text", copy=None))
        captured = capsys.readouterr()

        assert result == 0
        # Should find the bundled audit skill
        assert "audit" in captured.out

    def test_bundled_skills_json_output(self, tmp_path, monkeypatch, capsys):
        """Bundled skills appear in JSON output with source='bundled'."""
        monkeypatch.chdir(tmp_path)

        result = cmd_skills(Namespace(format="json", copy=None))
        captured = capsys.readouterr()

        assert result == 0
        data = json.loads(captured.out)

        # Should have skills
        assert "skills" in data
        assert len(data["skills"]) > 0

        # Find the audit skill
        audit_skill = next((s for s in data["skills"] if s["name"] == "audit"), None)
        assert audit_skill is not None
        assert audit_skill["source"] == "bundled"

    def test_local_skills_override_bundled(self, tmp_path, monkeypatch, capsys):
        """Local skills with same name override bundled skills."""
        monkeypatch.chdir(tmp_path)

        # Create local audit skill with different description
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "audit.md").write_text("# Custom Audit\n\nMy custom audit skill.\n")

        result = cmd_skills(Namespace(format="json", copy=None))
        captured = capsys.readouterr()

        assert result == 0
        data = json.loads(captured.out)

        # Should only have one audit skill (local)
        audit_skills = [s for s in data["skills"] if s["name"] == "audit"]
        assert len(audit_skills) == 1
        assert audit_skills[0]["source"] == "local"
        assert "custom" in audit_skills[0]["description"].lower()

    def test_local_and_bundled_coexist(self, tmp_path, monkeypatch, capsys):
        """Local skills and bundled skills both appear when names differ."""
        monkeypatch.chdir(tmp_path)

        # Create local skill with different name
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "custom.md").write_text("# Custom Skill\n\nMy custom skill.\n")

        result = cmd_skills(Namespace(format="json", copy=None))
        captured = capsys.readouterr()

        assert result == 0
        data = json.loads(captured.out)

        # Should have both bundled (audit) and local (custom)
        names = {s["name"] for s in data["skills"]}
        assert "audit" in names
        assert "custom" in names

        # Verify sources
        audit = next(s for s in data["skills"] if s["name"] == "audit")
        custom = next(s for s in data["skills"] if s["name"] == "custom")
        assert audit["source"] == "bundled"
        assert custom["source"] == "local"


class TestSkillsCopy:
    """Tests for the --copy flag to copy bundled skills to local."""

    def test_copy_creates_local_skill(self, tmp_path, monkeypatch, capsys):
        """--copy creates local copy of bundled skill."""
        monkeypatch.chdir(tmp_path)

        result = cmd_skills(Namespace(format="text", copy="audit"))
        capsys.readouterr()  # Clear output

        assert result == 0

        # Local skill should now exist
        local_skill = tmp_path / ".claude" / "skills" / "audit.md"
        assert local_skill.exists()

        # Content should match bundled
        content = local_skill.read_text()
        assert "audit" in content.lower() or "Audit" in content

    def test_copy_creates_directory_if_missing(self, tmp_path, monkeypatch, capsys):
        """--copy creates .claude/skills/ directory if it doesn't exist."""
        monkeypatch.chdir(tmp_path)

        # Verify directory doesn't exist
        skills_dir = tmp_path / ".claude" / "skills"
        assert not skills_dir.exists()

        result = cmd_skills(Namespace(format="text", copy="audit"))

        assert result == 0
        assert skills_dir.exists()
        assert (skills_dir / "audit.md").exists()

    def test_copy_refuses_overwrite(self, tmp_path, monkeypatch, capsys):
        """--copy refuses to overwrite existing local skill."""
        monkeypatch.chdir(tmp_path)

        # Create existing local skill
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "audit.md").write_text("# My custom audit\n")

        result = cmd_skills(Namespace(format="text", copy="audit"))
        captured = capsys.readouterr()

        # Should fail with error
        assert result == 1
        assert "already exists" in captured.out.lower()

        # Content should be unchanged
        content = (skills_dir / "audit.md").read_text()
        assert "My custom audit" in content

    def test_copy_nonexistent_skill_fails(self, tmp_path, monkeypatch, capsys):
        """--copy fails gracefully for non-existent skill."""
        monkeypatch.chdir(tmp_path)

        result = cmd_skills(Namespace(format="text", copy="nonexistent"))
        captured = capsys.readouterr()

        assert result == 1
        assert "not found" in captured.out.lower()

    def test_copy_with_force_overwrites(self, tmp_path, monkeypatch, capsys):
        """--copy --force overwrites existing local skill."""
        monkeypatch.chdir(tmp_path)

        # Create existing local skill
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "audit.md").write_text("# Old content\n")

        result = cmd_skills(Namespace(format="text", copy="audit", force=True))
        capsys.readouterr()  # Clear output

        assert result == 0

        # Content should be replaced with bundled
        content = (skills_dir / "audit.md").read_text()
        assert "Old content" not in content


class TestSkillsTextOutput:
    """Tests for human-readable text output."""

    def test_text_shows_source_indicator(self, tmp_path, monkeypatch, capsys):
        """Text output shows [bundled] or [local] indicator."""
        monkeypatch.chdir(tmp_path)

        # Create a local skill
        skills_dir = tmp_path / ".claude" / "skills"
        skills_dir.mkdir(parents=True)
        (skills_dir / "custom.md").write_text("# Custom\n\nA custom skill.\n")

        result = cmd_skills(Namespace(format="text", copy=None))
        captured = capsys.readouterr()

        assert result == 0
        # Should show source indicators
        assert "[bundled]" in captured.out or "bundled" in captured.out.lower()
        assert "[local]" in captured.out or "local" in captured.out.lower()
