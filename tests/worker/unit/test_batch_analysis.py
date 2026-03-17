"""
Unit tests for analyze_plagiarism_batch function.
Tests batch pair analysis using pre-fetched fingerprint/AST data.
"""

import os
import pytest
from collections import Counter
from cli.analyzer import (
    analyze_plagiarism_batch,
    compute_fingerprints,
    winnow_fingerprints,
    index_fingerprints,
    tokenize_with_tree_sitter,
    extract_ast_hashes,
)


class TestAnalyzePlagiarismBatch:
    """Test batch plagiarism analysis."""

    def _create_file(self, tmp_path, name, content):
        """Helper to create a temp file and return its path."""
        path = os.path.join(tmp_path, name)
        with open(path, 'w') as f:
            f.write(content)
        return path

    def _prepare_fingerprints(self, file_path):
        """Helper to prepare fingerprints and AST hashes for a file."""
        tokens = tokenize_with_tree_sitter(file_path, 'python')
        fps = winnow_fingerprints(compute_fingerprints(tokens))
        ast_hashes = extract_ast_hashes(file_path, 'python', min_depth=3)
        index = index_fingerprints(fps)
        return fps, ast_hashes, index

    def test_batch_similar_files(self, tmp_path):
        """Test batch analysis detects similarity in similar files."""
        f1 = self._create_file(tmp_path, "a.py", "def hello():\n    return 'world'\n")
        f2 = self._create_file(tmp_path, "b.py", "def hello():\n    return 'world'\n")

        fps1, ast1, idx1 = self._prepare_fingerprints(f1)
        fps2, ast2, idx2 = self._prepare_fingerprints(f2)

        results = analyze_plagiarism_batch([{
            'file_a_hash': 'ha', 'file_b_hash': 'hb',
            'fps_a': fps1, 'ast_a': ast1, 'index_a': idx1, 'file_a_path': f1,
            'fps_b': fps2, 'ast_b': ast2, 'index_b': idx2, 'file_b_path': f2,
        }])

        assert len(results) == 1
        ast_sim, matches, metrics = results[0]
        assert ast_sim > 0.9  # Identical files should have high similarity

    def test_batch_different_files(self, tmp_path):
        """Test batch analysis returns low similarity for different files."""
        f1 = self._create_file(tmp_path, "a.py", "x = 1\ny = 2\nz = 3\n")
        f2 = self._create_file(tmp_path, "b.py", "import os\nimport sys\nprint('hi')\n")

        fps1, ast1, idx1 = self._prepare_fingerprints(f1)
        fps2, ast2, idx2 = self._prepare_fingerprints(f2)

        results = analyze_plagiarism_batch([{
            'file_a_hash': 'ha', 'file_b_hash': 'hb',
            'fps_a': fps1, 'ast_a': ast1, 'index_a': idx1, 'file_a_path': f1,
            'fps_b': fps2, 'ast_b': ast2, 'index_b': idx2, 'file_b_path': f2,
        }])

        assert len(results) == 1
        ast_sim, matches, metrics = results[0]
        assert ast_sim < 0.3

    def test_batch_multiple_pairs(self, tmp_path):
        """Test batch analysis handles multiple pairs."""
        f1 = self._create_file(tmp_path, "a.py", "def foo(): pass\n")
        f2 = self._create_file(tmp_path, "b.py", "def foo(): pass\n")
        f3 = self._create_file(tmp_path, "c.py", "import json\n")

        fps1, ast1, idx1 = self._prepare_fingerprints(f1)
        fps2, ast2, idx2 = self._prepare_fingerprints(f2)
        fps3, ast3, idx3 = self._prepare_fingerprints(f3)

        results = analyze_plagiarism_batch([
            {
                'file_a_hash': 'ha', 'file_b_hash': 'hb',
                'fps_a': fps1, 'ast_a': ast1, 'index_a': idx1, 'file_a_path': f1,
                'fps_b': fps2, 'ast_b': ast2, 'index_b': idx2, 'file_b_path': f2,
            },
            {
                'file_a_hash': 'ha', 'file_b_hash': 'hc',
                'fps_a': fps1, 'ast_a': ast1, 'index_a': idx1, 'file_a_path': f1,
                'fps_b': fps3, 'ast_b': ast3, 'index_b': idx3, 'file_b_path': f3,
            },
        ])

        assert len(results) == 2
        # First pair: identical files → high similarity
        assert results[0][0] > 0.5
        # Second pair: different files → low similarity
        assert results[1][0] < 0.5

    def test_batch_empty_returns_empty(self):
        """Test batch analysis with empty input returns empty list."""
        results = analyze_plagiarism_batch([])
        assert results == []

    def test_batch_early_exit_below_threshold(self, tmp_path):
        """Test that fragment building is skipped when AST sim is below threshold."""
        f1 = self._create_file(tmp_path, "a.py", "x = 1\n")
        f2 = self._create_file(tmp_path, "b.py", "import os\n")

        fps1, ast1, idx1 = self._prepare_fingerprints(f1)
        fps2, ast2, idx2 = self._prepare_fingerprints(f2)

        # Use high threshold so files with low similarity skip fragment building
        results = analyze_plagiarism_batch([{
            'file_a_hash': 'ha', 'file_b_hash': 'hb',
            'fps_a': fps1, 'ast_a': ast1, 'index_a': idx1, 'file_a_path': f1,
            'fps_b': fps2, 'ast_b': ast2, 'index_b': idx2, 'file_b_path': f2,
        }], ast_threshold=0.5)

        ast_sim, matches, metrics = results[0]
        # Below threshold → no matches, minimal metrics
        assert matches == []
        assert metrics['left_covered'] == 0
        assert metrics['right_covered'] == 0
        assert metrics['longest_fragment'] == 0

    def test_batch_uses_pre_fetched_data(self, tmp_path):
        """Test that batch analysis uses pre-fetched data without file I/O."""
        f1 = self._create_file(tmp_path, "a.py", "def foo(): pass\n")
        f2 = self._create_file(tmp_path, "b.py", "def foo(): pass\n")

        fps1, ast1, idx1 = self._prepare_fingerprints(f1)
        fps2, ast2, idx2 = self._prepare_fingerprints(f2)

        # Pass pre-fetched data, and a non-existent path to verify no I/O
        results = analyze_plagiarism_batch([{
            'file_a_hash': 'ha', 'file_b_hash': 'hb',
            'fps_a': fps1, 'ast_a': ast1, 'index_a': idx1,
            'file_a_path': '/nonexistent/path.py',
            'fps_b': fps2, 'ast_b': ast2, 'index_b': idx2,
            'file_b_path': '/nonexistent/path2.py',
        }])

        assert len(results) == 1
        ast_sim, matches, metrics = results[0]
        assert ast_sim > 0.5  # Should work despite non-existent paths

    def test_batch_builds_index_if_missing(self, tmp_path):
        """Test that index is built from fingerprints if not provided."""
        f1 = self._create_file(tmp_path, "a.py", "def foo(): pass\n")
        f2 = self._create_file(tmp_path, "b.py", "def foo(): pass\n")

        fps1, ast1, _ = self._prepare_fingerprints(f1)
        fps2, ast2, _ = self._prepare_fingerprints(f2)

        # Don't provide indexes — they should be built from fps
        results = analyze_plagiarism_batch([{
            'file_a_hash': 'ha', 'file_b_hash': 'hb',
            'fps_a': fps1, 'ast_a': ast1, 'index_a': None, 'file_a_path': f1,
            'fps_b': fps2, 'ast_b': ast2, 'index_b': None, 'file_b_path': f2,
        }])

        assert len(results) == 1
        ast_sim, _, _ = results[0]
        assert ast_sim > 0.5
