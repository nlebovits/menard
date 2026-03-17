"""Tests for source directory detection in docsync init."""

from argparse import Namespace
from pathlib import Path

from docsync.cli import EXCLUDED_DIRS, cmd_init, detect_source_directories


class TestDetectSourceDirectories:
    """Tests for detect_source_directories function."""

    def test_fallback_to_src_when_empty(self, tmp_path: Path) -> None:
        """When no packages found, fall back to src/**/*.py."""
        result = detect_source_directories(tmp_path)
        assert result == ["src/**/*.py"]

    def test_detects_package_with_init_py(self, tmp_path: Path) -> None:
        """Detect directories containing __init__.py."""
        # Create a package structure
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")
        (pkg_dir / "module.py").write_text("")

        result = detect_source_directories(tmp_path)
        assert result == ["mypackage/**/*.py"]

    def test_detects_multiple_packages(self, tmp_path: Path) -> None:
        """Detect multiple top-level packages."""
        # Create multiple packages
        for name in ["alpha", "beta"]:
            pkg_dir = tmp_path / name
            pkg_dir.mkdir()
            (pkg_dir / "__init__.py").write_text("")

        result = detect_source_directories(tmp_path)
        assert sorted(result) == ["alpha/**/*.py", "beta/**/*.py"]

    def test_excludes_test_directories(self, tmp_path: Path) -> None:
        """Exclude common test directories."""
        # Create a real package
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        # Create test directories that should be excluded
        tests_dir = tmp_path / "tests"
        tests_dir.mkdir()
        (tests_dir / "__init__.py").write_text("")

        test_dir = tmp_path / "test"
        test_dir.mkdir()
        (test_dir / "__init__.py").write_text("")

        result = detect_source_directories(tmp_path)
        assert result == ["mypackage/**/*.py"]
        assert "tests/**/*.py" not in result
        assert "test/**/*.py" not in result

    def test_excludes_venv_directories(self, tmp_path: Path) -> None:
        """Exclude virtual environment directories."""
        # Create a real package
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        # Create venv with packages (common in real projects)
        venv_dir = tmp_path / ".venv" / "lib" / "python3.11" / "site-packages" / "somelib"
        venv_dir.mkdir(parents=True)
        (venv_dir / "__init__.py").write_text("")

        result = detect_source_directories(tmp_path)
        assert result == ["mypackage/**/*.py"]

    def test_excludes_hidden_directories(self, tmp_path: Path) -> None:
        """Exclude hidden directories (starting with .)."""
        # Create a real package
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        # Create hidden directory
        hidden_dir = tmp_path / ".hidden_pkg"
        hidden_dir.mkdir()
        (hidden_dir / "__init__.py").write_text("")

        result = detect_source_directories(tmp_path)
        assert result == ["mypackage/**/*.py"]

    def test_finds_top_level_package_for_nested(self, tmp_path: Path) -> None:
        """Find top-level package even when nested packages exist."""
        # Create nested package structure
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        subpkg_dir = pkg_dir / "subpackage"
        subpkg_dir.mkdir()
        (subpkg_dir / "__init__.py").write_text("")

        result = detect_source_directories(tmp_path)
        # Should return just the top-level, not both
        assert result == ["mypackage/**/*.py"]

    def test_detects_src_layout(self, tmp_path: Path) -> None:
        """Detect src layout (src/packagename/)."""
        # Create src layout
        src_dir = tmp_path / "src"
        src_dir.mkdir()
        pkg_dir = src_dir / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        result = detect_source_directories(tmp_path)
        # Should find src as the top-level directory
        assert result == ["src/**/*.py"]

    def test_reads_hatch_packages_config(self, tmp_path: Path) -> None:
        """Read package configuration from [tool.hatch.build.targets.wheel]."""
        # Create pyproject.toml with hatch config
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "myproject"
version = "1.0.0"

[tool.hatch.build.targets.wheel]
packages = ["src/mypackage"]
""")

        result = detect_source_directories(tmp_path)
        assert result == ["src/mypackage/**/*.py"]

    def test_reads_setuptools_packages_config(self, tmp_path: Path) -> None:
        """Read package configuration from [tool.setuptools]."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "myproject"
version = "1.0.0"

[tool.setuptools]
packages = ["mypackage", "mypackage.subpkg"]
""")

        result = detect_source_directories(tmp_path)
        assert "mypackage/**/*.py" in result
        assert "mypackage.subpkg/**/*.py" in result

    def test_reads_setuptools_package_dir_config(self, tmp_path: Path) -> None:
        """Read package-dir configuration from [tool.setuptools]."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "myproject"
version = "1.0.0"

[tool.setuptools.package-dir]
mypackage = "lib/mypackage"
""")

        result = detect_source_directories(tmp_path)
        assert result == ["lib/mypackage/**/*.py"]

    def test_pyproject_config_takes_precedence(self, tmp_path: Path) -> None:
        """pyproject.toml config takes precedence over __init__.py scanning."""
        # Create pyproject.toml with explicit config
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "myproject"
version = "1.0.0"

[tool.hatch.build.targets.wheel]
packages = ["src/specified"]
""")

        # Create a different package that would be found by scanning
        other_pkg = tmp_path / "other_package"
        other_pkg.mkdir()
        (other_pkg / "__init__.py").write_text("")

        result = detect_source_directories(tmp_path)
        # Should use pyproject.toml config, not scan
        assert result == ["src/specified/**/*.py"]

    def test_handles_malformed_pyproject(self, tmp_path: Path) -> None:
        """Handle malformed pyproject.toml gracefully."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("this is not valid toml {{{}}")

        # Create a package that can be found by scanning
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        result = detect_source_directories(tmp_path)
        # Should fall back to scanning
        assert result == ["mypackage/**/*.py"]


class TestExcludedDirs:
    """Tests for the EXCLUDED_DIRS constant."""

    def test_common_test_dirs_excluded(self) -> None:
        """Verify common test directories are in exclusion list."""
        assert "tests" in EXCLUDED_DIRS
        assert "test" in EXCLUDED_DIRS

    def test_common_doc_dirs_excluded(self) -> None:
        """Verify documentation directories are excluded."""
        assert "docs" in EXCLUDED_DIRS
        assert "doc" in EXCLUDED_DIRS

    def test_virtual_env_dirs_excluded(self) -> None:
        """Verify virtual environment directories are excluded."""
        assert ".venv" in EXCLUDED_DIRS
        assert "venv" in EXCLUDED_DIRS

    def test_build_dirs_excluded(self) -> None:
        """Verify build directories are excluded."""
        assert "build" in EXCLUDED_DIRS
        assert "dist" in EXCLUDED_DIRS


class TestCmdInitWithDetection:
    """Integration tests for cmd_init using auto-detection."""

    def test_init_detects_existing_package(self, tmp_path: Path, monkeypatch) -> None:
        """cmd_init uses detected package in require_links."""
        monkeypatch.chdir(tmp_path)

        # Create a package
        pkg_dir = tmp_path / "mypackage"
        pkg_dir.mkdir()
        (pkg_dir / "__init__.py").write_text("")

        result = cmd_init(Namespace())
        assert result == 0

        # Verify config uses detected package
        pyproject = tmp_path / "pyproject.toml"
        content = pyproject.read_text()
        assert 'require_links = ["mypackage/**/*.py"]' in content

    def test_init_fallback_to_src(self, tmp_path: Path, monkeypatch) -> None:
        """cmd_init falls back to src/ when no packages found."""
        monkeypatch.chdir(tmp_path)

        result = cmd_init(Namespace())
        assert result == 0

        pyproject = tmp_path / "pyproject.toml"
        content = pyproject.read_text()
        assert 'require_links = ["src/**/*.py"]' in content

    def test_init_with_existing_pyproject(self, tmp_path: Path, monkeypatch) -> None:
        """cmd_init appends to existing pyproject.toml with detection."""
        monkeypatch.chdir(tmp_path)

        # Create existing pyproject.toml with hatch config
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""[project]
name = "existing"
version = "1.0.0"

[tool.hatch.build.targets.wheel]
packages = ["src/existingpkg"]
""")

        result = cmd_init(Namespace())
        assert result == 0

        content = pyproject.read_text()
        assert "[tool.docsync]" in content
        assert 'require_links = ["src/existingpkg/**/*.py"]' in content

    def test_init_detects_multiple_packages(self, tmp_path: Path, monkeypatch) -> None:
        """cmd_init handles multiple detected packages."""
        monkeypatch.chdir(tmp_path)

        # Create multiple packages
        for name in ["alpha", "beta"]:
            pkg_dir = tmp_path / name
            pkg_dir.mkdir()
            (pkg_dir / "__init__.py").write_text("")

        result = cmd_init(Namespace())
        assert result == 0

        pyproject = tmp_path / "pyproject.toml"
        content = pyproject.read_text()
        # Should have both patterns
        assert "alpha/**/*.py" in content
        assert "beta/**/*.py" in content
