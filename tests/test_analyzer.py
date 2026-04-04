"""Tests for plagiarism_core.analyzer module."""


from plagiarism_core.analyzer import Analyzer


class TestAnalyzeSources:
    def setup_method(self):
        self.analyzer = Analyzer()

    def test_identical_code(self):
        source = "def hello():\n    return 42\n"
        result = self.analyzer.analyze_sources(source, source, "python")
        assert result.similarity_ratio == 1.0
        assert len(result.matches) > 0
        assert result.language == "python"

    def test_different_code(self):
        s1 = "def add(a, b): return a + b\n"
        s2 = "def sub(a, b): return a - b\n"
        result = self.analyzer.analyze_sources(s1, s2, "python")
        assert result.language == "python"
        assert result.metrics is not None

    def test_empty_sources(self):
        result = self.analyzer.analyze_sources("", "", "python")
        assert result.similarity_ratio == 0.0
        assert len(result.matches) == 0

    def test_with_file_paths(self):
        source = "x = 1\n"
        result = self.analyzer.analyze_sources(
            source, source, "python", file1_path="a.py", file2_path="b.py"
        )
        assert result.file1_path == "a.py"
        assert result.file2_path == "b.py"

    def test_renamed_identifiers(self):
        s1 = "def foo(x):\n    return x + 1\n"
        s2 = "def bar(y):\n    return y + 1\n"
        result = self.analyzer.analyze_sources(s1, s2, "python")
        assert len(result.matches) > 0

    def test_metrics_computed(self):
        s1 = "def foo():\n    return 1\n"
        s2 = "def foo():\n    return 1\n"
        result = self.analyzer.analyze_sources(s1, s2, "python")
        assert result.metrics.left_covered >= 0
        assert result.metrics.right_covered >= 0
        assert result.metrics.left_total > 0
        assert result.metrics.right_total > 0

    def test_parse_failure_graceful(self):
        source = "this is not valid python code {{{{"
        result = self.analyzer.analyze_sources(source, source, "python")
        assert result is not None
        assert result.language == "python"


class TestAnalyze:
    def setup_method(self):
        self.analyzer = Analyzer()

    def test_analyze_files(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        source = "def hello():\n    return 42\n"
        f1.write_text(source)
        f2.write_text(source)

        result = self.analyzer.analyze(str(f1), str(f2), "python")
        assert result.similarity_ratio == 1.0
        assert len(result.matches) > 0
        assert result.file1_path == str(f1)
        assert result.file2_path == str(f2)

    def test_analyze_different_files(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n")
        f2.write_text("y = 2\n")

        result = self.analyzer.analyze(str(f1), str(f2), "python")
        assert result is not None


class TestAnalyzeCached:
    def setup_method(self):
        self.analyzer = Analyzer()

    def test_cached_analysis_cache_hit(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        source = "def foo():\n    return 1\n"
        f1.write_text(source)
        f2.write_text(source)

        cached_hashes = {
            "hash1": [123, 456],
            "hash2": [123, 456],
        }

        ast_sim, matches_data, metrics = self.analyzer.analyze_cached(
            file1_path=str(f1),
            file2_path=str(f2),
            file1_hash="hash1",
            file2_hash="hash2",
            get_ast_hashes=lambda h: cached_hashes.get(h),
            language="python",
        )

        assert ast_sim == 1.0
        assert isinstance(matches_data, list)
        assert isinstance(metrics, dict)
        assert "left_covered" in metrics
        assert "right_covered" in metrics
        assert "similarity" in metrics

    def test_cached_analysis_cache_miss(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        source = "def foo():\n    return 1\n"
        f1.write_text(source)
        f2.write_text(source)

        ast_sim, matches_data, metrics = self.analyzer.analyze_cached(
            file1_path=str(f1),
            file2_path=str(f2),
            file1_hash="new1",
            file2_hash="new2",
            get_ast_hashes=lambda h: None,
            language="python",
        )

        assert ast_sim == 1.0
        assert isinstance(matches_data, list)

    def test_cached_analysis_different_code(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n")
        f2.write_text("y = 2\n")

        ast_sim, matches_data, metrics = self.analyzer.analyze_cached(
            file1_path=str(f1),
            file2_path=str(f2),
            file1_hash="h1",
            file2_hash="h2",
            get_ast_hashes=lambda h: None,
            language="python",
        )

        assert isinstance(ast_sim, float)
        assert isinstance(matches_data, list)
        assert isinstance(metrics, dict)

    def test_cached_matches_have_1_indexed_lines(self, tmp_path):
        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        source = "def foo():\n    return 1\n"
        f1.write_text(source)
        f2.write_text(source)

        _, matches_data, _ = self.analyzer.analyze_cached(
            file1_path=str(f1),
            file2_path=str(f2),
            file1_hash="h1",
            file2_hash="h2",
            get_ast_hashes=lambda h: None,
            language="python",
        )

        for m in matches_data:
            assert m["file1"]["start_line"] >= 1
            assert m["file2"]["start_line"] >= 1
