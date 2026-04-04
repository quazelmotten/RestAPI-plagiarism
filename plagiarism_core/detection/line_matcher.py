"""Exact + shadow line matching."""

from ..models import Match, PlagiarismType
from .line_helpers import _line_hash


def _line_level_matches(
    lines_a: list[str],
    lines_b: list[str],
    shadow_a: list[str],
    shadow_b: list[str],
    min_match_lines: int = 2,
) -> list[Match]:
    """
    Match lines at two levels simultaneously.

    For each matching shadow-line region:
      - If the original lines also match → Type 1
      - If only the shadows match       → Type 2 (with rename info)
    """
    # Build hash → line-indices index for shadow B
    shadow_b_index: dict[int, list[int]] = {}
    for j, s in enumerate(shadow_b):
        if s:
            shadow_b_index.setdefault(_line_hash(s), []).append(j)

    # Build hash of exact lines for A
    exact_a_hashes = [_line_hash(ln) for ln in lines_a]
    exact_b_hashes = [_line_hash(ln) for ln in lines_b]

    # Find all A→B shadow-matching line pairs
    pair_map: dict[int, list[int]] = {}
    for i, s in enumerate(shadow_a):
        if not s:
            continue
        h = _line_hash(s)
        if h in shadow_b_index:
            pair_map[i] = shadow_b_index[h]

    # Precompute shadow hashes to avoid recomputation in tight loop
    shadow_a_hashes = [_line_hash(s) for s in shadow_a]
    shadow_b_hashes = [_line_hash(s) for s in shadow_b]

    # Extend matches to contiguous regions.
    # When a line in A matches multiple lines in B, prefer the B candidate
    # that produces the longest contiguous match (avoids greedy short-match
    # selection that blocks longer downstream matches).
    raw: list[tuple[int, int, int]] = []  # (start_a, start_b, length)
    visited: set[int] = set()

    for start_a in sorted(pair_map.keys()):
        if start_a in visited:
            continue
        candidates = pair_map[start_a]
        # Try all candidates, keep the one with the longest extension
        best_b, best_len = candidates[0], 0
        for start_b in candidates:
            length = 0
            ia, ib = start_a, start_b
            while (
                ia < len(shadow_a)
                and ib < len(shadow_b)
                and shadow_a_hashes[ia]
                and shadow_b_hashes[ib]
                and shadow_a_hashes[ia] == shadow_b_hashes[ib]
            ):
                length += 1
                ia += 1
                ib += 1
            if length > best_len:
                best_b, best_len = start_b, length

        # Record the best match and mark visited
        if best_len >= min_match_lines:
            for offset in range(best_len):
                visited.add(start_a + offset)
            raw.append((start_a, best_b, best_len))

    # Greedy longest-first, non-overlapping selection
    raw.sort(key=lambda x: -x[2])
    used_a: set[int] = set()
    used_b: set[int] = set()
    matches: list[Match] = []

    for sa, sb, length in raw:
        ra = set(range(sa, sa + length))
        rb = set(range(sb, sb + length))
        if ra & used_a or rb & used_b:
            # Trim overlapping edges
            while (sa in used_a or sb in used_b) and length > 0:
                sa += 1
                sb += 1
                length -= 1
            while ((sa + length - 1) in used_a or (sb + length - 1) in used_b) and length > 0:
                length -= 1
            if length < min_match_lines:
                continue

        # Classify each line in the region
        line_details = []
        all_exact = True
        for offset in range(length):
            ia, ib = sa + offset, sb + offset
            if ia < len(exact_a_hashes) and ib < len(exact_b_hashes):
                is_exact = exact_a_hashes[ia] != 0 and exact_a_hashes[ia] == exact_b_hashes[ib]
            else:
                is_exact = False
            if not is_exact:
                all_exact = False
            line_details.append(
                {
                    "line_a": ia + 1,  # 1-indexed
                    "line_b": ib + 1,
                    "is_exact": is_exact,
                }
            )

        if all_exact:
            ptype = PlagiarismType.EXACT
            desc = None
            renames = None
        else:
            ptype = PlagiarismType.RENAMED
            renames = _extract_line_renames(lines_a, lines_b, shadow_a, shadow_b, sa, sb, length)
            desc = (
                ", ".join(f"{r['original']} → {r['renamed']}" for r in renames) if renames else None
            )

        matches.append(
            Match(
                file1={"start_line": sa, "start_col": 0, "end_line": sa + length - 1, "end_col": 0},
                file2={"start_line": sb, "start_col": 0, "end_line": sb + length - 1, "end_col": 0},
                kgram_count=length,
                plagiarism_type=ptype,
                similarity=1.0,
                details={"renames": renames} if renames else None,
                description=desc,
            )
        )
        used_a.update(range(sa, sa + length))
        used_b.update(range(sb, sb + length))

    matches.sort(key=lambda m: m.file1["start_line"])
    return matches


def _extract_line_renames(
    lines_a: list[str],
    lines_b: list[str],
    shadow_a: list[str],
    shadow_b: list[str],
    start_a: int,
    start_b: int,
    length: int,
) -> list[dict]:
    """
    For a matched shadow region, figure out which specific identifiers differ.

    Builds local VAR_N mappings per match region (first-occurrence order)
    and pairs identifiers that map to the same VAR_N across files.
    This correctly handles cases where identifiers appear in different orders.
    """
    import re

    vars_set = {f"VAR_{i}" for i in range(50)}

    def build_local_map(original_lines, shadow_lines):
        """Map VAR_N -> original name using first occurrence in the region."""
        mapping = {}
        for orig, shad in zip(original_lines, shadow_lines, strict=False):
            orig_names = [n for n in re.findall(r"\b[a-zA-Z_]\w*\b", orig) if n not in vars_set]
            shad_names = [n for n in re.findall(r"\b[a-zA-Z_]\w*\b", shad) if n in vars_set]
            for on, sn in zip(orig_names, shad_names, strict=False):
                if sn not in mapping:
                    mapping[sn] = on
        return mapping

    orig_a_lines = lines_a[start_a : start_a + length]
    shad_a_lines = shadow_a[start_a : start_a + length]
    orig_b_lines = lines_b[start_b : start_b + length]
    shad_b_lines = shadow_b[start_b : start_b + length]

    map_a = build_local_map(orig_a_lines, shad_a_lines)  # VAR_N -> name in A
    map_b = build_local_map(orig_b_lines, shad_b_lines)  # VAR_N -> name in B

    renames = []
    seen_renames: set[tuple[str, str]] = set()
    for var_n, name_a in map_a.items():
        name_b = map_b.get(var_n)
        if name_b and name_a != name_b and (name_a, name_b) not in seen_renames:
            renames.append({"original": name_a, "renamed": name_b, "line": start_a + 1})
            seen_renames.add((name_a, name_b))

    return renames
