"""Tests for AST-based symbol extraction."""

import tempfile
from pathlib import Path

from menard.symbols import (
    SymbolDiff,
    SymbolInfo,
    diff_symbols,
    extract_symbols,
    extract_symbols_from_file,
    get_symbols_cached,
)


def test_extract_symbols_functions():
    """Test extracting top-level functions."""
    source = """
def public_function():
    pass

def another_public():
    return 42

def _private_function():
    pass
"""
    symbols = extract_symbols(source)
    assert symbols.functions == ["another_public", "public_function"]
    assert symbols.classes == []


def test_extract_symbols_classes():
    """Test extracting top-level classes."""
    source = """
class PublicClass:
    pass

class AnotherClass:
    def method(self):
        pass

class _PrivateClass:
    pass
"""
    symbols = extract_symbols(source)
    assert symbols.classes == ["AnotherClass", "PublicClass"]
    assert symbols.functions == []


def test_extract_symbols_mixed():
    """Test extracting both functions and classes."""
    source = """
def foo():
    pass

class Bar:
    pass

def _private():
    pass

class _Hidden:
    pass

async def async_func():
    pass
"""
    symbols = extract_symbols(source)
    assert symbols.functions == ["async_func", "foo"]
    assert symbols.classes == ["Bar"]


def test_extract_symbols_syntax_error():
    """Test that syntax errors return empty symbols."""
    source = "def broken( pass"
    symbols = extract_symbols(source)
    assert symbols.functions == []
    assert symbols.classes == []


def test_extract_symbols_empty():
    """Test extracting from empty source."""
    symbols = extract_symbols("")
    assert symbols.functions == []
    assert symbols.classes == []


def test_extract_symbols_nested_not_included():
    """Test that nested functions/classes are not included."""
    source = """
def outer():
    def inner():
        pass
    class InnerClass:
        pass

class Outer:
    def method(self):
        pass
    class Nested:
        pass
"""
    symbols = extract_symbols(source)
    # Only top-level should be included
    assert symbols.functions == ["outer"]
    assert symbols.classes == ["Outer"]


def test_diff_symbols_additions():
    """Test detecting symbol additions."""
    old = SymbolInfo(functions=["foo"], classes=["Bar"])
    new = SymbolInfo(functions=["foo", "baz"], classes=["Bar", "Qux"])

    diff = diff_symbols(old, new)
    assert diff.functions_added == ["baz"]
    assert diff.functions_removed == []
    assert diff.classes_added == ["Qux"]
    assert diff.classes_removed == []
    assert diff.has_changes


def test_diff_symbols_removals():
    """Test detecting symbol removals."""
    old = SymbolInfo(functions=["foo", "bar"], classes=["A", "B"])
    new = SymbolInfo(functions=["foo"], classes=["A"])

    diff = diff_symbols(old, new)
    assert diff.functions_added == []
    assert diff.functions_removed == ["bar"]
    assert diff.classes_added == []
    assert diff.classes_removed == ["B"]
    assert diff.has_changes


def test_diff_symbols_mixed():
    """Test mixed additions and removals."""
    old = SymbolInfo(functions=["foo", "bar"], classes=["A"])
    new = SymbolInfo(functions=["foo", "baz"], classes=["B"])

    diff = diff_symbols(old, new)
    assert diff.functions_added == ["baz"]
    assert diff.functions_removed == ["bar"]
    assert diff.classes_added == ["B"]
    assert diff.classes_removed == ["A"]


def test_diff_symbols_no_changes():
    """Test when there are no changes."""
    old = SymbolInfo(functions=["foo"], classes=["Bar"])
    new = SymbolInfo(functions=["foo"], classes=["Bar"])

    diff = diff_symbols(old, new)
    assert not diff.has_changes
    assert diff.functions_added == []
    assert diff.functions_removed == []


def test_extract_symbols_from_file():
    """Test extracting symbols from a file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = Path(tmpdir) / "test.py"
        file_path.write_text("def hello(): pass\nclass World: pass")

        symbols = extract_symbols_from_file(file_path)
        assert symbols.functions == ["hello"]
        assert symbols.classes == ["World"]


def test_extract_symbols_from_nonexistent_file():
    """Test extracting from nonexistent file returns empty."""
    symbols = extract_symbols_from_file(Path("/nonexistent/file.py"))
    assert symbols.functions == []
    assert symbols.classes == []


def test_symbol_info_serialization():
    """Test SymbolInfo to_dict and from_dict."""
    original = SymbolInfo(functions=["foo", "bar"], classes=["Baz"])
    data = original.to_dict()
    restored = SymbolInfo.from_dict(data)

    assert restored.functions == original.functions
    assert restored.classes == original.classes


def test_symbol_diff_serialization():
    """Test SymbolDiff to_dict."""
    diff = SymbolDiff(
        functions_added=["new_func"],
        functions_removed=["old_func"],
        classes_added=["NewClass"],
        classes_removed=["OldClass"],
    )
    data = diff.to_dict()

    assert data["functions_added"] == ["new_func"]
    assert data["functions_removed"] == ["old_func"]
    assert data["classes_added"] == ["NewClass"]
    assert data["classes_removed"] == ["OldClass"]


def test_get_symbols_cached():
    """Test that caching works for symbol extraction."""
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        (repo_root / ".menard").mkdir()

        source = "def cached_func(): pass"

        # First call should compute
        symbols1 = get_symbols_cached(repo_root, source)
        assert symbols1.functions == ["cached_func"]

        # Second call should hit cache (same result)
        symbols2 = get_symbols_cached(repo_root, source)
        assert symbols2.functions == ["cached_func"]
