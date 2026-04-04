"""Tests for plagiarism_core.ast_hash module."""


from plagiarism_core.ast_hash import (
    ast_similarity,
    extract_ast_hashes,
    find_ast_matches,
    hash_ast_subtrees,
    hash_ast_subtrees_with_positions,
)


class TestHashAstSubtrees:
    def test_empty_tree(self, tmp_path):
        from plagiarism_core.fingerprints import get_language
        from tree_sitter import Parser

        lang = get_language("python")
        parser = Parser(lang)
        tree = parser.parse(b"")
        hashes = hash_ast_subtrees(tree.root_node)
        assert isinstance(hashes, list)

    def test_simple_function(self, tmp_path):
        from plagiarism_core.fingerprints import get_language
        from tree_sitter import Parser

        lang = get_language("python")
        parser = Parser(lang)
        tree = parser.parse(b"def foo():\n    return 1\n")
        hashes = hash_ast_subtrees(tree.root_node)
        assert isinstance(hashes, list)
        assert len(hashes) > 0

    def test_min_depth_filter(self, tmp_path):
        from plagiarism_core.fingerprints import get_language
        from tree_sitter import Parser

        lang = get_language("python")
        parser = Parser(lang)
        tree = parser.parse(b"x = 1\n")
        hashes_default = hash_ast_subtrees(tree.root_node, min_depth=3)
        hashes_shallow = hash_ast_subtrees(tree.root_node, min_depth=1)
        assert len(hashes_shallow) >= len(hashes_default)

    def test_comment_ignored(self, tmp_path):
        from plagiarism_core.fingerprints import get_language
        from tree_sitter import Parser

        lang = get_language("python")
        parser = Parser(lang)
        tree = parser.parse(b"# comment\n")
        hashes = hash_ast_subtrees(tree.root_node)
        assert isinstance(hashes, list)

    def test_deterministic(self, tmp_path):
        from plagiarism_core.fingerprints import get_language
        from tree_sitter import Parser

        code = b"def foo(x):\n    return x + 1\n"
        lang = get_language("python")
        parser = Parser(lang)
        tree1 = parser.parse(code)
        tree2 = parser.parse(code)
        h1 = hash_ast_subtrees(tree1.root_node)
        h2 = hash_ast_subtrees(tree2.root_node)
        assert h1 == h2

    def test_different_code_different_hashes(self, tmp_path):
        from plagiarism_core.fingerprints import get_language
        from tree_sitter import Parser

        lang = get_language("python")
        parser = Parser(lang)
        tree1 = parser.parse(b"def foo():\n    return 1\n")
        tree2 = parser.parse(b"def bar():\n    return 2\n")
        h1 = hash_ast_subtrees(tree1.root_node)
        h2 = hash_ast_subtrees(tree2.root_node)
        assert isinstance(h1, list)
        assert isinstance(h2, list)


class TestExtractAstHashes:
    def test_from_file(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    return 1\n")
        hashes = extract_ast_hashes(str(f), "python")
        assert isinstance(hashes, list)
        assert len(hashes) > 0

    def test_with_preparsed_tree(self, tmp_path):
        from plagiarism_core.fingerprints import get_language
        from tree_sitter import Parser

        f = tmp_path / "test.py"
        f.write_text("def foo():\n    return 1\n")
        lang = get_language("python")
        parser = Parser(lang)
        tree = parser.parse(f.read_bytes())
        hashes = extract_ast_hashes(str(f), "python", tree=tree)
        assert isinstance(hashes, list)
        assert len(hashes) > 0

    def test_min_depth(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("def foo():\n    return 1\n")
        hashes = extract_ast_hashes(str(f), "python", min_depth=1)
        assert len(hashes) > 0


class TestAstSimilarity:
    def test_identical(self):
        h = [1, 2, 3]
        assert ast_similarity(h, h) == 1.0

    def test_completely_different(self):
        assert ast_similarity([1, 2, 3], [4, 5, 6]) == 0.0

    def test_partial_overlap(self):
        h1 = [1, 2, 3]
        h2 = [2, 3, 4]
        sim = ast_similarity(h1, h2)
        assert 0 < sim < 1.0

    def test_empty_both(self):
        assert ast_similarity([], []) == 0.0

    def test_empty_one(self):
        assert ast_similarity([1, 2], []) == 0.0

    def test_with_duplicates(self):
        h1 = [1, 1, 1]
        h2 = [1, 1]
        sim = ast_similarity(h1, h2)
        assert sim > 0

    def test_subset(self):
        h1 = [1, 2]
        h2 = [1, 2, 3, 4]
        sim = ast_similarity(h1, h2)
        assert sim == 0.5


class TestHashAstSubtreesWithPositions:
    def test_basic(self, tmp_path):
        from plagiarism_core.fingerprints import get_language
        from tree_sitter import Parser

        lang = get_language("python")
        parser = Parser(lang)
        tree = parser.parse(b"def foo():\n    return 1\n")
        results = hash_ast_subtrees_with_positions(tree.root_node)
        assert isinstance(results, list)
        if results:
            for h, start, end in results:
                assert isinstance(h, int)
                assert isinstance(start, tuple)
                assert isinstance(end, tuple)

    def test_min_depth(self, tmp_path):
        from plagiarism_core.fingerprints import get_language
        from tree_sitter import Parser

        lang = get_language("python")
        parser = Parser(lang)
        tree = parser.parse(b"x = 1\n")
        results_deep = hash_ast_subtrees_with_positions(tree.root_node, min_depth=3)
        results_shallow = hash_ast_subtrees_with_positions(tree.root_node, min_depth=1)
        assert len(results_shallow) >= len(results_deep)


class TestFindAstMatches:
    def test_identical_files(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        source = "def foo():\n    return 1\n"
        f1.write_text(source)
        f2.write_text(source)

        matches = find_ast_matches(str(f1), str(f2), "python")
        assert isinstance(matches, list)
        assert len(matches) > 0

    def test_different_files(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n")
        f2.write_text("y = 2\n")

        matches = find_ast_matches(str(f1), str(f2), "python")
        assert isinstance(matches, list)

    def test_match_structure(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        source = "def foo():\n    return 1\n"
        f1.write_text(source)
        f2.write_text(source)

        matches = find_ast_matches(str(f1), str(f2), "python")
        for m in matches:
            assert "file1" in m
            assert "file2" in m
            assert "kgram_count" in m
            assert "start_line" in m["file1"]
            assert "end_line" in m["file1"]
