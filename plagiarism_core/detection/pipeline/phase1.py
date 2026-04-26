"""Phase 1: Function-level matching (1a-1d)."""

import logging

from ...canonicalizer import ast_canonicalize
from ...models import Match, PlagiarismType
from ...ast_hash import ast_minhash
from ..ast_helpers import _extract_functions
from ..body_signatures import _extract_body_signature
from ..function_matcher import _function_level_matches
from ..line_helpers import _line_hash
from ..line_matcher import _line_level_matches
from ..semantic_function_matcher import _semantic_function_matches
from ..semantic_line_matcher import _semantic_line_matches
from .helpers import _mark_covered

logger = logging.getLogger(__name__)

_LARGE_FUNCTION_THRESHOLD = 50
_LARGE_FUNCTION_OVERLAP_RATIO = 0.4
_MOSTLY_IDENTICAL_RATIO = 0.1
_MIN_CANONICAL_LENGTH = 50

_MINHASH_THRESHOLD = 0.75
_MINHASH_MIN_SIZE = 10


def run_phase1(
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
):
    all_matches = []
    funcs_a = _extract_functions(tree_a.root_node, bytes_a, lang_code)
    funcs_b = _extract_functions(tree_b.root_node, bytes_b, lang_code)
    func_matches = _function_level_matches(
        lines_a,
        lines_b,
        covered_a,
        covered_b,
        lang_code,
        tree_a=tree_a,
        bytes_a=bytes_a,
        tree_b=tree_b,
        bytes_b=bytes_b,
    )
    for fm in func_matches:
        _mark_covered(covered_a, fm)
        _mark_covered(covered_b, fm)
    all_matches.extend(func_matches)

    sem_func_matches = _semantic_function_matches(
        lines_a,
        lines_b,
        covered_a,
        covered_b,
        lang_code,
        tree_a=tree_a,
        bytes_a=bytes_a,
        tree_b=tree_b,
        bytes_b=bytes_b,
    )
    for fm in sem_func_matches:
        _mark_covered(covered_a, fm)
        _mark_covered(covered_b, fm)
    all_matches.extend(sem_func_matches)

    _match_by_name(
        funcs_a,
        funcs_b,
        lines_a,
        lines_b,
        shadow_a,
        shadow_b,
        covered_a,
        covered_b,
        lang_code,
        all_matches,
    )
    _match_by_body_signature(
        funcs_a,
        funcs_b,
        lines_a,
        lines_b,
        shadow_a,
        shadow_b,
        covered_a,
        covered_b,
        lang_code,
        all_matches,
    )
    _match_by_minhash(
        funcs_a,
        funcs_b,
        covered_a,
        covered_b,
        tree_a,
        tree_b,
        all_matches,
    )
    return all_matches


def _match_by_name(
    funcs_a,
    funcs_b,
    lines_a,
    lines_b,
    shadow_a,
    shadow_b,
    covered_a,
    covered_b,
    lang_code,
    all_matches,
):
    name_b_index = {}
    for j, fb in enumerate(funcs_b):
        func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
        if func_lines_b & covered_b:
            continue
        name_b_index.setdefault(fb["name"], []).append(j)

    for fa in funcs_a:
        func_lines_a = set(range(fa["start_line"], fa["end_line"] + 1))
        if func_lines_a & covered_a:
            continue
        candidates = name_b_index.get(fa["name"], [])
        for j in candidates:
            fb = funcs_b[j]
            func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
            if func_lines_b & covered_b:
                continue
            fn_lines_a = lines_a[fa["start_line"] : fa["end_line"] + 1]
            fn_lines_b = lines_b[fb["start_line"] : fb["end_line"] + 1]
            fn_shadow_a = shadow_a[fa["start_line"] : fa["end_line"] + 1]
            fn_shadow_b = shadow_b[fb["start_line"] : fb["end_line"] + 1]

            body_line_match = _line_level_matches(
                fn_lines_a, fn_lines_b, fn_shadow_a, fn_shadow_b, 3
            )
            body_sem_match = _semantic_line_matches(
                "\n".join(fn_lines_a),
                "\n".join(fn_lines_b),
                set(),
                set(),
                fn_lines_a,
                fn_lines_b,
                fn_shadow_a,
                fn_shadow_b,
                min_match_lines=3,
                lang_code=lang_code,
            )
            if body_line_match or body_sem_match:
                total_matched = 0
                for m in body_line_match:
                    total_matched += m.file1["end_line"] - m.file1["start_line"] + 1
                for m in body_sem_match:
                    total_matched += m.file1["end_line"] - m.file1["start_line"] + 1
                min_func_lines = min(len(fn_lines_a), len(fn_lines_b))
                if min_func_lines > _LARGE_FUNCTION_THRESHOLD:
                    if total_matched / min_func_lines < _LARGE_FUNCTION_OVERLAP_RATIO:
                        body_line_match = []
                        body_sem_match = []

            if not body_line_match and not body_sem_match:
                if not _check_body_similarity(fn_lines_a, fn_lines_b, lang_code):
                    continue

            prefix_len, suffix_len = _find_prefix_suffix(
                fn_lines_a, fn_lines_b, fn_shadow_a, fn_shadow_b
            )
            trim_a_start = fa["start_line"] + prefix_len
            trim_a_end = fa["end_line"] - suffix_len
            trim_b_start = fb["start_line"] + prefix_len
            trim_b_end = fb["end_line"] - suffix_len
            if trim_a_start > trim_a_end or trim_b_start > trim_b_end:
                continue

            differing_lines = _count_differing_lines(
                fn_lines_a, fn_lines_b, fn_shadow_a, fn_shadow_b, prefix_len, suffix_len
            )
            total_trimmed = min(len(fn_lines_a), len(fn_lines_b)) - prefix_len - suffix_len
            if total_trimmed > 0 and differing_lines / total_trimmed < _MOSTLY_IDENTICAL_RATIO:
                name_match = Match(
                    file1={
                        "start_line": fa["start_line"],
                        "start_col": 0,
                        "end_line": fa["end_line"],
                        "end_col": 0,
                    },
                    file2={
                        "start_line": fb["start_line"],
                        "start_col": 0,
                        "end_line": fb["end_line"],
                        "end_col": 0,
                    },
                    kgram_count=fa["end_line"] - fa["start_line"] + 1,
                    plagiarism_type=PlagiarismType.RENAMED,
                    similarity=1.0 - (differing_lines / total_trimmed),
                    details={
                        "original_function": fa["name"],
                        "matched_function": fb["name"],
                        "_mostly_identical": True,
                    },
                    description=f"Renamed function: {fa['name']} ↔ {fb['name']} (mostly identical)",
                )
                all_matches.append(name_match)
                name_b_index[fa["name"]].remove(j)
                break

            name_match = Match(
                file1={
                    "start_line": trim_a_start,
                    "start_col": 0,
                    "end_line": trim_a_end,
                    "end_col": 0,
                },
                file2={
                    "start_line": trim_b_start,
                    "start_col": 0,
                    "end_line": trim_b_end,
                    "end_col": 0,
                },
                kgram_count=trim_a_end - trim_a_start + 1,
                plagiarism_type=PlagiarismType.SEMANTIC,
                similarity=1.0,
                details={"original_function": fa["name"], "matched_function": fb["name"]},
                description=f"Semantic equivalent: {fa['name']} ↔ {fb['name']} (name-based)",
            )
            all_matches.append(name_match)
            for line in range(trim_a_start, trim_a_end + 1):
                covered_a.add(line)
            for line in range(trim_b_start, trim_b_end + 1):
                covered_b.add(line)
            name_b_index[fa["name"]].remove(j)
            break


def _match_by_body_signature(
    funcs_a,
    funcs_b,
    lines_a,
    lines_b,
    shadow_a,
    shadow_b,
    covered_a,
    covered_b,
    lang_code,
    all_matches,
):
    for fa in funcs_a:
        func_lines_a = set(range(fa["start_line"], fa["end_line"] + 1))
        if func_lines_a & covered_a:
            continue
        for _j, fb in enumerate(funcs_b):
            func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
            if func_lines_b & covered_b:
                continue
            size_a = fa["end_line"] - fa["start_line"] + 1
            size_b = fb["end_line"] - fb["start_line"] + 1
            if size_a < 3 or size_b < 3:
                continue
            if min(size_a, size_b) / max(size_a, size_b) < 0.5:
                continue
            fn_lines_a = lines_a[fa["start_line"] : fa["end_line"] + 1]
            fn_lines_b = lines_b[fb["start_line"] : fb["end_line"] + 1]
            fn_shadow_a = shadow_a[fa["start_line"] : fa["end_line"] + 1]
            fn_shadow_b = shadow_b[fb["start_line"] : fb["end_line"] + 1]
            try:
                sig_a = _extract_body_signature("\n".join(fn_lines_a), lang_code)
                sig_b = _extract_body_signature("\n".join(fn_lines_b), lang_code)
                if not (sig_a and sig_b and sig_a == sig_b):
                    continue
            except Exception:
                continue
            prefix_len, suffix_len = _find_prefix_suffix(
                fn_lines_a, fn_lines_b, fn_shadow_a, fn_shadow_b
            )
            trim_a_start = fa["start_line"] + prefix_len
            trim_a_end = fa["end_line"] - suffix_len
            trim_b_start = fb["start_line"] + prefix_len
            trim_b_end = fb["end_line"] - suffix_len
            if trim_a_start > trim_a_end or trim_b_start > trim_b_end:
                continue
            cross_match = Match(
                file1={
                    "start_line": trim_a_start,
                    "start_col": 0,
                    "end_line": trim_a_end,
                    "end_col": 0,
                },
                file2={
                    "start_line": trim_b_start,
                    "start_col": 0,
                    "end_line": trim_b_end,
                    "end_col": 0,
                },
                kgram_count=trim_a_end - trim_a_start + 1,
                plagiarism_type=PlagiarismType.SEMANTIC,
                similarity=1.0,
                details={"original_function": fa["name"], "matched_function": fb["name"]},
                description=f"Semantic equivalent (cross-name): {fa['name']} ↔ {fb['name']}",
            )
            all_matches.append(cross_match)
            for line in range(trim_a_start, trim_a_end + 1):
                covered_a.add(line)
            for line in range(trim_b_start, trim_b_end + 1):
                covered_b.add(line)
            break


def _check_body_similarity(fn_lines_a, fn_lines_b, lang_code):
    body_src_a = "\n".join(fn_lines_a)
    body_src_b = "\n".join(fn_lines_b)
    try:
        sig_a = _extract_body_signature(body_src_a, lang_code)
        sig_b = _extract_body_signature(body_src_b, lang_code)
        if sig_a and sig_b and sig_a == sig_b:
            return True
        body_canon_a = ast_canonicalize(body_src_a, lang_code)
        body_canon_b = ast_canonicalize(body_src_b, lang_code)
        if body_canon_a != body_canon_b:
            return False
        return len(body_canon_a) >= _MIN_CANONICAL_LENGTH
    except Exception:
        return False


def _find_prefix_suffix(fn_lines_a, fn_lines_b, fn_shadow_a, fn_shadow_b):
    min_body = min(len(fn_lines_a), len(fn_lines_b))
    prefix_len = 0
    while prefix_len < min_body:
        sa = (fn_shadow_a[prefix_len] or "").strip()
        sb = (fn_shadow_b[prefix_len] or "").strip()
        exact_a = (fn_lines_a[prefix_len] or "").strip()
        exact_b = (fn_lines_b[prefix_len] or "").strip()
        shadow_match = sa and sb and _line_hash(sa) == _line_hash(sb)
        exact_match = exact_a == exact_b and bool(exact_a)
        if shadow_match or exact_match:
            prefix_len += 1
        else:
            break
    suffix_len = 0
    while suffix_len < min_body - prefix_len:
        ia = len(fn_lines_a) - 1 - suffix_len
        ib = len(fn_lines_b) - 1 - suffix_len
        sa = (fn_shadow_a[ia] or "").strip()
        sb = (fn_shadow_b[ib] or "").strip()
        exact_a = (fn_lines_a[ia] or "").strip()
        exact_b = (fn_lines_b[ib] or "").strip()
        shadow_match = sa and sb and _line_hash(sa) == _line_hash(sb)
        exact_match = exact_a == exact_b and bool(exact_a)
        if shadow_match or exact_match:
            suffix_len += 1
        else:
            break
    return prefix_len, suffix_len


def _match_by_minhash(
    funcs_a,
    funcs_b,
    covered_a,
    covered_b,
    tree_a,
    tree_b,
    all_matches,
):
    """
    Match functions using MinHash similarity for partial matches.
    
    This catches functions that are structurally similar but not identical
    (e.g., a few lines added/removed or modified). It's the "fallback"
    layer after exact structural/semantic matching.
    """
    from ...fingerprinting.minhash import MinHash
    
    minhash_sigs_a = {}
    for fa in funcs_a:
        func_lines = set(range(fa["start_line"], fa["end_line"] + 1))
        if func_lines & covered_a:
            continue
        if fa["end_line"] - fa["start_line"] < _MINHASH_MIN_SIZE:
            continue
        try:
            func_node = _find_function_node(tree_a.root_node, fa["start_line"], fa["end_line"])
            if func_node:
                minhash_sigs_a[fa["name"]] = ast_minhash(func_node)
        except Exception:
            continue
    
    minhash_sigs_b = {}
    for fb in funcs_b:
        func_lines = set(range(fb["start_line"], fb["end_line"] + 1))
        if func_lines & covered_b:
            continue
        if fb["end_line"] - fb["start_line"] < _MINHASH_MIN_SIZE:
            continue
        try:
            func_node = _find_function_node(tree_b.root_node, fb["start_line"], fb["end_line"])
            if func_node:
                minhash_sigs_b[fb["name"]] = ast_minhash(func_node)
        except Exception:
            continue
    
    matched_pairs = set()
    for name_a, sig_a in minhash_sigs_a.items():
        if name_a in matched_pairs:
            continue
        for name_b, sig_b in minhash_sigs_b.items():
            if name_b in matched_pairs:
                continue
            sim = MinHash.jaccard(sig_a, sig_b)
            if sim >= _MINHASH_THRESHOLD:
                fa = next(f for f in funcs_a if f["name"] == name_a)
                fb = next(f for f in funcs_b if f["name"] == name_b)
                
                partial_match = Match(
                    file1={
                        "start_line": fa["start_line"],
                        "start_col": 0,
                        "end_line": fa["end_line"],
                        "end_col": 0,
                    },
                    file2={
                        "start_line": fb["start_line"],
                        "start_col": 0,
                        "end_line": fb["end_line"],
                        "end_col": 0,
                    },
                    kgram_count=fa["end_line"] - fa["start_line"] + 1,
                    plagiarism_type=PlagiarismType.SEMANTIC,
                    similarity=sim,
                    details={
                        "original_function": fa["name"],
                        "matched_function": fb["name"],
                        "_minhash_match": True,
                    },
                    description=f"Partial match (MinHash): {fa['name']} ↔ {fb['name']} (similarity: {sim:.2f})",
                )
                all_matches.append(partial_match)
                matched_pairs.add(name_a)
                matched_pairs.add(name_b)
                for line in range(fa["start_line"], fa["end_line"] + 1):
                    covered_a.add(line)
                for line in range(fb["start_line"], fb["end_line"] + 1):
                    covered_b.add(line)
                break


def _find_function_node(root, start_line, end_line):
    """Find function node within the given line range."""
    
    def visit(node):
        if node.type in ("function_definition", "method_definition", "function_declaration"):
            if node.start_point[0] <= start_line <= node.end_point[0]:
                return node
        for child in node.children:
            result = visit(child)
            if result:
                return result
        return None
    
    return visit(root)


def _count_differing_lines(
    fn_lines_a, fn_lines_b, fn_shadow_a, fn_shadow_b, prefix_len, suffix_len
):
    differing = 0
    for k in range(prefix_len, min(len(fn_lines_a), len(fn_lines_b)) - suffix_len):
        exact_a = (fn_lines_a[k] or "").strip()
        exact_b = (fn_lines_b[k] or "").strip()
        sa = (fn_shadow_a[k] or "").strip()
        sb = (fn_shadow_b[k] or "").strip()
        if exact_a != exact_b and not (sa and sb and _line_hash(sa) == _line_hash(sb)):
            differing += 1
    return differing
