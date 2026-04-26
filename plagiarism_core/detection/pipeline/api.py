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
    
    all_matches = _filter_contained_matches(all_matches)
    
    return all_matches


def _filter_contained_matches(matches: list) -> list:
    """Remove matches fully contained within larger matches (regardless of type)."""
    if not matches:
        return matches
    
    ranges = []
    for m in matches:
        ranges.append({
            'match': m,
            'a_start': m.file1["start_line"],
            'a_end': m.file1["end_line"],
            'b_start': m.file2["start_line"],
            'b_end': m.file2["end_line"],
            'size': (m.file1["end_line"] - m.file1["start_line"]) + (m.file2["end_line"] - m.file2["start_line"]),
        })
    
    ranges.sort(key=lambda x: -x['size'])
    
    filtered = []
    used_a = set()
    used_b = set()
    
    for r in ranges:
        a_range = set(range(r['a_start'], r['a_end'] + 1))
        b_range = set(range(r['b_start'], r['b_end'] + 1))
        
        if a_range.issubset(used_a) and b_range.issubset(used_b):
            continue
        
        filtered.append(r['match'])
        used_a.update(a_range)
        used_b.update(b_range)
    
    filtered.sort(key=lambda m: m.file1["start_line"])
    return filtered


def _run_phase3(
    all_matches, lines_a, lines_b, shadow_a, shadow_b, covered_a, covered_b, min_match_lines
):
    module_line_matches = _line_level_matches(lines_a, lines_b, shadow_a, shadow_b, min_match_lines)
    for m in module_line_matches:
        a_range = set(range(m.file1["start_line"], m.file1["end_line"] + 1))
        b_range = set(range(m.file2["start_line"], m.file2["end_line"] + 1))
        new_a = a_range - covered_a
        new_b = b_range - covered_b
        
        # Skip if match is fully contained in existing coverage (would create overlapping matches)
        if not new_a or not new_b:
            continue
            
        # Only add if new portion is meaningful (>50% of original or >2 lines)
        orig_size = len(a_range)
        new_size = len(new_a)
        if new_size >= orig_size * 0.5 or new_size >= 3:
            new_a_range = sorted(new_a)
            new_b_range = sorted(new_b)
            m.file1["start_line"] = new_a_range[0]
            m.file1["end_line"] = new_a_range[-1]
            m.file2["start_line"] = new_b_range[0]
            m.file2["end_line"] = new_b_range[-1]
            all_matches.append(m)
            covered_a.update(new_a)
            covered_b.update(new_b)
        # Otherwise, fully covered - no need to add


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
        min_match_lines=1,
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
