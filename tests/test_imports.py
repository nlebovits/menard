"""Tests for imports.py."""

from pathlib import Path

from docsync.imports import build_import_graph, get_dependents


def test_build_import_graph_simple(tmp_path: Path):
    """Test simple absolute import resolution."""
    # Create src/foo.py
    src = tmp_path / "src"
    src.mkdir()
    foo = src / "foo.py"
    foo.write_text("x = 1\n")

    # Create src/bar.py that imports foo
    bar = src / "bar.py"
    bar.write_text("import foo\n")

    graph = build_import_graph(tmp_path)

    assert "src/bar.py" in graph
    assert "src/foo.py" in graph["src/bar.py"]


def test_build_import_graph_from_import(tmp_path: Path):
    """Test 'from foo import bar' style imports."""
    src = tmp_path / "src"
    src.mkdir()

    # Create src/foo/bar.py
    foo_dir = src / "foo"
    foo_dir.mkdir()
    (foo_dir / "__init__.py").write_text("")
    bar = foo_dir / "bar.py"
    bar.write_text("def baz(): pass\n")

    # Create src/main.py that imports from foo.bar
    main = src / "main.py"
    main.write_text("from foo.bar import baz\n")

    graph = build_import_graph(tmp_path)

    assert "src/main.py" in graph
    assert "src/foo/bar.py" in graph["src/main.py"]


def test_build_import_graph_relative_imports(tmp_path: Path):
    """Test relative imports with 'from . import foo'."""
    src = tmp_path / "src"
    src.mkdir()
    pkg = src / "pkg"
    pkg.mkdir()

    # Create src/pkg/module_a.py
    module_a = pkg / "module_a.py"
    module_a.write_text("x = 1\n")

    # Create src/pkg/module_b.py that imports from .module_a
    module_b = pkg / "module_b.py"
    module_b.write_text("from .module_a import x\n")

    graph = build_import_graph(tmp_path)

    assert "src/pkg/module_b.py" in graph
    assert "src/pkg/module_a.py" in graph["src/pkg/module_b.py"]


def test_build_import_graph_relative_parent(tmp_path: Path):
    """Test relative imports from parent package with 'from .. import foo'."""
    src = tmp_path / "src"
    src.mkdir()

    # Create src/parent.py
    parent = src / "parent.py"
    parent.write_text("x = 1\n")

    # Create src/pkg/child.py that imports from parent
    pkg = src / "pkg"
    pkg.mkdir()
    child = pkg / "child.py"
    child.write_text("from ..parent import x\n")

    graph = build_import_graph(tmp_path)

    assert "src/pkg/child.py" in graph
    assert "src/parent.py" in graph["src/pkg/child.py"]


def test_build_import_graph_package_init(tmp_path: Path):
    """Test importing a package (resolves to __init__.py)."""
    src = tmp_path / "src"
    src.mkdir()

    # Create src/pkg/__init__.py
    pkg = src / "pkg"
    pkg.mkdir()
    init = pkg / "__init__.py"
    init.write_text("x = 1\n")

    # Create src/main.py that imports the package
    main = src / "main.py"
    main.write_text("import pkg\n")

    graph = build_import_graph(tmp_path)

    assert "src/main.py" in graph
    assert "src/pkg/__init__.py" in graph["src/main.py"]


def test_build_import_graph_nonexistent_module(tmp_path: Path):
    """Test that imports to non-existent modules are ignored."""
    src = tmp_path / "src"
    src.mkdir()

    main = src / "main.py"
    main.write_text("import nonexistent_module\nimport os\n")

    graph = build_import_graph(tmp_path)

    # main.py should not be in graph since all its imports are external
    assert "src/main.py" not in graph or len(graph["src/main.py"]) == 0


def test_build_import_graph_syntax_error(tmp_path: Path):
    """Test that files with syntax errors are skipped."""
    src = tmp_path / "src"
    src.mkdir()

    bad = src / "bad.py"
    bad.write_text("this is not valid python [[[")

    good = src / "good.py"
    good.write_text("x = 1\n")

    # Should not crash, just skip the bad file
    graph = build_import_graph(tmp_path)

    assert "src/bad.py" not in graph


def test_get_dependents_depth_1(tmp_path: Path):
    """Test get_dependents at depth 1 (direct importers only)."""
    src = tmp_path / "src"
    src.mkdir()

    # Create a chain: a <- b <- c
    a = src / "a.py"
    a.write_text("x = 1\n")

    b = src / "b.py"
    b.write_text("from a import x\n")

    c = src / "c.py"
    c.write_text("from b import x\n")

    graph = build_import_graph(tmp_path)

    # Dependents of a at depth 1 should be just b
    deps = get_dependents("src/a.py", graph, depth=1)
    assert deps == {"src/b.py"}


def test_get_dependents_depth_2(tmp_path: Path):
    """Test get_dependents at depth 2 (transitive importers)."""
    src = tmp_path / "src"
    src.mkdir()

    # Create a chain: a <- b <- c
    a = src / "a.py"
    a.write_text("x = 1\n")

    b = src / "b.py"
    b.write_text("from a import x\n")

    c = src / "c.py"
    c.write_text("from b import x\n")

    graph = build_import_graph(tmp_path)

    # Dependents of a at depth 2 should be b and c
    deps = get_dependents("src/a.py", graph, depth=2)
    assert deps == {"src/b.py", "src/c.py"}


def test_get_dependents_cycle(tmp_path: Path):
    """Test that cycles in import graph don't cause infinite loop."""
    src = tmp_path / "src"
    src.mkdir()

    # Create a cycle: a <- b <- c <- a
    a = src / "a.py"
    a.write_text("from c import z\nx = 1\n")

    b = src / "b.py"
    b.write_text("from a import x\ny = 2\n")

    c = src / "c.py"
    c.write_text("from b import y\nz = 3\n")

    graph = build_import_graph(tmp_path)

    # Should handle the cycle gracefully
    deps = get_dependents("src/a.py", graph, depth=2)
    # b and c both depend on a (directly or transitively)
    assert "src/b.py" in deps
    assert "src/c.py" in deps


def test_get_dependents_no_dependents(tmp_path: Path):
    """Test get_dependents for a file with no dependents."""
    src = tmp_path / "src"
    src.mkdir()

    a = src / "a.py"
    a.write_text("x = 1\n")

    graph = build_import_graph(tmp_path)

    deps = get_dependents("src/a.py", graph, depth=1)
    assert deps == set()


def test_get_dependents_depth_0(tmp_path: Path):
    """Test that depth 0 returns empty set."""
    src = tmp_path / "src"
    src.mkdir()

    a = src / "a.py"
    a.write_text("x = 1\n")

    b = src / "b.py"
    b.write_text("from a import x\n")

    graph = build_import_graph(tmp_path)

    deps = get_dependents("src/a.py", graph, depth=0)
    assert deps == set()


def test_build_import_graph_custom_source_roots(tmp_path: Path):
    """Test that custom source roots work."""
    # Create lib/foo.py
    lib = tmp_path / "lib"
    lib.mkdir()
    foo = lib / "foo.py"
    foo.write_text("x = 1\n")

    # Create lib/bar.py that imports foo
    bar = lib / "bar.py"
    bar.write_text("import foo\n")

    graph = build_import_graph(tmp_path, source_roots=[lib])

    assert "lib/bar.py" in graph
    assert "lib/foo.py" in graph["lib/bar.py"]


def test_build_import_graph_multiple_imports(tmp_path: Path):
    """Test a file importing from multiple other files."""
    src = tmp_path / "src"
    src.mkdir()

    a = src / "a.py"
    a.write_text("x = 1\n")

    b = src / "b.py"
    b.write_text("y = 2\n")

    main = src / "main.py"
    main.write_text("from a import x\nfrom b import y\n")

    graph = build_import_graph(tmp_path)

    assert "src/main.py" in graph
    assert "src/a.py" in graph["src/main.py"]
    assert "src/b.py" in graph["src/main.py"]


def test_build_import_graph_outside_source_roots(tmp_path: Path):
    """Test that files outside source roots are ignored."""
    src = tmp_path / "src"
    src.mkdir()

    external = tmp_path / "external"
    external.mkdir()

    ext_file = external / "ext.py"
    ext_file.write_text("x = 1\n")

    main = src / "main.py"
    # This won't resolve because external/ is not in source roots
    main.write_text("import ext\n")

    graph = build_import_graph(tmp_path, source_roots=[src])

    # main.py should not have any imports (ext.py not found)
    assert "src/main.py" not in graph or len(graph.get("src/main.py", set())) == 0
