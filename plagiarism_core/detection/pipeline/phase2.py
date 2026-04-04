"""Phase 2: Line matching within matched function pairs."""

from ..line_matcher import _line_level_matches
from ..semantic_line_matcher import _semantic_line_matches
from .helpers import _mark_covered


def run_phase2(
    all_matches,
    lines_a,
    lines_b,
    shadow_a,
    shadow_b,
    covered_a,
    covered_b,
    min_match_lines,
    lang_code,
):
    for fm in all_matches[:]:
        a_start, a_end = fm.file1["start_line"], fm.file1["end_line"]
        b_start, b_end = fm.file2["start_line"], fm.file2["end_line"]
        fn_lines_a = lines_a[a_start : a_end + 1]
        fn_lines_b = lines_b[b_start : b_end + 1]
        fn_shadow_a = shadow_a[a_start : a_end + 1]
        fn_shadow_b = shadow_b[b_start : b_end + 1]

        fn_line_matches = _line_level_matches(
            fn_lines_a,
            fn_lines_b,
            fn_shadow_a,
            fn_shadow_b,
            min_match_lines,
        )
        for m in fn_line_matches:
            m.file1["start_line"] += a_start
            m.file1["end_line"] += a_start
            m.file2["start_line"] += b_start
            m.file2["end_line"] += b_start
            _mark_covered(covered_a, m)
            _mark_covered(covered_b, m)

        local_used_a = set(range(len(fn_lines_a)))
        local_used_b = set(range(len(fn_lines_b)))
        for m in fn_line_matches:
            for line in range(m.file1["start_line"] - a_start, m.file1["end_line"] - a_start + 1):
                local_used_a.discard(line)
            for line in range(m.file2["start_line"] - b_start, m.file2["end_line"] - b_start + 1):
                local_used_b.discard(line)

        fn_sem_matches = _semantic_line_matches(
            "\n".join(fn_lines_a),
            "\n".join(fn_lines_b),
            local_used_a,
            local_used_b,
            fn_lines_a,
            fn_lines_b,
            fn_shadow_a,
            fn_shadow_b,
            min_match_lines=1,
            lang_code=lang_code,
        )
        for m in fn_sem_matches:
            m.file1["start_line"] += a_start
            m.file1["end_line"] += a_start
            m.file2["start_line"] += b_start
            m.file2["end_line"] += b_start
            _mark_covered(covered_a, m)
            _mark_covered(covered_b, m)

        all_matches.extend(fn_line_matches)
        all_matches.extend(fn_sem_matches)

        _maybe_remove_function_match(
            all_matches, fm, fn_line_matches, fn_sem_matches, a_start, a_end, b_start, b_end
        )


def _maybe_remove_function_match(
    all_matches, fm, fn_line_matches, fn_sem_matches, a_start, a_end, b_start, b_end
):
    fm_a_range = set(range(a_start, a_end + 1))
    fm_b_range = set(range(b_start, b_end + 1))
    covered_by_sub_a = set()
    covered_by_sub_b = set()
    for m in fn_line_matches:
        for line in range(m.file1["start_line"], m.file1["end_line"] + 1):
            covered_by_sub_a.add(line)
        for line in range(m.file2["start_line"], m.file2["end_line"] + 1):
            covered_by_sub_b.add(line)
    for m in fn_sem_matches:
        for line in range(m.file1["start_line"], m.file1["end_line"] + 1):
            covered_by_sub_a.add(line)
        for line in range(m.file2["start_line"], m.file2["end_line"] + 1):
            covered_by_sub_b.add(line)
    is_mostly_identical = fm.details.get("_mostly_identical", False) if fm.details else False
    if is_mostly_identical:
        coverage_a = len(covered_by_sub_a) / len(fm_a_range) if fm_a_range else 0
        coverage_b = len(covered_by_sub_b) / len(fm_b_range) if fm_b_range else 0
        if coverage_a >= 0.9 and coverage_b >= 0.9:
            all_matches.remove(fm)
    elif covered_by_sub_a == fm_a_range and covered_by_sub_b == fm_b_range:
        all_matches.remove(fm)
