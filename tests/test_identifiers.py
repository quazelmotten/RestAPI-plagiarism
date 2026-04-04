"""Tests for plagiarism_core.fingerprinting.identifiers module."""


from plagiarism_core.fingerprinting.identifiers import (
    BUILTIN_NAMES,
    _find_function_scopes,
    _make_shadow_lines_scope,
    _normalize_identifiers_in_scope,
    _normalize_in_scope,
    _scope_shadow_hashes,
)


class TestBuiltinNames:
    def test_contains_common_builtins(self):
        assert "print" in BUILTIN_NAMES
        assert "len" in BUILTIN_NAMES
        assert "range" in BUILTIN_NAMES
        assert "int" in BUILTIN_NAMES
        assert "str" in BUILTIN_NAMES
        assert "list" in BUILTIN_NAMES
        assert "dict" in BUILTIN_NAMES

    def test_contains_keywords(self):
        assert "if" in BUILTIN_NAMES
        assert "for" in BUILTIN_NAMES
        assert "def" in BUILTIN_NAMES
        assert "return" in BUILTIN_NAMES

    def test_contains_other_lang(self):
        assert "void" in BUILTIN_NAMES
        assert "self" in BUILTIN_NAMES
        assert "this" in BUILTIN_NAMES


class TestFindFunctionScopes:
    def test_single_function(self):
        source = "def foo():\n    pass\n"
        scopes = _find_function_scopes(source, "python")
        assert len(scopes) == 1

    def test_multiple_functions(self):
        source = "def foo():\n    pass\n\ndef bar():\n    pass\n"
        scopes = _find_function_scopes(source, "python")
        assert len(scopes) == 2

    def test_nested_function(self):
        source = "def outer():\n    def inner():\n        pass\n"
        scopes = _find_function_scopes(source, "python")
        assert len(scopes) >= 1

    def test_no_functions(self):
        source = "x = 1\n"
        scopes = _find_function_scopes(source, "python")
        assert len(scopes) == 0

    def test_invalid_source(self):
        scopes = _find_function_scopes("{{{not valid", "python")
        assert scopes == []

    def test_scope_has_position_info(self):
        source = "def foo():\n    pass\n"
        scopes = _find_function_scopes(source, "python")
        assert "start_byte" in scopes[0]
        assert "end_byte" in scopes[0]
        assert "start_line" in scopes[0]
        assert "end_line" in scopes[0]


class TestNormalizeInScope:
    def test_renames_identifiers(self):
        source = "x = calculate_total(items)"
        result = _normalize_in_scope(source, "python")
        assert "VAR_" in result

    def test_preserves_builtins(self):
        source = "print(len(items))"
        result = _normalize_in_scope(source, "python")
        assert "print" in result
        assert "len" in result

    def test_same_pattern_different_names(self):
        code_a = "x = calculate_total(items)"
        code_b = "y = compute_sum(values)"
        norm_a = _normalize_in_scope(code_a, "python")
        norm_b = _normalize_in_scope(code_b, "python")
        assert norm_a == norm_b

    def test_empty_source(self):
        result = _normalize_in_scope("", "python")
        assert result == ""

    def test_whitespace_only(self):
        result = _normalize_in_scope("   \n  ", "python")
        assert result.strip() == ""

    def test_preserves_dunder(self):
        source = "__init__ = 1"
        result = _normalize_in_scope(source, "python")
        assert "__init__" in result

    def test_invalid_source_fallback(self):
        source = "{{{not valid"
        result = _normalize_in_scope(source, "python")
        assert result is not None


class TestNormalizeIdentifiersInScope:
    def test_single_function(self):
        source = "def foo(x):\n    return x + 1\n"
        result = _normalize_identifiers_in_scope(source, "python")
        assert "VAR_" in result

    def test_multiple_functions(self):
        source = "def foo(x):\n    return x\n\ndef bar(y):\n    return y\n"
        result = _normalize_identifiers_in_scope(source, "python")
        assert "VAR_" in result

    def test_no_functions(self):
        source = "x = calculate(items)"
        result = _normalize_identifiers_in_scope(source, "python")
        assert "VAR_" in result

    def test_invalid_source(self):
        result = _normalize_identifiers_in_scope("{{{not valid", "python")
        assert result is not None


class TestMakeShadowLinesScope:
    def test_basic(self):
        source = "def foo():\n    return x + 1\n"
        lines = _make_shadow_lines_scope(source, "python")
        assert isinstance(lines, list)
        assert len(lines) > 0

    def test_normalized(self):
        source = "def foo(x):\n    return x\n"
        lines = _make_shadow_lines_scope(source, "python")
        combined = "\n".join(lines)
        assert "VAR_" in combined


class TestScopeShadowHashes:
    def test_basic(self):
        source = "def foo():\n    return 1\n"
        hashes = _scope_shadow_hashes(source, "python")
        assert isinstance(hashes, set)
        assert len(hashes) > 0

    def test_empty_lines_not_hashed(self):
        source = "\n\n\n"
        hashes = _scope_shadow_hashes(source, "python")
        assert 0 not in hashes

    def test_same_code_same_hashes(self):
        source = "x = 1\n"
        h1 = _scope_shadow_hashes(source, "python")
        h2 = _scope_shadow_hashes(source, "python")
        assert h1 == h2
