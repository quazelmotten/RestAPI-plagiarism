"""Type classification via normalization-level analysis."""

import re
from dataclasses import dataclass, field
from collections import Counter
from typing import List

from .models import PlagiarismType
from .detection.line_helpers import _make_shadow_lines, _make_exact_lines, _line_hash


def _lcs_len(seq1: List, seq2: List) -> int:
    n, m = len(seq1), len(seq2)
    if n == 0 or m == 0:
        return 0
    if n > m:
        seq1, seq2 = seq2, seq1
        n, m = m, n
    prev = [0] * (n + 1)
    for item in seq2:
        curr = [0] * (n + 1)
        for i in range(n):
            if item == seq1[i]:
                curr[i + 1] = prev[i] + 1
            else:
                curr[i + 1] = max(prev[i + 1], curr[i])
        prev = curr
    return prev[n]


def _jaccard_on_counter(cnt_a: Counter, cnt_b: Counter) -> float:
    inter = sum(min(cnt_a.get(k, 0), cnt_b.get(k, 0)) for k in cnt_a)
    union = sum(max(cnt_a.get(k, 0), cnt_b.get(k, 0)) for k in set(cnt_a) | set(cnt_b))
    return inter / union if union else 0.0


def _lcs_ratio(seq_a: List, seq_b: List) -> float:
    lcs = _lcs_len(seq_a, seq_b)
    min_len = min(len(seq_a), len(seq_b))
    return lcs / min_len if min_len else 0.0


@dataclass
class SimilaritySignals:
    """All similarity signals computed from a source code pair."""
    raw_jaccard: float = 0.0
    clean_jaccard: float = 0.0
    shadow_jaccard: float = 0.0
    shadow_lcs_ratio: float = 0.0
    func_struct_multiset_jaccard: float = 0.0
    func_order_ratio: float = 0.0
    canonical_equiv: bool = False
    canonical_jaccard: float = 0.0
    raw_equal: bool = False
    normalized_equal: bool = False


# Pattern for stub function detection (language-agnostic via tree-sitter)
_STUB_PATTERN = re.compile(
    r'(?:def\s+\w+\s*\([^)]*\)\s*:\s*(?:\s*\.\.\.\s*|\s*pass\s*|\s*"""[^"]*"""\s*|\s*\'\'\'[^\']*\'\'\'\s*|\s*$))'
    r'|(?:^\s*print\(["\']debug["\']\))'
)


def _filter_noise(source: str, lang: str = "python") -> str:
    """Remove noise patterns (stub functions, debug prints) from source code."""
    lines = source.splitlines()
    filtered = []
    skip_next = 0
    for i, line in enumerate(lines):
        if skip_next > 0:
            skip_next -= 1
            continue
        stripped = line.strip()
        # Skip blank lines
        if not stripped:
            continue
        # Skip debug print("debug") lines
        if stripped == 'print("debug")' or stripped == "print('debug')":
            continue
        # Detect and skip stub function headers
        if _STUB_PATTERN.match(line):
            # If it's a stub def, skip it and its body lines
            indent = len(line) - len(line.lstrip())
            j = i + 1
            while j < len(lines) and lines[j].startswith(" " * (indent + 1)):
                j += 1
            continue
        # Remove trailing whitespace for normalization
        filtered.append(line.rstrip())
    return "\n".join(filtered)


def compute_signals(
    source_a: str,
    source_b: str,
    lang: str = "python",
    filter_noise: bool = True,
) -> SimilaritySignals:
    """Compute all similarity signals between two source strings."""
    s = SimilaritySignals()

    # Apply noise filtering when requested (removes stubs, debug prints)
    if filter_noise and lang == "python":
        source_a_clean = _filter_noise(source_a, lang)
        source_b_clean = _filter_noise(source_b, lang)
    else:
        source_a_clean = source_a
        source_b_clean = source_b

    s.raw_equal = source_a == source_b and bool(source_a.strip())

    # L0: raw line multiset Jaccard (using noise-filtered source)
    lines_a = source_a_clean.splitlines()
    lines_b = source_b_clean.splitlines()
    if lines_a and lines_b:
        cnt_a = Counter(lines_a)
        cnt_b = Counter(lines_b)
        s.raw_jaccard = _jaccard_on_counter(cnt_a, cnt_b)

    # L1: clean line multiset Jaccard (whitespace + comments stripped, noise filtered)
    exact_a = _make_exact_lines(source_a_clean, lang)
    exact_b = _make_exact_lines(source_b_clean, lang)
    s.normalized_equal = exact_a == exact_b
    if exact_a and exact_b:
        cnt_a = Counter(exact_a)
        cnt_b = Counter(exact_b)
        s.clean_jaccard = _jaccard_on_counter(cnt_a, cnt_b)

    # L2: shadow line multiset Jaccard (identifier-normalized, noise filtered)
    shadow_a = _make_shadow_lines(source_a_clean, lang)
    shadow_b = _make_shadow_lines(source_b_clean, lang)
    if shadow_a and shadow_b:
        cnt_a = Counter(shadow_a)
        cnt_b = Counter(shadow_b)
        s.shadow_jaccard = _jaccard_on_counter(cnt_a, cnt_b)
        s.shadow_lcs_ratio = _lcs_ratio(shadow_a, shadow_b)

    # L4: full-file canonical equivalence (uses v2 with rewrite rules)
    try:
        from .normalizer import canonicalize_type4_v2
        can_a = canonicalize_type4_v2(source_a, lang_code=lang)
        can_b = canonicalize_type4_v2(source_b, lang_code=lang)
        s.canonical_equiv = can_a.strip() == can_b.strip() and bool(can_a.strip())
    except Exception:
        s.canonical_equiv = False

    # L3: function-level structural hash multiset Jaccard
    try:
        from .fingerprinting.parser import parse_string_once
        from .detection.ast_helpers import _extract_functions
        tree_a, bytes_a = parse_string_once(source_a, lang)
        tree_b, bytes_b = parse_string_once(source_b, lang)
        funcs_a = _extract_functions(tree_a.root_node, bytes_a, lang)
        funcs_b = _extract_functions(tree_b.root_node, bytes_b, lang)
        if funcs_a and funcs_b:
            hashes_a = [f.get("struct_hash", 0) for f in funcs_a]
            hashes_b = [f.get("struct_hash", 0) for f in funcs_b]
            cnt_a = Counter(hashes_a)
            cnt_b = Counter(hashes_b)
            s.func_struct_multiset_jaccard = _jaccard_on_counter(cnt_a, cnt_b)
            s.func_order_ratio = _lcs_ratio(hashes_a, hashes_b)
    except Exception:
        pass

    # L4: function-level semantic hash Jaccard
    try:
        if funcs_a and funcs_b:
            sem_a = [f.get("semantic_hash", 0) for f in funcs_a]
            sem_b = [f.get("semantic_hash", 0) for f in funcs_b]
            cnt_a = Counter(sem_a)
            cnt_b = Counter(sem_b)
            s.canonical_jaccard = _jaccard_on_counter(cnt_a, cnt_b)
    except Exception:
        pass

    return s


def classify_type(signals: SimilaritySignals) -> PlagiarismType:
    """Classify plagiarism type from similarity signals.

    The type is determined by the HARDEST normalization level needed
    for a match, checking hardest (L4) first. This matches the
    ground truth convention where Type 4 > Type 3 > Type 2 > Type 1.
    """
    # L4: semantically equivalent → Type 4
    # Guard: only if NOT already very similar at shadow level
    # (otherwise the canonical equivalence is just an artifact of
    #  the same renamed code having identical AST structure)
    if signals.canonical_equiv and not signals.raw_equal and signals.shadow_jaccard < 0.85 and signals.clean_jaccard < 0.95:
        return PlagiarismType.SEMANTIC

    # L3: content matches as multiset but order differs → REORDERED
    if signals.clean_jaccard >= 0.55 and signals.shadow_lcs_ratio < 0.95:
        return PlagiarismType.REORDERED

    # L1: comment/whitespace normalized match → EXACT
    # Check before L2 so exact copies (shadow_jaccard≈1.0) aren't
    # misclassified as RENAMED.
    if signals.clean_jaccard >= 0.95 or signals.raw_equal:
        return PlagiarismType.EXACT

    # L2: content matches after identifier normalization → RENAMED
    if signals.shadow_jaccard >= 0.85:
        return PlagiarismType.RENAMED

    return PlagiarismType.NONE


def classify_signals_raw(
    clean_jaccard: float = 0.0,
    shadow_jaccard: float = 0.0,
    shadow_lcs_ratio: float = 1.0,
    canonical_equiv: bool = False,
    raw_equal: bool = False,
) -> PlagiarismType:
    """Classify type from raw signal values.

    Order matters – we check hardest normalization level first (L4→L1)
    but must avoid the REORDERED condition catching EXACT/RENAMED pairs
    and the EXACT condition catching RENAMED pairs.

    Guard rules:
      - EXACT must come before RENAMED (exact copies have shadow_jaccard≈1.0)
      - REORDERED requires shadow_lcs_ratio < 0.95 (EXACT/RENAMED have ≈1.0)
      - SEMANTIC requires shadow_jaccard < 0.85 (otherwise it's Type 2
        that happens to have canonical equivalence)
    """
    # L4: semantically equivalent, not raw-equal, AND not Type-2-like
    if canonical_equiv and not raw_equal and shadow_jaccard < 0.85 and clean_jaccard < 0.95:
        return PlagiarismType.SEMANTIC

    # L3: content matches as multiset but order differs
    if clean_jaccard >= 0.55 and shadow_lcs_ratio < 0.95:
        return PlagiarismType.REORDERED

    # L1: comment/whitespace-normalized match (check before L2 shadow_jaccard)
    if clean_jaccard >= 0.95 or raw_equal:
        return PlagiarismType.EXACT

    # L2: identifier-normalized match
    if shadow_jaccard >= 0.85:
        return PlagiarismType.RENAMED

    return PlagiarismType.NONE
