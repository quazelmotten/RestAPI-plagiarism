"""Semantic line matching."""

from ..canonicalizer import canonicalize_type4
from ..models import Match, PlagiarismType
from .line_helpers import _line_hash, _strip_comments


def _semantic_line_matches(
    source_a: str,
    source_b: str,
    used_lines_a: set[int],
    used_lines_b: set[int],
    lines_a: list[str],
    lines_b: list[str],
    shadow_a: list[str],
    shadow_b: list[str],
    min_match_lines: int = 2,
    lang_code: str = "python",
    func_matches: list[Match] | None = None,
) -> list[Match]:
    """
    For unmatched lines, apply Type 4 canonicalization and re-match.

    Only classifies lines as SEMANTIC if they:
      1. Don't match in original form (not EXACT)
      2. Don't match in shadow form (not RENAMED)
      3. Do match after Type 4 canonicalization (SEMANTIC)

    Step 4: Shadow exclusion is scoped to function pairs when function
    matches are available, preventing a line in one function from being
    excluded because its shadow appears in a completely different function.
    """
    # Step 4: Build scope-local shadow exclusion sets
    # For lines inside matched functions, only exclude shadows within
    # the matched function's partner (not globally).
    # For lines outside matched functions, fall back to global exclusion.
    global_shadow_b_hashes: set[int] = set()
    global_shadow_a_hashes: set[int] = set()
    for s in shadow_b:
        h = _line_hash(s.strip()) if s else 0
        if h:
            global_shadow_b_hashes.add(h)
    for s in shadow_a:
        h = _line_hash(s.strip()) if s else 0
        if h:
            global_shadow_a_hashes.add(h)

    # Build per-function shadow hash maps: line_index -> partner shadow hashes
    line_a_scoped_b: dict[int, set[int]] = {}
    line_b_scoped_a: dict[int, set[int]] = {}
    if func_matches:
        for fm in func_matches:
            a_start, a_end = fm.file1["start_line"], fm.file1["end_line"]
            b_start, b_end = fm.file2["start_line"], fm.file2["end_line"]
            # Partner B hashes for each line in A's function
            b_hashes = set()
            for j in range(b_start, min(b_end + 1, len(shadow_b))):
                h = _line_hash(shadow_b[j].strip()) if j < len(shadow_b) and shadow_b[j] else 0
                if h:
                    b_hashes.add(h)
            for i in range(a_start, min(a_end + 1, len(shadow_a))):
                line_a_scoped_b[i] = b_hashes
            # Partner A hashes for each line in B's function
            a_hashes = set()
            for i in range(a_start, min(a_end + 1, len(shadow_a))):
                h = _line_hash(shadow_a[i].strip()) if i < len(shadow_a) and shadow_a[i] else 0
                if h:
                    a_hashes.add(h)
            for j in range(b_start, min(b_end + 1, len(shadow_b))):
                line_b_scoped_a[j] = a_hashes

    def _get_exclusion_b(line_idx: int) -> set[int]:
        """Get shadow exclusion set for a line in file A."""
        if line_idx in line_a_scoped_b:
            return line_a_scoped_b[line_idx]
        return global_shadow_b_hashes

    def _get_exclusion_a(line_idx: int) -> set[int]:
        """Get shadow exclusion set for a line in file B."""
        if line_idx in line_b_scoped_a:
            return line_b_scoped_a[line_idx]
        return global_shadow_a_hashes

    # Canonicalize all unmatched lines.
    # Skip lines that match in shadow form (scope-local) — those are RENAMED, not SEMANTIC
    canon_a_lines = []
    canon_b_lines = []
    for i, line in enumerate(lines_a):
        if i in used_lines_a or not line.strip():
            canon_a_lines.append("")
        else:
            clean_line = _strip_comments(line, lang_code)
            if not clean_line:
                canon_a_lines.append("")
                continue
            # Step 4: Use scope-local shadow exclusion
            if i < len(shadow_a):
                shadow_h = _line_hash(shadow_a[i].strip())
                if shadow_h and shadow_h in _get_exclusion_b(i):
                    canon_a_lines.append("")
                    continue
            canon = canonicalize_type4(clean_line, lang_code=lang_code)
            canon_a_lines.append(canon.strip())
    for j, line in enumerate(lines_b):
        if j in used_lines_b or not line.strip():
            canon_b_lines.append("")
        else:
            clean_line = _strip_comments(line, lang_code)
            if not clean_line:
                canon_b_lines.append("")
                continue
            # Step 4: Use scope-local shadow exclusion
            if j < len(shadow_b):
                shadow_h = _line_hash(shadow_b[j].strip())
                if shadow_h and shadow_h in _get_exclusion_a(j):
                    canon_b_lines.append("")
                    continue
            canon = canonicalize_type4(clean_line, lang_code=lang_code)
            canon_b_lines.append(canon.strip())

    # Build hash index for B's canonicalized lines
    canon_b_index: dict[int, list[int]] = {}
    for j, c in enumerate(canon_b_lines):
        if c:
            canon_b_index.setdefault(_line_hash(c), []).append(j)

    # Find matching canonicalized line pairs
    pair_map: dict[int, list[int]] = {}
    for i, c in enumerate(canon_a_lines):
        if not c:
            continue
        h = _line_hash(c)
        if h in canon_b_index:
            pair_map[i] = canon_b_index[h]

    # Precompute canonical line hashes to avoid recomputation in tight loop
    canon_a_hashes = [_line_hash(c) for c in canon_a_lines]
    canon_b_hashes = [_line_hash(c) for c in canon_b_lines]

    # Extend to contiguous regions of lines that match ONLY after canonicalization.
    # Match by canonical form even when shadows differ (e.g., += vs =...+).
    raw: list[tuple[int, int, int]] = []
    visited: set[int] = set()

    # Common boilerplate canonical patterns that should be rejected
    # These appear in nearly every C/C++/Java/JS competitive programming file
    _common_boilerplate_hashes: set[int] = set()
    _boilerplate_patterns = [
        "int n;",
        "int t;",
        "int m;",
        "int i;",
        "int j;",
        "int k;",
        "return 0;",
        "return 0",
        "using namespace std;",
        # Canonicalized forms (after _canonicalize_type4_light)
        "cin in n;",
        "cin in t;",
        "cin in m;",
        "cin in n",
        "cin in t",
        "cin in m",
        "cin IN n;",
        "cin IN t;",
        "cin IN m;",
        "cin IN n",
        "cin IN t",
        "cin IN m",
        "cin >> n;",
        "cin >> t;",
        "cin >> m;",
        "loop(",
        "loop (",
        "for (int i = 0; i < n; i++)",
        "for (int i=0; i<n; i++)",
        "loop (int i = 0; i < n; i++)",
    ]
    for bp in _boilerplate_patterns:
        _common_boilerplate_hashes.add(_line_hash(bp))
        _common_boilerplate_hashes.add(_line_hash(bp.lower()))
        _common_boilerplate_hashes.add(_line_hash(bp.upper()))

    for start_a in sorted(pair_map.keys()):
        if start_a in visited:
            continue
        for start_b in pair_map[start_a]:
            length = 0
            ia, ib = start_a, start_b
            while (
                ia < len(canon_a_lines)
                and ib < len(canon_b_lines)
                and canon_a_hashes[ia]
                and canon_b_hashes[ib]
                and canon_a_hashes[ia] == canon_b_hashes[ib]
            ):
                length += 1
                visited.add(ia)
                ia += 1
                ib += 1
            if length >= min_match_lines:
                # Reject if all matched lines are common boilerplate
                all_boilerplate = True
                for offset in range(length):
                    h = canon_a_hashes[start_a + offset]
                    if h not in _common_boilerplate_hashes:
                        all_boilerplate = False
                        break
                if all_boilerplate:
                    continue
                raw.append((start_a, start_b, length))

    # Greedy longest-first selection
    raw.sort(key=lambda x: -x[2])
    used_a: set[int] = set()
    used_b: set[int] = set()
    matches: list[Match] = []

    for sa, sb, length in raw:
        ra = set(range(sa, sa + length))
        rb = set(range(sb, sb + length))
        if ra & used_a or rb & used_b:
            while (sa in used_a or sb in used_b) and length > 0:
                sa += 1
                sb += 1
                length -= 1
            while ((sa + length - 1) in used_a or (sb + length - 1) in used_b) and length > 0:
                length -= 1
            if length < min_match_lines:
                continue

        # Build transformation description
        transforms = []
        for offset in range(length):
            ia, ib = sa + offset, sb + offset
            if ia < len(lines_a) and ib < len(lines_b):
                if lines_a[ia].strip() != lines_b[ib].strip():
                    transforms.append(
                        {
                            "line_a": ia + 1,
                            "line_b": ib + 1,
                            "original": lines_a[ia].strip()[:80],
                            "canonical": lines_b[ib].strip()[:80],
                        }
                    )

        desc = None
        if transforms:
            # Summarize the transformation types
            descs = []
            for t in transforms:
                if "for " in t["original"] and "map(" in t["canonical"]:
                    descs.append("list comprehension → map")
                elif "+=" in t["original"] or "+=" in t["canonical"]:
                    descs.append("augmented assignment")
                elif "lambda" in t["original"] or "lambda" in t["canonical"]:
                    descs.append("lambda ↔ def")
                else:
                    descs.append("semantic rewrite")
            desc = ", ".join(set(descs))

        matches.append(
            Match(
                file1={"start_line": sa, "start_col": 0, "end_line": sa + length - 1, "end_col": 0},
                file2={"start_line": sb, "start_col": 0, "end_line": sb + length - 1, "end_col": 0},
                kgram_count=length,
                plagiarism_type=PlagiarismType.SEMANTIC,
                similarity=1.0,
                details={"transformations": transforms} if transforms else None,
                description=desc,
            )
        )
        used_a.update(range(sa, sa + length))
        used_b.update(range(sb, sb + length))

    matches.sort(key=lambda m: m.file1["start_line"])
    return matches
