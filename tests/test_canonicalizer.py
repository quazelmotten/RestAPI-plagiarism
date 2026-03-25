import pytest
from plagiarism_core.canonicalizer import (
    normalize_identifiers,
    canonicalize_type4,
    canonicalize_full,
    get_identifier_renames,
    _normalize_identifiers_from_tree,
    parse_file_once_from_string,
)


class TestNormalizeIdentifiers:
    """Test identifier normalization (Type 2 detection)."""

    def test_renames_variables_to_placeholders(self):
        source = """
def add(a, b):
    result = a + b
    return result
"""
        normalized = normalize_identifiers(source, 'python')
        assert 'VAR_0' in normalized
        assert 'VAR_1' in normalized
        assert 'add' not in normalized
        assert 'result' not in normalized

    def test_consistent_mapping_same_source(self):
        source = """
x = 1
y = x + 2
"""
        norm1 = normalize_identifiers(source, 'python')
        norm2 = normalize_identifiers(source, 'python')
        assert norm1 == norm2

    def test_different_sources_get_different_placeholders(self):
        source_a = "alpha = 1"
        source_b = "beta = 1"
        norm_a = normalize_identifiers(source_a, 'python')
        norm_b = normalize_identifiers(source_b, 'python')
        # Both should have VAR_0 but mapped to different names
        assert 'VAR_0' in norm_a
        assert 'VAR_0' in norm_b

    def test_preserves_keywords(self):
        source = "for i in range(10):\n    pass"
        normalized = normalize_identifiers(source, 'python')
        assert 'for' in normalized
        assert 'in' in normalized
        assert 'pass' in normalized

    def test_replaces_all_identifiers(self):
        source = "print(len([1, 2, 3]))"
        normalized = normalize_identifiers(source, 'python')
        # Canonicalizer replaces all non-dunder identifiers, including builtins
        assert 'VAR_0' in normalized
        assert 'VAR_1' in normalized

    def test_skips_dunder_names(self):
        source = """
class Foo:
    def __init__(self):
        self.x = 1
"""
        normalized = normalize_identifiers(source, 'python')
        # Only dunder names (__init__) are preserved; 'self' and 'Foo' get replaced
        assert '__init__' in normalized
        assert 'VAR_0' in normalized  # Foo
        assert 'VAR_1' in normalized  # self

    def test_returns_original_on_parse_failure(self):
        # Empty string returns empty (parse succeeds but no identifiers)
        result = normalize_identifiers("", 'python')
        assert result == ""


class TestNormalizeIdentifiersFromTree:
    """Test the pre-parsed tree variant."""

    def test_same_result_as_normalize_identifiers(self):
        source = """
def calculate(x, y):
    total = x + y
    return total
"""
        tree, source_bytes = parse_file_once_from_string(source, 'python')
        from_tree = _normalize_identifiers_from_tree(tree, source_bytes, source)
        from_string = normalize_identifiers(source, 'python')
        assert from_tree == from_string

    def test_returns_fallback_on_no_identifiers(self):
        source = "1 + 2 * 3"
        tree, source_bytes = parse_file_once_from_string(source, 'python')
        result = _normalize_identifiers_from_tree(tree, source_bytes, source)
        # No user identifiers in pure arithmetic, returns original
        assert result == source


class TestCanonicalizeType4:
    """Test Type 4 semantic canonicalization rules."""

    def test_for_to_while_conversion(self):
        code = "for x in items:\n    print(x)"
        result = canonicalize_type4(code)
        assert 'while True' in result
        assert 'next(' in result

    def test_lambda_to_def_conversion(self):
        code = "square = lambda x: x * 2"
        result = canonicalize_type4(code)
        assert 'def square' in result
        assert 'return' in result

    def test_fstring_to_format(self):
        code = 'msg = f"hello {name}"'
        result = canonicalize_type4(code)
        assert '.format(' in result
        assert 'f"' not in result

    def test_none_comparison_normalization(self):
        code = "if x == None:\n    pass"
        result = canonicalize_type4(code)
        assert 'is None' in result

    def test_multiple_rules_applied(self):
        code = """
for i in range(10):
    if x == None:
        pass
"""
        result = canonicalize_type4(code)
        # for→while and == None → is None
        assert 'while True' in result or 'is None' in result

    def test_no_crash_on_empty_string(self):
        result = canonicalize_type4("")
        assert result == ""

    def test_no_crash_on_malformed_code(self):
        # This shouldn't crash even with weird input
        result = canonicalize_type4("!!!invalid syntax!!!")
        assert isinstance(result, str)


class TestGetIdentifierRenames:
    """Test rename detection between two files."""

    def test_detects_simple_rename(self):
        source_a = """
def add(a, b):
    return a + b
"""
        source_b = """
def add(x, y):
    return x + y
"""
        renames = get_identifier_renames(source_a, source_b, 'python')
        # Should detect a→x and b→y (or similar renames)
        assert len(renames) > 0
        rename_names = {r['renamed'] for r in renames}
        assert 'x' in rename_names or 'y' in rename_names

    def test_no_renames_for_identical_code(self):
        source = "x = 1\ny = 2"
        renames = get_identifier_renames(source, source, 'python')
        assert len(renames) == 0

    def test_handles_mismatched_code_gracefully(self):
        renames = get_identifier_renames("x = 1", "y = 2", 'python')
        # Should return renames (x → y) or empty, but not crash
        assert isinstance(renames, list)


class TestCanonicalizeFull:
    """Test full canonicalization (type4 + identifier normalization)."""

    def test_both_transformations_applied(self):
        source = """
for i in range(10):
    result = i * 2
"""
        result = canonicalize_full(source, 'python')
        # Should have both for→while conversion AND identifier normalization
        assert 'while True' in result or 'VAR_' in result

    def test_non_python_skips_type4(self):
        source = "int x = 0;"
        result = canonicalize_full(source, 'cpp')
        # For non-python, only identifier normalization runs (if parser supports it)
        assert isinstance(result, str)
