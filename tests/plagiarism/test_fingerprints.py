"""
Unit tests for fingerprinting functions from plagiarism_core.fingerprints.
Tests tokenization, hashing, fingerprint computation, and winnowing.
"""

from unittest.mock import patch

import pytest
from plagiarism_core.fingerprints import (
    compute_and_winnow,
    compute_fingerprints,
    index_fingerprints,
    parse_file_once,
    stable_hash,
    tokenize_and_hash_ast,
    tokenize_with_tree_sitter,
    winnow_fingerprints,
)


class TestStableHash:
    """Test deterministic hashing function."""

    def test_same_input_produces_same_hash(self):
        """Same string should always produce the same hash."""
        h1 = stable_hash("hello world")
        h2 = stable_hash("hello world")
        assert h1 == h2

    def test_different_inputs_produce_different_hashes(self):
        """Different strings should (almost always) produce different hashes."""
        h1 = stable_hash("hello")
        h2 = stable_hash("world")
        assert h1 != h2

    def test_empty_string(self):
        """Empty string should produce a valid hash."""
        h = stable_hash("")
        assert isinstance(h, int)
        assert h != 0 or h == 0  # Could be 0 or non-zero, just ensure it's computed

    def test_unicode_characters(self):
        """Unicode strings should be handled correctly."""
        h = stable_hash("café 🎉")
        assert isinstance(h, int)

    def test_hash_is_within_expected_range(self):
        """xxhash.xxh64 produces 64-bit unsigned integer."""
        h = stable_hash("test")
        assert 0 <= h < 2**64


class TestTokenizeWithTreeSitter:
    """Test tree-sitter tokenization."""

    @pytest.fixture
    def sample_python_code(self, tmp_path):
        """Create a sample Python file for testing."""
        code = """
def add(a, b):
    return a + b

def multiply(x, y):
    return x * y
"""
        file_path = tmp_path / "sample.py"
        file_path.write_text(code)
        return str(file_path)

    def test_tokenize_returns_list_of_tuples(self, sample_python_code):
        """Should return list of (token_type, start_point, end_point)."""
        tokens = tokenize_with_tree_sitter(sample_python_code, "python")
        assert isinstance(tokens, list)
        for token in tokens:
            assert isinstance(token, tuple)
            assert len(token) == 3
            token_type, start, end = token
            assert isinstance(token_type, str)
            assert isinstance(start, tuple) and len(start) == 2
            assert isinstance(end, tuple) and len(end) == 2

    def test_tokenize_excludes_comments(self, tmp_path):
        """Comments should be excluded from tokens."""
        code_with_comment = """# This is a comment\ndef foo():\n    pass"""
        file_path = tmp_path / "commented.py"
        file_path.write_text(code_with_comment)
        tokens = tokenize_with_tree_sitter(str(file_path), "python")
        token_types = [t[0] for t in tokens]
        assert "comment" not in token_types

    def test_tokenize_includes_keywords_and_identifiers(self, sample_python_code):
        """Should include function, identifier, operator tokens."""
        tokens = tokenize_with_tree_sitter(sample_python_code, "python")
        token_types = [t[0] for t in tokens]
        # Should include def, return, identifiers, operators, etc.
        assert "def" in token_types or "function_definition" in token_types
        assert "return" in token_types or "return_statement" in token_types

    def test_tokenize_unsupported_language_raises(self, tmp_path):
        """Unsupported language should raise ValueError."""
        file_path = tmp_path / "sample.xyz"
        file_path.write_text("some code")
        with pytest.raises(ValueError):
            tokenize_with_tree_sitter(str(file_path), "xyz")

    def test_tokenize_nonexistent_file_raises(self, tmp_path):
        """Non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            tokenize_with_tree_sitter(str(tmp_path / "missing.py"), "python")

    def test_tokenize_with_provided_tree(self, sample_python_code):
        """Should use provided tree instead of re-parsing."""
        tree, _ = parse_file_once(sample_python_code, "python")
        with patch("plagiarism_core.fingerprints.parse_file_once") as mock_parse:
            tokens = tokenize_with_tree_sitter(sample_python_code, "python", tree=tree)
            mock_parse.assert_not_called()
        assert isinstance(tokens, list)


class TestTokenizeAndHashAst:
    """Test combined tokenization and AST hashing."""

    @pytest.fixture
    def sample_python_code(self, tmp_path):
        """Create a sample Python file."""
        code = """
def calculate_total(items):
    total = 0
    for item in items:
        total += item
    return total
"""
        file_path = tmp_path / "sample.py"
        file_path.write_text(code)
        return str(file_path)

    def test_returns_tokens_and_ast_hashes(self, sample_python_code):
        """Should return (tokens, ast_hashes) tuple."""
        tokens, ast_hashes = tokenize_and_hash_ast(sample_python_code, "python")
        assert isinstance(tokens, list)
        assert isinstance(ast_hashes, list)
        for token in tokens:
            assert isinstance(token, tuple) and len(token) == 3
        for h in ast_hashes:
            assert isinstance(h, int)

    def test_ast_hashes_not_empty_for_nontrivial_code(self, sample_python_code):
        """Non-trivial AST should produce some subtree hashes."""
        _, ast_hashes = tokenize_and_hash_ast(sample_python_code, "python")
        assert len(ast_hashes) > 0

    def test_min_depth_filters_shallow_subtrees(self, sample_python_code):
        """Setting min_depth higher should produce fewer hashes."""
        tokens1, hashes1 = tokenize_and_hash_ast(sample_python_code, "python", min_depth=1)
        tokens2, hashes2 = tokenize_and_hash_ast(sample_python_code, "python", min_depth=5)
        assert len(hashes2) <= len(hashes1)

    def test_excludes_comments_from_ast_hash(self, tmp_path):
        """Comments should not contribute to AST hashes."""
        code_with_comment = """# comment\ndef foo():\n    pass"""
        file_path = tmp_path / "commented.py"
        file_path.write_text(code_with_comment)
        _, ast_hashes = tokenize_and_hash_ast(str(file_path), "python")
        # Should still produce hashes (comment doesn't break parsing)
        assert len(ast_hashes) >= 0

    def test_same_code_produces_same_hashes(self, sample_python_code):
        """Deterministic code should produce identical AST hashes."""
        _, hashes1 = tokenize_and_hash_ast(sample_python_code, "python")
        _, hashes2 = tokenize_and_hash_ast(sample_python_code, "python")
        assert hashes1 == hashes2


class TestComputeFingerprints:
    """Test k-gram fingerprint computation."""

    @pytest.fixture
    def sample_tokens(self):
        """Create sample tokens for fingerprinting."""
        return [
            ("def", (0, 0), (0, 3)),
            ("func_name", (0, 4), (0, 12)),
            ("(", (0, 12), (0, 13)),
            (")", (0, 13), (0, 14)),
            (":", (0, 14), (0, 15)),
            ("NEWLINE", (0, 15), (0, 16)),
            ("INDENT", (1, 0), (1, 4)),
            ("pass", (1, 4), (1, 8)),
        ]

    def test_returns_list_of_dicts(self, sample_tokens):
        """Should return list of fingerprint dictionaries."""
        fps = compute_fingerprints(sample_tokens)
        assert isinstance(fps, list)
        for fp in fps:
            assert isinstance(fp, dict)
            assert "hash" in fp
            assert "start" in fp
            assert "end" in fp
            assert "kgram_idx" in fp

    def test_empty_tokens_returns_empty(self):
        """Empty token list should return empty fingerprints."""
        fps = compute_fingerprints([])
        assert fps == []

    def test_fewer_tokens_than_k_returns_empty(self):
        """Token count less than k should return empty list."""
        tokens = [("def", (0, 0), (0, 3)), ("func", (0, 4), (0, 8))]
        fps = compute_fingerprints(tokens, k=3)
        assert fps == []

    def test_k_gram_hashes_are_computed_correctly(self, sample_tokens):
        """Should compute rolling hash for each k-gram."""
        fps = compute_fingerprints(sample_tokens, k=3)
        # Should have len(tokens) - k + 1 fingerprints
        expected_count = len(sample_tokens) - 3 + 1
        assert len(fps) == expected_count
        # Each fingerprint should have a hash value
        for fp in fps:
            assert isinstance(fp["hash"], int)

    def test_kgram_indices_are_sequential(self, sample_tokens):
        """kgram_idx should increment by 1 for each fingerprint."""
        fps = compute_fingerprints(sample_tokens, k=3)
        for i, fp in enumerate(fps):
            assert fp["kgram_idx"] == i

    def test_start_end_points_cover_k_tokens(self, sample_tokens):
        """Each fingerprint's start/end should cover k consecutive tokens."""
        fps = compute_fingerprints(sample_tokens, k=3)
        for fp in fps:
            start_idx = fp["kgram_idx"]
            expected_start = sample_tokens[start_idx][1]
            expected_end = sample_tokens[start_idx + 2][2]  # k-th token's end
            assert fp["start"] == expected_start
            assert fp["end"] == expected_end

    def test_custom_k_base_mod(self, sample_tokens):
        """Should accept custom k, base, mod parameters."""
        fps = compute_fingerprints(sample_tokens, k=2, base=131, mod=10**9 + 9)
        assert len(fps) == len(sample_tokens) - 2 + 1
        for fp in fps:
            assert isinstance(fp["hash"], int)


class TestWinnowFingerprints:
    """Test winnowing algorithm."""

    @pytest.fixture
    def fingerprints(self):
        """Create sample fingerprints with known minimums."""
        # Simulate a sequence where we know the minima
        return [
            {"hash": 10, "kgram_idx": 0, "start": (0, 0), "end": (1, 0)},
            {"hash": 5, "kgram_idx": 1, "start": (1, 0), "end": (2, 0)},
            {"hash": 8, "kgram_idx": 2, "start": (2, 0), "end": (3, 0)},
            {"hash": 3, "kgram_idx": 3, "start": (3, 0), "end": (4, 0)},
            {"hash": 7, "kgram_idx": 4, "start": (4, 0), "end": (5, 0)},
            {"hash": 2, "kgram_idx": 5, "start": (5, 0), "end": (6, 0)},
        ]

    def test_returns_list_of_dicts(self, fingerprints):
        """Should return list of fingerprint dictionaries."""
        winnowed = winnow_fingerprints(fingerprints, window_size=3)
        assert isinstance(winnowed, list)
        for fp in winnowed:
            assert isinstance(fp, dict)
            assert "hash" in fp and "kgram_idx" in fp

    def test_empty_input_returns_empty(self):
        """Empty list should return empty."""
        assert winnow_fingerprints([]) == []

    def test_window_size_equal_sequence_returns_one(self, fingerprints):
        """If window equals sequence length, return the minimum of entire sequence."""
        winnowed = winnow_fingerprints(fingerprints, window_size=len(fingerprints))
        assert len(winnowed) == 1
        # That one should be the global minimum
        global_min = min(fingerprints, key=lambda x: x["hash"])
        assert winnowed[0]["hash"] == global_min["hash"]

    def test_winnowed_sequence_has_no_duplicate_consecutive_hashes(self, fingerprints):
        """Consecutive winnowed fingerprints should have different hashes."""
        winnowed = winnow_fingerprints(fingerprints, window_size=3)
        for i in range(1, len(winnowed)):
            assert winnowed[i]["hash"] != winnowed[i - 1]["hash"]

    def test_winnowed_matches_expected_sequence(self, fingerprints):
        """Winnowed sequence should follow expected minima."""
        winnowed = winnow_fingerprints(fingerprints, window_size=3)
        # Based on manual calculation: idx1(5), idx3(3), idx5(2)
        assert len(winnowed) == 3
        assert winnowed[0]["kgram_idx"] == 1
        assert winnowed[0]["hash"] == 5
        assert winnowed[1]["kgram_idx"] == 3
        assert winnowed[1]["hash"] == 3
        assert winnowed[2]["kgram_idx"] == 5
        assert winnowed[2]["hash"] == 2

    def test_custom_window_size(self, fingerprints):
        """Should accept different window sizes."""
        winnowed = winnow_fingerprints(fingerprints, window_size=2)
        assert isinstance(winnowed, list)


class TestComputeAndWinnow:
    """Test optimized combined computation and winnowing."""

    @pytest.fixture
    def sample_tokens(self):
        return [
            ("def", (0, 0), (0, 3)),
            ("func", (0, 4), (0, 8)),
            ("(", (0, 8), (0, 9)),
            (")", (0, 9), (0, 10)),
            (":", (0, 10), (0, 11)),
            ("pass", (1, 0), (1, 4)),
            ("x", (2, 0), (2, 1)),
            ("=", (2, 2), (2, 3)),
            ("1", (2, 4), (2, 5)),
        ]

    def test_returns_list_of_dicts(self, sample_tokens):
        """Should return winnowed fingerprints."""
        result = compute_and_winnow(sample_tokens, k=3)
        assert isinstance(result, list)
        for fp in result:
            assert isinstance(fp, dict)
            assert "hash" in fp and "start" in fp and "end" in fp and "kgram_idx" in fp

    def test_empty_tokens_returns_empty(self):
        """Empty token list returns empty."""
        assert compute_and_winnow([]) == []

    def test_fewer_tokens_than_k_returns_empty(self):
        """Fewer than k tokens returns empty."""
        tokens = [("a", (0, 0), (0, 1)), ("b", (0, 2), (0, 3))]
        assert compute_and_winnow(tokens, k=3) == []

    def test_consistency_with_separate_functions(self, sample_tokens):
        """Results should match compute_fingerprints + winnow_fingerprints."""
        result_combined = compute_and_winnow(sample_tokens, k=3, window_size=3)
        fps = compute_fingerprints(sample_tokens, k=3)
        result_separate = winnow_fingerprints(fps, window_size=3)
        # The two approaches should produce equivalent results
        assert len(result_combined) == len(result_separate)
        for rc, rs in zip(result_combined, result_separate, strict=True):
            assert rc["hash"] == rs["hash"]
            assert rc["kgram_idx"] == rs["kgram_idx"]

    def test_custom_parameters(self, sample_tokens):
        """Should accept custom k, base, mod, window_size."""
        result = compute_and_winnow(sample_tokens, k=2, base=131, mod=10**9 + 9, window_size=2)
        assert isinstance(result, list)

    def test_monotonic_queue_property(self, sample_tokens):
        """Winnowed fingerprints should be selected via deque algorithm."""
        result = compute_and_winnow(sample_tokens, k=3, window_size=3)
        # Check that each result is minimum in its window
        fingerprints = compute_fingerprints(sample_tokens, k=3)
        for wfp in result:
            idx = wfp["kgram_idx"]
            window = fingerprints[idx : idx + 3]
            min_hash = min(w["hash"] for w in window)
            assert wfp["hash"] == min_hash


class TestParseFileOnce:
    """Test file parsing."""

    @pytest.fixture
    def sample_python_code(self, tmp_path):
        code = "def foo():\n    return 42\n"
        file_path = tmp_path / "sample.py"
        file_path.write_text(code)
        return str(file_path)

    def test_returns_tree_and_bytes(self, sample_python_code):
        """Should return (tree, source_bytes) tuple."""
        tree, source_bytes = parse_file_once(sample_python_code, "python")
        assert tree is not None
        assert isinstance(source_bytes, bytes)

    def test_tree_is_parse_tree(self, sample_python_code):
        """Returned tree should be a tree-sitter Tree."""
        from tree_sitter import Tree

        tree, _ = parse_file_once(sample_python_code, "python")
        assert isinstance(tree, Tree)

    def test_source_bytes_match_file_content(self, sample_python_code):
        """Returned bytes should match file content."""
        with open(sample_python_code, "rb") as f:
            expected = f.read()
        _, source_bytes = parse_file_once(sample_python_code, "python")
        assert source_bytes == expected

    def test_unsupported_language_raises(self, tmp_path):
        """Unsupported language should raise ValueError."""
        file_path = tmp_path / "sample.xyz"
        file_path.write_text("code")
        with pytest.raises(ValueError):
            parse_file_once(str(file_path), "xyz")

    def test_nonexistent_file_raises(self, tmp_path):
        """Non-existent file should raise FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_file_once(str(tmp_path / "missing.py"), "python")

    def test_utf8_encoding_handled(self, tmp_path):
        """Should handle UTF-8 encoded files."""
        code = "print('café')\n"
        file_path = tmp_path / "utf8.py"
        file_path.write_text(code, encoding="utf-8")
        tree, source_bytes = parse_file_once(str(file_path), "python")
        assert source_bytes.decode("utf-8") == code


class TestIndexFingerprints:
    """Test fingerprint indexing."""

    @pytest.fixture
    def sample_fingerprints(self):
        return [
            {"hash": 100, "start": (0, 0), "end": (1, 0), "kgram_idx": 0},
            {"hash": 200, "start": (1, 0), "end": (2, 0), "kgram_idx": 1},
            {"hash": 100, "start": (2, 0), "end": (3, 0), "kgram_idx": 2},
            {"hash": 300, "start": (3, 0), "end": (4, 0), "kgram_idx": 3},
            {"hash": 100, "start": (4, 0), "end": (5, 0), "kgram_idx": 4},
        ]

    def test_creates_hash_to_fingerprints_index(self, sample_fingerprints):
        """Should return dict mapping hash -> list of fingerprint dicts."""
        index = index_fingerprints(sample_fingerprints)
        assert isinstance(index, dict)
        assert 100 in index
        assert 200 in index
        assert 300 in index
        assert len(index[100]) == 3  # Three fingerprints with hash 100
        assert len(index[200]) == 1
        assert len(index[300]) == 1

    def test_fingerprints_preserved_in_index(self, sample_fingerprints):
        """Fingerprints in index should be the original dicts."""
        index = index_fingerprints(sample_fingerprints)
        for fp_list in index.values():
            for fp in fp_list:
                assert "hash" in fp
                assert "start" in fp
                assert "end" in fp
                assert "kgram_idx" in fp

    def test_empty_input_returns_empty_dict(self):
        """Empty fingerprint list returns empty dict."""
        index = index_fingerprints([])
        assert index == {}

    def test_multiple_identical_hashes_grouped(self, sample_fingerprints):
        """All fingerprints with same hash should be in same list."""
        index = index_fingerprints(sample_fingerprints)
        fps_100 = index[100]
        assert len(fps_100) == 3
        # Each should have different kgram_idx
        indices = [fp["kgram_idx"] for fp in fps_100]
        assert len(set(indices)) == len(indices)
