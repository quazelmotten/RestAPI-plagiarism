"""detect_plagiarism orchestrator."""

import logging

from ..line_matcher import _line_level_matches
from ..merge_helpers import _merge_matches
from ..semantic_line_matcher import _semantic_line_matches
from .phase1 import run_phase1
from .phase2 import run_phase2
from .prep import prepare_sources

logger = logging.getLogger(__name__)


def detect_plagiarism(source_a, source_b, lang_code="python", min_match_lines=2):
    lines_a, lines_b, tree_a, bytes_a, tree_b, bytes_b, shadow_a, shadow_b = prepare_sources(
        source_a, source_b, lang_code
    )

    all_matches = []
    covered_a = set()
    covered_b = set()

    if tree_a and tree_b:
        all_matches = run_phase1(
            lines_a,
            lines_b,
            shadow_a,
            shadow_b,
            covered_a,
            covered_b,
            lang_code,
            tree_a,
            bytes_a,
            tree_b,
            bytes_b,
        )
        run_phase2(
            all_matches,
            lines_a,
            lines_b,
            shadow_a,
            shadow_b,
            covered_a,
            covered_b,
            min_match_lines,
            lang_code,
        )

    _run_phase3(
        all_matches, lines_a, lines_b, shadow_a, shadow_b, covered_a, covered_b, min_match_lines
    )
    _run_phase4(
        all_matches,
        source_a,
        source_b,
        covered_a,
        covered_b,
        lines_a,
        lines_b,
        shadow_a,
        shadow_b,
        min_match_lines,
        lang_code,
    )

    all_matches = _merge_matches(all_matches, gap=0)
    all_matches.sort(key=lambda m: m.file1["start_line"])
    return all_matches


def _run_phase3(
    all_matches, lines_a, lines_b, shadow_a, shadow_b, covered_a, covered_b, min_match_lines
):
    module_line_matches = _line_level_matches(lines_a, lines_b, shadow_a, shadow_b, min_match_lines)
    for m in module_line_matches:
        a_range = set(range(m.file1["start_line"], m.file1["end_line"] + 1))
        b_range = set(range(m.file2["start_line"], m.file2["end_line"] + 1))
        if not (a_range & covered_a) and not (b_range & covered_b):
            all_matches.append(m)
            covered_a.update(a_range)
            covered_b.update(b_range)


def _run_phase4(
    all_matches,
    source_a,
    source_b,
    covered_a,
    covered_b,
    lines_a,
    lines_b,
    shadow_a,
    shadow_b,
    min_match_lines,
    lang_code,
):
    sem_line_matches = _semantic_line_matches(
        source_a,
        source_b,
        covered_a,
        covered_b,
        lines_a,
        lines_b,
        shadow_a,
        shadow_b,
        min_match_lines=2,
        lang_code=lang_code,
        func_matches=all_matches,
    )
    all_matches.extend(sem_line_matches)


def detect_plagiarism_from_files(file_a, file_b, lang_code="python", min_match_lines=2):
    with open(file_a, encoding="utf-8", errors="ignore") as f:
        source_a = f.read()
    with open(file_b, encoding="utf-8", errors="ignore") as f:
        source_b = f.read()
    return detect_plagiarism(source_a, source_b, lang_code, min_match_lines)
