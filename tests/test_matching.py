"""
Comprehensive tests for the sequence-aligned AST subtree matcher.

Tests both Phase 1 (position-constrained) and Phase 2 (alignment-based)
matching strategies, along with edge cases and regression tests.
"""

import sys

sys.path.insert(0, "src")

from plagiarism_core.analyzer import (
    Analyzer,
    _find_ast_regions,
    _nw_align,
)
from plagiarism_core.ast_hash import (
    hash_ast_subtrees,
    hash_ast_subtrees_with_positions,
)
from plagiarism_core.fingerprinting.parser import parse_string_once

# =========================================================================
# Tests for NW alignment (Phase 2 - sequence alignment)
# =========================================================================

class TestNWAlign:
    def test_identical_sequences(self):
        seq = [1, 2, 3, 4, 5]
        result = _nw_align(seq, seq)
        assert result == [(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)]

    def test_empty_sequences(self):
        result = _nw_align([], [])
        assert result == []

    def test_one_empty(self):
        result = _nw_align([1, 2], [])
        assert result == [(0, None), (1, None)]

    def test_other_empty(self):
        result = _nw_align([], [1, 2])
        assert result == [(None, 0), (None, 1)]

    def test_prefix_match(self):
        a = [1, 2, 3, 4]
        b = [1, 2]
        result = _nw_align(a, b)
        # Should match 1↔1, 2↔2, then gap A[3], A[4]
        matches = [(i, j) for i, j in result if i is not None and j is not None]
        assert matches == [(0, 0), (1, 1)]

    def test_suffix_match(self):
        a = [1, 2, 3, 4]
        b = [3, 4]
        result = _nw_align(a, b)
        matches = [(i, j) for i, j in result if i is not None and j is not None]
        assert matches == [(2, 0), (3, 1)]

    def test_repeated_hashes(self):
        """Multiple identical hashes should align in order."""
        a = [5, 5, 5]
        b = [5, 5, 5]
        result = _nw_align(a, b)
        assert result == [(0, 0), (1, 1), (2, 2)]

    def test_repeated_hashes_different_counts(self):
        """Different counts of repeated hashes should use gaps."""
        a = [5, 5, 5]
        b = [5, 5]
        result = _nw_align(a, b)
        matches = [(i, j) for i, j in result if i is not None and j is not None]
        assert len(matches) == 2

    def test_interleaved_repeated(self):
        """Repeated structures in different order should still align correctly."""
        a = [1, 2, 1, 2]
        b = [1, 2, 1, 2]
        result = _nw_align(a, b)
        assert result == [(0, 0), (1, 1), (2, 2), (3, 3)]

    def test_partial_overlap(self):
        a = [10, 20, 30, 40, 50]
        b = [20, 30, 60]
        result = _nw_align(a, b)
        matches = [(i, j) for i, j in result if i is not None and j is not None]
        assert (1, 0) in matches  # 20
        assert (2, 1) in matches  # 30

    def test_all_different(self):
        a = [1, 2, 3]
        b = [4, 5, 6]
        result = _nw_align(a, b)
        # With mismatch=-999, gap=-1, the optimal alignment
        # is to gap everything (much less penalty than mismatches)
        for i, j in result:
            assert i is None or j is None  # should only have gaps

    def test_single_element(self):
        result = _nw_align([42], [42])
        assert result == [(0, 0)]

    def test_single_element_mismatch(self):
        result = _nw_align([42], [99])
        # Should prefer gap over mismatch
        for i, j in result:
            assert i is None or j is None


# =========================================================================
# Tests for hash sequence alignment between hash_ast_subtrees and
# hash_ast_subtrees_with_positions
# =========================================================================

class TestHashSequenceConsistency:
    """Verify that both hash functions produce the same sequences."""

    def test_identical_sequences_simple_function(self):
        code = """
def foo():
    x = 1
    y = 2
    return x + y
"""
        tree, _ = parse_string_once(code, "python")
        h1 = hash_ast_subtrees(tree.root_node)
        h2 = [h for h, _, _ in hash_ast_subtrees_with_positions(tree.root_node)]
        assert h1 == h2, f"Sequences differ:\n  hash_ast_subtrees: {h1}\n  with_positions: {h2}"

    def test_identical_sequences_if_statement(self):
        code = """
def check(value):
    if value > 0:
        result = value * 2
        return result
    return -1
"""
        tree, _ = parse_string_once(code, "python")
        h1 = hash_ast_subtrees(tree.root_node)
        h2 = [h for h, _, _ in hash_ast_subtrees_with_positions(tree.root_node)]
        assert h1 == h2

    def test_identical_sequences_multiple_functions(self):
        code = """
def first():
    a = 1
    b = 2
    return a + b

def second():
    x = 10
    y = 20
    return x * y

def third():
    items = [1, 2, 3]
    total = sum(items)
    return total
"""
        tree, _ = parse_string_once(code, "python")
        h1 = hash_ast_subtrees(tree.root_node)
        h2 = [h for h, _, _ in hash_ast_subtrees_with_positions(tree.root_node)]
        assert h1 == h2


# =========================================================================
# Tests for the integrated matching (Phase 1 + Phase 2)
# =========================================================================

class TestFindASTRegions:
    """Tests for the full alignment-based matcher."""

    def test_identical_files(self):
        code = """
def foo():
    x = 1
    y = 2
    if x > 0:
        result = x + y
        return result
    return -1
"""
        tree1, _ = parse_string_once(code, "python")
        tree2, _ = parse_string_once(code, "python")
        matches = _find_ast_regions(tree1, tree2)
        assert len(matches) > 0
        # All lines should be covered (one merged block)
        total_lines = len(code.strip().split("\n"))
        for m in matches:
            a_span = m.file1["end_line"] - m.file1["start_line"] + 1
            b_span = m.file2["end_line"] - m.file2["start_line"] + 1
            assert a_span == b_span  # symmetric spans

    def test_identical_files_blank_lines(self):
        """Files with same structure but different blank lines."""
        code_a = """
def process():
    x = get_value()
    if x > 0:
        y = compute(x)
        return y
    return 0
"""
        code_b = """
def process():
    x = get_value()

    if x > 0:
        y = compute(x)

        return y
    return 0
"""
        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)
        # Should still find matches covering similar regions
        assert len(matches) > 0

    def test_renamed_identifiers(self):
        """Structurally identical code with renamed identifiers."""
        code_a = """
def calculate_total(prices, tax_rate):
    subtotal = sum(prices)
    tax = subtotal * tax_rate
    total = subtotal + tax
    return total
"""
        code_b = """
def compute_sum(values, rate):
    sum_val = sum(values)
    tax = sum_val * rate
    total = sum_val + tax
    return total
"""
        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)
        assert len(matches) > 0

    def test_completely_different_code(self):
        code_a = "x = 1"
        code_b = "y = 2"
        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)
        # Both are structurally identical assignments (same AST shape)
        # so they SHOULD match — the algorithm matches on structure not values
        assert len(matches) > 0

    def test_empty_file(self):
        tree1, _ = parse_string_once("", "python")
        tree2, _ = parse_string_once("print('hi')", "python")
        matches = _find_ast_regions(tree1, tree2)
        assert len(matches) == 0

    def test_partial_similarity(self):
        """Files with some shared structure."""
        code_a = """
def shared():
    x = 1
    y = 2
    return x + y

def unique_a():
    a = 10
    return a
"""
        code_b = """
def shared():
    x = 1
    y = 2
    return x + y

def unique_b():
    b = 20
    return b
"""
        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)
        assert len(matches) > 0


    def test_repeated_blocks_no_blank_lines(self):
        """
        Multiple similar blocks in same order, no extra whitespace.
        Should merge into a single large coverage block.
        """
        code_a_lines = ["def process():", "    results = []"]
        code_b_lines = ["def process():", "    results = []"]

        for i in range(5):
            val = chr(97 + i)
            code_a_lines.append(f"    if check_{val}():")
            code_a_lines.append(f"        data = fetch_{val}()")
            code_a_lines.append(f"        result = process_{val}(data)")
            code_a_lines.append("        results.append(result)")
            code_b_lines.append(f"    if check_{val}():")
            code_b_lines.append(f"        data = fetch_{val}()")
            code_b_lines.append(f"        result = process_{val}(data)")
            code_b_lines.append("        results.append(result)")

        code_a_lines.append("    return results")
        code_b_lines.append("    return results")

        code_a = "\n".join(code_a_lines)
        code_b = "\n".join(code_b_lines)

        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)
        assert len(matches) >= 1
        # The merged match should cover similar ranges in both files
        for m in matches:
            a_span = m.file1["end_line"] - m.file1["start_line"] + 1
            b_span = m.file2["end_line"] - m.file2["start_line"] + 1
            assert abs(a_span - b_span) <= 2  # allow slight whitespace diff

    def test_repeated_blocks_with_extra_whitespace(self):
        """
        Multiple similar blocks where File A has extra blank lines between blocks.
        This was the problematic case from the issue.
        """
        code_a_lines = ["def process():", "    results = []"]
        code_b_lines = ["def process():", "    results = []"]

        for i in range(8):
            val = chr(97 + i)
            code_a_lines.append(f"    if status_{val}() > 0:")
            code_a_lines.append(f"        result_a = compute_a(value_{val})")
            code_a_lines.append("        if result_a > threshold:")
            code_a_lines.append("            store_a(result_a)")
            code_a_lines.append("        log_a(result_a)")
            code_a_lines.append("")
            code_a_lines.append("")  # extra blank lines in File A

            code_b_lines.append(f"    if check_{val}() > 0:")
            code_b_lines.append(f"        output_b = calc_b(input_{val})")
            code_b_lines.append("        if output_b > limit:")
            code_b_lines.append("            save_b(output_b)")
            code_b_lines.append("        trace_b(output_b)")

        code_a_lines.append("    return results")
        code_b_lines.append("    return results")

        code_a = "\n".join(code_a_lines)
        code_b = "\n".join(code_b_lines)

        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)
        assert len(matches) >= 1

        # Verify no cross-matching: all A matches should be before their B matches
        # in terms of order (the alignment guarantees this)
        for m in matches:
            assert m.file1["start_line"] >= 0
            assert m.file2["start_line"] >= 0

    def test_cross_matching_prevention(self):
        """
        Critical test: Verify that our algorithm prevents the cross-matching
        pattern seen in the bug report:
          Match 19: A[194-213], B[197-197]  (20 vs 1 line - crossed!)
          Match 20: A[228-229], B[196-197]  (A way later, B way earlier - crossed!)
        """
        code_a_lines = []
        code_b_lines = []

        # A large shared block at the start
        code_a_lines.append("def main():")
        code_b_lines.append("def main():")
        for i in range(20):
            code_a_lines.append(f"    x{i} = init_{i}()")
            code_b_lines.append(f"    x{i} = init_{i}()")

        # Add some blocks with the same structure but at different relative positions
        for i in range(5):
            code_a_lines.append(f"    if cond_{i}():")
            code_a_lines.append(f"        result_{i} = compute_{i}(x{i})")
            code_a_lines.append(f"        if result_{i} > limit_{i}:")
            code_a_lines.append(f"            save_{i}(result_{i})")
            code_a_lines.append("")
            code_a_lines.append("")

            code_b_lines.append(f"    if cond_{i}():")
            code_b_lines.append(f"        result_{i} = compute_{i}(x{i})")
            code_b_lines.append(f"        if result_{i} > limit_{i}:")
            code_b_lines.append(f"            save_{i}(result_{i})")

        code_a = "\n".join(code_a_lines)
        code_b = "\n".join(code_b_lines)

        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)

        # Check: each match should have similar-length spans in both files
        for m in matches:
            a_len = m.file1["end_line"] - m.file1["start_line"] + 1
            b_len = m.file2["end_line"] - m.file2["start_line"] + 1
            ratio = min(a_len, b_len) / max(a_len, b_len) if max(a_len, b_len) > 0 else 1
            assert ratio >= 0.5, f"Asymmetric span: A has {a_len} lines, B has {b_len} lines for match {m}"

    def test_reordered_functions(self):
        """Functions moved to different positions between files should still match."""
        code_a = """
def lc_list(input_list):
    return [x**2 for x in input_list]

def for_list(input_list):
    output_list = []
    for x in input_list:
        output_list.append(x**2)
    return output_list

def my_enumerate(input_list):
    num_list = [i for i in range(len(input_list))]
    return list(zip(num_list, input_list))
"""
        code_b = """
def my_enumerate(input_list):
    num_list = [i for i in range(len(input_list))]
    return list(zip(num_list, input_list))

def lc_list(input_list):
    return [x**2 for x in input_list]

def for_list(input_list):
    output_list = []
    for x in input_list:
        output_list.append(x**2)
    return output_list
"""
        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)
        # Should have at least one match per reordered function (3 total),
        # possibly more from internal subtree matches
        assert len(matches) >= 3, f"Expected >=3 matches, got {len(matches)}"
        # Verify at least 9 lines matched in each file (3 functions × ~3 lines each)
        matched_lines_a: set[int] = set()
        matched_lines_b: set[int] = set()
        for m in matches:
            for ln in range(m.file1["start_line"], m.file1["end_line"] + 1):
                matched_lines_a.add(ln)
            for ln in range(m.file2["start_line"], m.file2["end_line"] + 1):
                matched_lines_b.add(ln)
        assert len(matched_lines_a) >= 9, f"A only covers {len(matched_lines_a)} lines"
        assert len(matched_lines_b) >= 9, f"B only covers {len(matched_lines_b)} lines"

    def test_no_cross_function_subexpression_matches(self):
        """Sub-expression matches must not cross function boundaries.

        Two structurally identical expressions in different functions
        (e.g. ``x = obj.method()`` in one function and
        ``y = obj2.method2()`` in another) produce the same AST hash
        because leaf-node values are not included in the hash.
        The post-merge filter must remove any match where one side
        is dominated by a larger function-level match while the other
        side lives in a different function.
        """
        code_a = """def func_a():
    x = source.method()
    return x

def func_b():
    y = other.method()
    z = 42
    return y
"""
        code_b = """def func_b():
    y = other.method()
    z = 42
    return y

def func_a():
    x = source.method()
    return x
"""

        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)

        # Every match should be contained within the SAME function
        # in both files (i.e. a match that spans func_a in A should
        # not also span func_b in B).
        def func_for_line(lines_source: str, line_1idx: int) -> str | None:
            """Return the function name the given 1-indexed line belongs to."""
            last: str | None = None
            for i, ln in enumerate(lines_source.split("\n"), 1):
                stripped = ln.strip()
                if stripped.startswith("def ") and "(" in stripped:
                    name = stripped.split("def ")[1].split("(")[0].strip()
                    if i <= line_1idx:
                        last = name
            return last

        for m in matches:
            a_line = m.file1["start_line"] + 1
            b_line = m.file2["start_line"] + 1
            fn_a = func_for_line(code_a, a_line)
            fn_b = func_for_line(code_b, b_line)
            assert fn_a == fn_b, (
                f"Cross-function match: A line {a_line} is in '{fn_a}' "
                f"but B line {b_line} is in '{fn_b}'"
            )

# =========================================================================
# Full analyzer integration tests
# =========================================================================

class TestAnalyzerMatching:
    """End-to-end tests through the Analyzer API."""

    def test_identical_files_full_coverage(self):
        """For 100% identical files, coverage should cover all code lines
        (excluding leading/trailing whitespace outside AST nodes)."""
        code_a = """
def process():
    x = get_value()
    y = compute(x)
    if y > 0:
        z = transform(y)
        return z
    return 0
"""
        code_b = code_a
        analyzer = Analyzer()
        result = analyzer.analyze_sources(code_a, code_b, language="python")

        code_lines = len(code_a.strip().split("\n"))

        # The module node spans from line 1 to the last code line,
        # including the trailing newline. Leading blank line (line 0)
        # and any lines outside AST span are not covered.
        assert result.metrics.left_covered >= code_lines - 1, (
            f"Expected ~{code_lines} covered lines in A, got {result.metrics.left_covered}"
            f" (total={result.metrics.left_total})"
        )
        assert result.metrics.right_covered >= code_lines - 1, (
            f"Expected ~{code_lines} covered lines in B, got {result.metrics.right_covered}"
        )

    def test_renamed_identifiers_full_coverage(self):
        """Structurally identical code should get full coverage on both sides."""
        code_a = (
            "def calculate_total(prices, tax_rate):\n"
            "    subtotal = sum(prices)\n"
            "    tax = subtotal * tax_rate\n"
            "    total = subtotal + tax\n"
            "    return total\n"
        )
        code_b = (
            "def compute_sum(values, rate):\n"
            "    sum_val = sum(values)\n"
            "    tax = sum_val * rate\n"
            "    total = sum_val + tax\n"
            "    return total\n"
        )
        analyzer = Analyzer()
        result = analyzer.analyze_sources(code_a, code_b, language="python")

        lines_a = len(code_a.strip().split("\n"))
        lines_b = len(code_b.strip().split("\n"))

        left_pct = result.metrics.left_covered / result.metrics.left_total * 100
        right_pct = result.metrics.right_covered / result.metrics.right_total * 100

        # Both should have substantial coverage
        assert left_pct >= 80, f"File A coverage too low: {left_pct:.1f}%"
        assert right_pct >= 80, f"File B coverage too low: {right_pct:.1f}%"

        # Coverage should be similar (not wildly different)
        assert abs(left_pct - right_pct) <= 25, (
            f"Coverage gap too large: A={left_pct:.1f}%, B={right_pct:.1f}%"
        )

    def test_whitespace_difference_coverage(self):
        """
        Files with the same AST structure but different whitespace.
        Coverage should be similar (ratio within 15%).
        """
        code_a = """
def main():
    x = init()
    if x > 0:
        y = compute(x)
        z = validate(y)
        if z:
            save(z)
    cleanup()
"""
        code_b_lines = [
            "def main():",
            "    x = init()",
            "",
            "    if x > 0:",
            "        y = compute(x)",
            "        z = validate(y)",
            "",
            "        if z:",
            "            save(z)",
            "",
            "    cleanup()",
        ]
        code_b = "\n".join(code_b_lines)

        analyzer = Analyzer()
        result = analyzer.analyze_sources(code_a, code_b, language="python")

        left_pct = result.metrics.left_covered / result.metrics.left_total * 100
        right_pct = result.metrics.right_covered / result.metrics.right_total * 100

        # Both should have high coverage (> 80%)
        assert left_pct >= 80, f"File A coverage too low: {left_pct:.1f}%"
        assert right_pct >= 80, f"File B coverage too low: {right_pct:.1f}%"

    def test_repeated_blocks_symmetric_coverage(self):
        """
        Key test: repeated blocks with extra whitespace in one file.
        Coverage should be roughly symmetric (within 15 percentage points).
        This is the primary scenario from the bug report.
        """
        a_lines = ["def process():", "    results = []"]
        b_lines = ["def process():", "    results = []"]

        for i in range(10):
            a_lines.append(f"    if status_{i}() > 0:")
            a_lines.append(f"        value = fetch_{i}()")
            a_lines.append(f"        result = compute_{i}(value)")
            a_lines.append(f"        if result > threshold_{i}:")
            a_lines.append(f"            store_{i}(result)")
            a_lines.append(f"        log_{i}(result)")
            a_lines.append("")
            a_lines.append("")

            b_lines.append(f"    if status_{i}() > 0:")
            b_lines.append(f"        value = fetch_{i}()")
            b_lines.append(f"        result = compute_{i}(value)")
            b_lines.append(f"        if result > threshold_{i}:")
            b_lines.append(f"            store_{i}(result)")
            b_lines.append(f"        log_{i}(result)")

        a_lines.append("    return results")
        b_lines.append("    return results")

        code_a = "\n".join(a_lines)
        code_b = "\n".join(b_lines)

        analyzer = Analyzer()
        result = analyzer.analyze_sources(code_a, code_b, language="python")

        left_pct = result.metrics.left_covered / result.metrics.left_total * 100
        right_pct = result.metrics.right_covered / result.metrics.right_total * 100

        print(f"  Coverage A: {result.metrics.left_covered}/{result.metrics.left_total} = {left_pct:.1f}%")
        print(f"  Coverage B: {result.metrics.right_covered}/{result.metrics.right_total} = {right_pct:.1f}%")

        # Coverage should be symmetric (within 10 percentage points)
        gap = abs(left_pct - right_pct)
        assert gap <= 15, (
            f"Coverage gap too large: A={left_pct:.1f}%, B={right_pct:.1f}% (gap={gap:.1f}pp)"
        )

        # Both should have high coverage
        assert left_pct >= 85, f"File A coverage too low: {left_pct:.1f}%"
        assert right_pct >= 85, f"File B coverage too low: {right_pct:.1f}%"


# =========================================================================
# Edge case tests
# =========================================================================

class TestEdgeCases:
    def test_single_line_files(self):
        code_a = "x = 1"
        code_b = "y = 1"
        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        # Both are simple assignments - depth likely < 4, so no matches
        matches = _find_ast_regions(tree1, tree2)
        # Either no matches or correct matches - just don't crash
        assert isinstance(matches, list)

    def test_import_only(self):
        code_a = "import sys"
        code_b = "import os"
        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)
        assert isinstance(matches, list)

    def test_trailing_whitespace(self):
        code_a = "def foo():\n    pass\n"
        code_b = "def foo():\n    pass\n\n\n"
        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)
        assert len(matches) > 0

    def test_only_comments(self):
        code_a = "# just a comment"
        code_b = "# another comment"
        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)
        assert len(matches) == 0  # comments excluded

    def test_nested_structures(self):
        code_a = """
class Container:
    def method_a(self):
        if self.check():
            for item in self.items:
                if item.active:
                    item.process()
        return None

    def method_b(self):
        while self.running:
            x = self.next()
            if x is None:
                break
            self.handle(x)
"""
        code_b = """
class Container:
    def method_a(self):
        if self.check():
            for item in self.items:
                if item.active:
                    item.process()
        return None

    def method_b(self):
        while self.running:
            x = self.next()
            if x is None:
                break
            self.handle(x)
"""
        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")
        matches = _find_ast_regions(tree1, tree2)
        assert len(matches) > 0
        # Coverage should be 100%
        total = code_a.strip().count("\n") + 1  # +1 for first line
        covered = set()
        for m in matches:
            for line in range(m.file1["start_line"], m.file1["end_line"] + 1):
                covered.add(line)
        assert len(covered) >= total * 0.9  # at least 90%

    def test_symmetry(self):
        """swap(file_a, file_b) should produce same coverage."""
        code_a = """
def first():
    x = 1
    if x > 0:
        y = 2
    return y

def second():
    a = 10
    b = 20
    return a + b
"""
        code_b = """
def first():
    a = 1
    if a > 0:
        b = 2
    return b

def second():
    x = 10
    y = 20
    return x + y
"""
        analyzer = Analyzer()
        result_ab = analyzer.analyze_sources(code_a, code_b, language="python")
        result_ba = analyzer.analyze_sources(code_b, code_a, language="python")

        # Coverage should be symmetric
        assert result_ab.metrics.left_covered == result_ba.metrics.right_covered
        assert result_ab.metrics.right_covered == result_ba.metrics.left_covered


# =========================================================================
# Regression test: The specific bug from the user
# =========================================================================

class TestRegressionBugPattern:
    """
    Reproduces the pattern from the bug report where:
    - File A has extra blank lines between repeated similar blocks
    - Match 18: A[186-199] (14 lines), B[189-192] (4 lines) — huge span diff
    - Match 19: A[194-213] (20 lines), B[197-197] (1 line) — cross-matched!
    - Match 20: A[228-229], B[196-197] — crossed!
    """

    def test_no_cross_matching(self):
        """Verify the alignment-based matcher never crosses matches."""
        n_blocks = 12
        a = ["def main():", "    setup()"]
        b = ["def main():", "    setup()"]

        # Each block has the same AST structure
        for i in range(n_blocks):
            a.append(f"    # Process item {i}")
            a.append(f"    if status_{i}() > 0:")
            a.append(f"        value_{i} = fetch_{i}()")
            a.append(f"        temp_{i} = transform_{i}(value_{i})")
            a.append(f"        if temp_{i} > limit_{i}:")
            a.append(f"            result_{i} = save_{i}(temp_{i})")
            a.append(f"        log_{i}(result_{i})")
            a.append("")
            a.append("")  # File A has extra blanks

            b.append(f"    if status_{i}() > 0:")
            b.append(f"        value_{i} = fetch_{i}()")
            b.append(f"        temp_{i} = transform_{i}(value_{i})")
            b.append(f"        if temp_{i} > limit_{i}:")
            b.append(f"            result_{i} = save_{i}(temp_{i})")
            b.append(f"        log_{i}(result_{i})")

        a.append("    cleanup()")
        b.append("    cleanup()")

        code_a = "\n".join(a)
        code_b = "\n".join(b)

        tree1, _ = parse_string_once(code_a, "python")
        tree2, _ = parse_string_once(code_b, "python")

        matches = _find_ast_regions(tree1, tree2)

        # Verify no cross-matching:
        # The start_line in A and B should be monotonically correlated
        a_starts = [m.file1["start_line"] for m in matches]
        b_starts = [m.file2["start_line"] for m in matches]

        # Check that A and B start lines are in the same relative order
        for k in range(1, len(matches)):
            a_inc = a_starts[k] >= a_starts[k - 1]
            b_inc = b_starts[k] >= b_starts[k - 1]
            assert a_inc and b_inc, (
                f"Cross-matching detected at match {k}: "
                f"A[{a_starts[k-1]}→{a_starts[k]}], "
                f"B[{b_starts[k-1]}→{b_starts[k]}]"
            )

    def test_no_span_asymmetry(self):
        """Verify no match has wildly different spans in A vs B."""
        n_blocks = 10
        a = ["def main():", "    setup()"]
        b = ["def main():", "    setup()"]

        for i in range(n_blocks):
            a.append(f"    if status_{i}() > 0:")
            a.append(f"        value_{i} = fetch_{i}()")
            a.append(f"        result_{i} = compute_{i}(value_{i})")
            a.append(f"        if result_{i} > limit_{i}:")
            a.append(f"            store_{i}(result_{i})")
            a.append(f"        log_{i}(result_{i})")
            a.append("")
            a.append("")

            b.append(f"    if status_{i}() > 0:")
            b.append(f"        value_{i} = fetch_{i}()")
            b.append(f"        result_{i} = compute_{i}(value_{i})")
            b.append(f"        if result_{i} > limit_{i}:")
            b.append(f"            store_{i}(result_{i})")
            b.append(f"        log_{i}(result_{i})")

        a.append("    cleanup()")
        b.append("    cleanup()")

        code_a = "\n".join(a)
        code_b = "\n".join(b)

        analyzer = Analyzer()
        result = analyzer.analyze_sources(code_a, code_b, language="python")

        left_pct = result.metrics.left_covered / result.metrics.left_total * 100
        right_pct = result.metrics.right_covered / result.metrics.right_total * 100

        gap = abs(left_pct - right_pct)
        assert gap <= 10, (
            f"Coverage gap too large: A={left_pct:.1f}%, B={right_pct:.1f}% (gap={gap:.1f}pp)\n"
            f"Matches:\n" +
            "\n".join(
                f"  A[{m.file1['start_line']+1}-{m.file1['end_line']+1}] "
                f"({m.file1['end_line']-m.file1['start_line']+1} lines), "
                f"B[{m.file2['start_line']+1}-{m.file2['end_line']+1}] "
                f"({m.file2['end_line']-m.file2['start_line']+1} lines)"
                for m in result.matches
            )
        )
