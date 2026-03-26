"""
Multi-level plagiarism detector.

Runs a cascade of matching strategies, each progressively more abstract:
  Level 1 – Exact line matching           → Type 1 (exact copy)
  Level 2 – Identifier-normalized lines   → Type 2 (renamed)
  Level 3 – Function structural matching  → Type 3 (reordered) / Type 2
  Level 4 – Semantic canonicalization     → Type 4 (semantic equivalent)

Each match carries a plagiarism_type, similarity score, and optional details
(renames detected, transformations applied, etc.).
"""

import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from tree_sitter import Node

from .canonicalizer import (
    _normalize_identifiers_from_tree,
    canonicalize_type4,
    get_identifier_renames,
    normalize_identifiers,
    parse_file_once_from_string,
)
from .fingerprints import stable_hash
from .models import Match, PlagiarismType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalized-line helpers
# ---------------------------------------------------------------------------

def _strip_comments(line: str) -> str:
    """Remove Python-style comments from a line, respecting strings."""
    in_string = False
    string_char = None
    result = []
    i = 0
    while i < len(line):
        ch = line[i]
        if not in_string:
            if ch in ('"', "'"):
                in_string = True
                string_char = ch
                result.append(ch)
            elif ch == '#' and (i == 0 or line[i - 1] != '\\'):
                break
            else:
                result.append(ch)
        else:
            result.append(ch)
            if ch == string_char and (i == 0 or line[i - 1] != '\\'):
                in_string = False
        i += 1
    return ''.join(result).strip()


def _make_shadow_lines(source: str, lang_code: str = 'python', tree=None, source_bytes: bytes = None) -> List[str]:
    """Produce identifier-normalized lines (shadow version)."""
    if tree is not None and source_bytes is not None:
        normalized = _normalize_identifiers_from_tree(tree, source_bytes, source)
    else:
        normalized = normalize_identifiers(source, lang_code)
    return normalized.split('\n')


def _make_exact_lines(source: str) -> List[str]:
    """Produce whitespace-and-comment-normalized lines."""
    import re
    lines = []
    for line in source.split('\n'):
        stripped = _strip_comments(line)
        if not stripped:
            lines.append('')
        else:
            lines.append(re.sub(r'\s+', ' ', stripped))
    return lines


def _line_hash(line: str) -> int:
    """Fast int hash for a normalized line using xxhash for consistency."""
    if not line:
        return 0
    return stable_hash(line)


# ---------------------------------------------------------------------------
# Level 1 + 2: Line-level matching
# ---------------------------------------------------------------------------

def _line_level_matches(
    lines_a: List[str],
    lines_b: List[str],
    shadow_a: List[str],
    shadow_b: List[str],
    min_match_lines: int = 2,
) -> List[Match]:
    """
    Match lines at two levels simultaneously.

    For each matching shadow-line region:
      - If the original lines also match → Type 1
      - If only the shadows match       → Type 2 (with rename info)
    """
    # Build hash → line-indices index for shadow B
    shadow_b_index: Dict[int, List[int]] = {}
    for j, s in enumerate(shadow_b):
        if s:
            shadow_b_index.setdefault(_line_hash(s), []).append(j)

    # Build hash of exact lines for A
    exact_a_hashes = [_line_hash(l) for l in lines_a]
    exact_b_hashes = [_line_hash(l) for l in lines_b]

    # Find all A→B shadow-matching line pairs
    pair_map: Dict[int, List[int]] = {}
    for i, s in enumerate(shadow_a):
        if not s:
            continue
        h = _line_hash(s)
        if h in shadow_b_index:
            pair_map[i] = shadow_b_index[h]

    # Extend matches to contiguous regions
    raw: List[Tuple[int, int, int]] = []  # (start_a, start_b, length)
    visited: Set[int] = set()

    for start_a in sorted(pair_map.keys()):
        if start_a in visited:
            continue
        for start_b in pair_map[start_a]:
            length = 0
            ia, ib = start_a, start_b
            while (
                ia < len(shadow_a)
                and ib < len(shadow_b)
                and shadow_a[ia]
                and shadow_b[ib]
                and _line_hash(shadow_a[ia]) == _line_hash(shadow_b[ib])
            ):
                length += 1
                visited.add(ia)
                ia += 1
                ib += 1
            if length >= min_match_lines:
                raw.append((start_a, start_b, length))

    # Greedy longest-first, non-overlapping selection
    raw.sort(key=lambda x: -x[2])
    used_a: Set[int] = set()
    used_b: Set[int] = set()
    matches: List[Match] = []

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
            line_details.append({
                'line_a': ia + 1,   # 1-indexed
                'line_b': ib + 1,
                'is_exact': is_exact,
            })

        if all_exact:
            ptype = PlagiarismType.EXACT
            desc = None
            renames = None
        else:
            ptype = PlagiarismType.RENAMED
            renames = _extract_line_renames(lines_a, lines_b, shadow_a, shadow_b, sa, sb, length)
            desc = ', '.join(f"{r['original']} → {r['renamed']}" for r in renames) if renames else None

        matches.append(Match(
            file1={'start_line': sa, 'start_col': 0, 'end_line': sa + length - 1, 'end_col': 0},
            file2={'start_line': sb, 'start_col': 0, 'end_line': sb + length - 1, 'end_col': 0},
            kgram_count=length,
            plagiarism_type=ptype,
            similarity=1.0,
            details={'renames': renames} if renames else None,
            description=desc,
        ))
        used_a.update(range(sa, sa + length))
        used_b.update(range(sb, sb + length))

    matches.sort(key=lambda m: m.file1['start_line'])
    return matches


def _extract_line_renames(
    lines_a: List[str],
    lines_b: List[str],
    shadow_a: List[str],
    shadow_b: List[str],
    start_a: int,
    start_b: int,
    length: int,
) -> List[Dict]:
    """
    For a matched shadow region, figure out which specific identifiers differ.
    Uses occurrence ordering within the region for accurate pairing.
    """
    import re
    # Collect ordered lists of unique identifiers from each side
    # preserving first-occurrence order (consistent with canonicalizer)
    seen_a: Dict[str, int] = {}  # name → first offset
    seen_b: Dict[str, int] = {}
    vars_set = {f'VAR_{i}' for i in range(20)}

    for offset in range(length):
        ia, ib = start_a + offset, start_b + offset
        if ia >= len(lines_a) or ib >= len(lines_b):
            continue
        for name in re.findall(r'\b[a-zA-Z_]\w*\b', lines_a[ia]):
            if name not in seen_a and name not in vars_set:
                seen_a[name] = offset
        for name in re.findall(r'\b[a-zA-Z_]\w*\b', lines_b[ib]):
            if name not in seen_b and name not in vars_set:
                seen_b[name] = offset

    # Sort by first occurrence to get consistent ordering
    ordered_a = sorted(seen_a, key=lambda n: seen_a[n])
    ordered_b = sorted(seen_b, key=lambda n: seen_b[n])

    # Pair by position order using enumerate (O(n) instead of O(n²))
    renames = []
    paired_b: Set[str] = set()
    for idx_a, name_a in enumerate(ordered_a):
        if idx_a < len(ordered_b):
            name_b = ordered_b[idx_a]
            if name_a != name_b and name_b not in paired_b:
                renames.append({
                    'original': name_a,
                    'renamed': name_b,
                    'line': start_a + seen_a[name_a] + 1,
                })
                paired_b.add(name_b)

    return renames


# ---------------------------------------------------------------------------
# AST structural hashing (identifier-independent, with semantic normalization)
# ---------------------------------------------------------------------------

# Import semantic node type map from canonicalizer for consistent hashing
from .canonicalizer import SEMANTIC_NODE_MAP, _semantic_node_type


def _hash_ast_subtree(node: Node, use_semantic: bool = False) -> int:
    """
    Hash a subtree's structure, optionally using semantic normalization.

    If use_semantic=True, semantically equivalent constructs (for/while loops,
    list comprehensions/map calls, etc.) produce the same hash, enabling better
    Type 4 detection at the AST level.

    With use_semantic=False (default), the function ignores identifier names,
    so two functions with different variable names produce identical hashes
    (for Type 2 detection).
    """
    if node.type == 'comment':
        return 0

    # Get the effective node type for hashing
    if use_semantic:
        hash_type = _semantic_node_type(node) or node.type
    else:
        hash_type = node.type

    if not node.children:
        if hash_type == 'identifier':
            return 0  # ignore names entirely
        return stable_hash(hash_type)

    child_hashes = []
    for child in node.children:
        ch = _hash_ast_subtree(child, use_semantic)
        if ch:
            child_hashes.append(ch)

    if not child_hashes:
        return 0

    rep = hash_type + "(" + ",".join(str(h) for h in child_hashes) + ")"
    return stable_hash(rep)


def _hash_ast_subtree_semantic(node: Node) -> int:
    """
    Hash a subtree using semantic normalization (Approach A).
    
    Semantically equivalent code constructs produce identical hashes:
      - for loops and while loops → same hash (LOOP)
      - list comprehensions and map() calls → same hash (COLLECTION)
      - f-strings and .format() → same hash (STRING_FORMAT)
    """
    return _hash_ast_subtree(node, use_semantic=True)


def _extract_functions(root_node: Node, source_bytes: bytes) -> List[Dict]:
    """Extract top-level function definitions with both structural and semantic hashes."""
    functions = []
    for child in root_node.children:
        if child.type in ('function_definition', 'decorated_definition'):
            # For decorated definitions, find the actual function_definition inside
            func_node = child
            if child.type == 'decorated_definition':
                for sub in child.children:
                    if sub.type == 'function_definition':
                        func_node = sub
                        break

            # Get function name
            name = None
            for sub in func_node.children:
                if sub.type == 'identifier':
                    name = source_bytes[sub.start_byte:sub.end_byte].decode('utf-8', errors='ignore')
                    break

            struct_hash = _hash_ast_subtree(child)
            semantic_hash = _hash_ast_subtree_semantic(child)
            functions.append({
                'name': name or '<anonymous>',
                'start_line': child.start_point[0],
                'end_line': child.end_point[0],
                'struct_hash': struct_hash,
                'semantic_hash': semantic_hash,
                'node': child,
            })

        elif child.type == 'class_definition':
            struct_hash = _hash_ast_subtree(child)
            semantic_hash = _hash_ast_subtree_semantic(child)
            name = None
            for sub in child.children:
                if sub.type == 'identifier':
                    name = source_bytes[sub.start_byte:sub.end_byte].decode('utf-8', errors='ignore')
                    break
            functions.append({
                'name': name or '<anonymous>',
                'start_line': child.start_point[0],
                'end_line': child.end_point[0],
                'struct_hash': struct_hash,
                'semantic_hash': semantic_hash,
                'node': child,
            })

    return functions


# ---------------------------------------------------------------------------
# Level 3: Function-level matching (reordering / renaming)
# ---------------------------------------------------------------------------

def _function_level_matches(
    source_a: str,
    source_b: str,
    used_lines_a: Set[int],
    used_lines_b: Set[int],
    lang_code: str = 'python',
    tree_a=None,
    bytes_a: bytes = None,
    tree_b=None,
    bytes_b: bytes = None,
) -> List[Match]:
    """
    Match functions between files by structural hash (identifiers ignored).

    Produces:
      - Type 3 if the function moved to a different position
      - Type 2 if it stayed in the same position but has different names
    """
    if tree_a is None or bytes_a is None or tree_b is None or bytes_b is None:
        try:
            tree_a, bytes_a = parse_file_once_from_string(source_a, lang_code)
            tree_b, bytes_b = parse_file_once_from_string(source_b, lang_code)
        except Exception:
            logger.warning("Failed to parse sources for function-level matching (lang=%s), skipping", lang_code, exc_info=True)
            return []

    funcs_a = _extract_functions(tree_a.root_node, bytes_a)
    funcs_b = _extract_functions(tree_b.root_node, bytes_b)

    # Index B functions by struct hash
    hash_index: Dict[int, List[int]] = {}
    for j, f in enumerate(funcs_b):
        if f['struct_hash']:
            hash_index.setdefault(f['struct_hash'], []).append(j)

    used_b_idx: Set[int] = set()
    matches: List[Match] = []

    for i, fa in enumerate(funcs_a):
        # Skip if already covered by line-level matching
        func_lines_a = set(range(fa['start_line'], fa['end_line'] + 1))
        if func_lines_a & used_lines_a:
            continue
        if not fa['struct_hash']:
            continue

        candidates = hash_index.get(fa['struct_hash'], [])
        for j in candidates:
            if j in used_b_idx:
                continue
            fb = funcs_b[j]
            func_lines_b = set(range(fb['start_line'], fb['end_line'] + 1))
            if func_lines_b & used_lines_b:
                continue

            # Classify
            is_reordered = (abs(fa['start_line'] - fb['start_line']) > 2)
            is_renamed = (fa['name'] != fb['name'])

            if is_renamed:
                ptype = PlagiarismType.RENAMED
                desc = f"Function renamed: {fa['name']} → {fb['name']}"
            elif is_reordered:
                ptype = PlagiarismType.REORDERED
                desc = f"Function reordered: {fa['name']}"
            else:
                ptype = PlagiarismType.EXACT
                desc = None

            matches.append(Match(
                file1={
                    'start_line': fa['start_line'],
                    'start_col': 0,
                    'end_line': fa['end_line'],
                    'end_col': 0,
                },
                file2={
                    'start_line': fb['start_line'],
                    'start_col': 0,
                    'end_line': fb['end_line'],
                    'end_col': 0,
                },
                kgram_count=fa['end_line'] - fa['start_line'] + 1,
                plagiarism_type=ptype,
                similarity=1.0,
                details={'original_name': fa['name'], 'renamed_name': fb['name']} if is_renamed else None,
                description=desc,
            ))
            used_b_idx.add(j)
            break

    return matches


# ---------------------------------------------------------------------------
# Level 4: Line-level semantic canonicalization
# ---------------------------------------------------------------------------

def _semantic_line_matches(
    source_a: str,
    source_b: str,
    used_lines_a: Set[int],
    used_lines_b: Set[int],
    lines_a: List[str],
    lines_b: List[str],
    shadow_a: List[str],
    shadow_b: List[str],
    min_match_lines: int = 2,
    lang_code: str = 'python',
) -> List[Match]:
    """
    For unmatched lines, apply Type 4 canonicalization and re-match.

    Only classifies lines as SEMANTIC if they:
      1. Don't match in original form (not EXACT)
      2. Don't match in shadow form (not RENAMED)
      3. Do match after Type 4 canonicalization (SEMANTIC)
    """
    if lang_code != 'python':
        return []

    # Canonicalize all lines (but only check unmatched ones)
    # Skip lines that match in shadow form (those are RENAMED, not SEMANTIC)
    canon_a_lines = []
    canon_b_lines = []
    for i, line in enumerate(lines_a):
        if i in used_lines_a or not line.strip():
            canon_a_lines.append('')
        else:
            # Skip if shadow matches (would be RENAMED, not SEMANTIC)
            if i < len(shadow_a) and i < len(shadow_b):
                shadow_h_a = _line_hash(shadow_a[i].strip())
                shadow_h_b = _line_hash(shadow_b[i].strip()) if i < len(shadow_b) else 0
                if shadow_h_a and shadow_h_a == shadow_h_b:
                    canon_a_lines.append('')
                    continue
            canon = canonicalize_type4(line)
            canon = normalize_identifiers(canon, lang_code)
            canon_a_lines.append(canon.strip())
    for j, line in enumerate(lines_b):
        if j in used_lines_b or not line.strip():
            canon_b_lines.append('')
        else:
            # Skip if shadow matches (would be RENAMED, not SEMANTIC)
            if j < len(shadow_b) and j < len(shadow_a):
                shadow_h_b = _line_hash(shadow_b[j].strip())
                shadow_h_a = _line_hash(shadow_a[j].strip()) if j < len(shadow_a) else 0
                if shadow_h_b and shadow_h_b == shadow_h_a:
                    canon_b_lines.append('')
                    continue
            canon = canonicalize_type4(line)
            canon = normalize_identifiers(canon, lang_code)
            canon_b_lines.append(canon.strip())

    # Build hash index for B's canonicalized lines
    canon_b_index: Dict[int, List[int]] = {}
    for j, c in enumerate(canon_b_lines):
        if c:
            canon_b_index.setdefault(_line_hash(c), []).append(j)

    # Find matching canonicalized line pairs
    pair_map: Dict[int, List[int]] = {}
    for i, c in enumerate(canon_a_lines):
        if not c:
            continue
        h = _line_hash(c)
        if h in canon_b_index:
            pair_map[i] = canon_b_index[h]

    # Extend to contiguous regions of lines that match ONLY after canonicalization
    # (i.e., the original lines differ but canonicalized forms match)
    raw: List[Tuple[int, int, int]] = []
    visited: Set[int] = set()

    for start_a in sorted(pair_map.keys()):
        if start_a in visited:
            continue
        for start_b in pair_map[start_a]:
            # Only extend through lines that DIFFER in original but MATCH after canonicalization
            # Lines that already match in the original should be left as EXACT type
            length = 0
            ia, ib = start_a, start_b
            while (ia < len(canon_a_lines) and ib < len(canon_b_lines)
                   and canon_a_lines[ia] and canon_b_lines[ib]
                   and _line_hash(canon_a_lines[ia]) == _line_hash(canon_b_lines[ib])):
                # Check if this line actually differs in the original
                orig_match = (ia < len(lines_a) and ib < len(lines_b)
                              and _line_hash(lines_a[ia].strip()) == _line_hash(lines_b[ib].strip()))
                if orig_match:
                    # This line already matches in original - stop extending
                    break
                length += 1
                visited.add(ia)
                ia += 1
                ib += 1
            if length >= min_match_lines:
                raw.append((start_a, start_b, length))

    # Greedy longest-first selection
    raw.sort(key=lambda x: -x[2])
    used_a: Set[int] = set()
    used_b: Set[int] = set()
    matches: List[Match] = []

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
                    transforms.append({
                        'line_a': ia + 1,
                        'line_b': ib + 1,
                        'original': lines_a[ia].strip()[:80],
                        'canonical': lines_b[ib].strip()[:80],
                    })

        desc = None
        if transforms:
            # Summarize the transformation types
            descs = []
            for t in transforms:
                if 'for ' in t['original'] and 'map(' in t['canonical']:
                    descs.append('list comprehension → map')
                elif '+=' in t['original'] or '+=' in t['canonical']:
                    descs.append('augmented assignment')
                elif 'lambda' in t['original'] or 'lambda' in t['canonical']:
                    descs.append('lambda ↔ def')
                else:
                    descs.append('semantic rewrite')
            desc = ', '.join(set(descs))

        matches.append(Match(
            file1={'start_line': sa, 'start_col': 0, 'end_line': sa + length - 1, 'end_col': 0},
            file2={'start_line': sb, 'start_col': 0, 'end_line': sb + length - 1, 'end_col': 0},
            kgram_count=length,
            plagiarism_type=PlagiarismType.SEMANTIC,
            similarity=1.0,
            details={'transformations': transforms} if transforms else None,
            description=desc,
        ))
        used_a.update(range(sa, sa + length))
        used_b.update(range(sb, sb + length))

    matches.sort(key=lambda m: m.file1['start_line'])
    return matches


# ---------------------------------------------------------------------------
# Level 4b: Function-level semantic canonicalization (existing)
# ---------------------------------------------------------------------------

def _semantic_function_matches(
    source_a: str,
    source_b: str,
    used_lines_a: Set[int],
    used_lines_b: Set[int],
    lang_code: str = 'python',
    tree_a=None,
    bytes_a: bytes = None,
    tree_b=None,
    bytes_b: bytes = None,
) -> List[Match]:
    """
    Apply Type 4 semantic matching at the function level.

    Uses AST-level semantic normalization (Approach A): semantically equivalent
    constructs (for/while loops, comprehensions, f-strings, etc.) produce identical
    semantic hashes, enabling detection even when the structural hashes differ.

    For each unmatched function in A, tries to find a function in B that:
      1. Didn't match at any earlier level
      2. Has the same SEMANTIC hash (different from structural hash)
    """
    if lang_code != 'python':
        return []

    if tree_a is None or bytes_a is None or tree_b is None or bytes_b is None:
        try:
            tree_a, bytes_a = parse_file_once_from_string(source_a, lang_code)
            tree_b, bytes_b = parse_file_once_from_string(source_b, lang_code)
        except Exception:
            logger.warning("Failed to parse sources for semantic function matching (lang=%s), skipping", lang_code, exc_info=True)
            return []

    funcs_a = _extract_functions(tree_a.root_node, bytes_a)
    funcs_b = _extract_functions(tree_b.root_node, bytes_b)

    # Index B functions by semantic hash (not structural hash)
    # This catches semantically equivalent code that structurally differs
    sem_b_hashes: Dict[int, List[int]] = {}
    for j, fb in enumerate(funcs_b):
        if fb['semantic_hash']:
            sem_b_hashes.setdefault(fb['semantic_hash'], []).append(j)

    used_b_idx: Set[int] = set()
    matches: List[Match] = []

    for i, fa in enumerate(funcs_a):
        func_lines_a = set(range(fa['start_line'], fa['end_line'] + 1))
        if func_lines_a & used_lines_a:
            continue
        if not fa['semantic_hash']:
            continue

        # Only match by semantic hash if structural hashes differ
        # (if structural hashes match, they would have been caught at Level 3)
        candidates = sem_b_hashes.get(fa['semantic_hash'], [])
        for j in candidates:
            if j in used_b_idx:
                continue
            fb = funcs_b[j]
            func_lines_b = set(range(fb['start_line'], fb['end_line'] + 1))
            if func_lines_b & used_lines_b:
                continue

            # Only classify as SEMANTIC if structural hashes differ
            # If they're the same, it would have been caught at Level 3
            if fa['struct_hash'] == fb['struct_hash']:
                continue

            matches.append(Match(
                file1={
                    'start_line': fa['start_line'],
                    'start_col': 0,
                    'end_line': fa['end_line'],
                    'end_col': 0,
                },
                file2={
                    'start_line': fb['start_line'],
                    'start_col': 0,
                    'end_line': fb['end_line'],
                    'end_col': 0,
                },
                kgram_count=fa['end_line'] - fa['start_line'] + 1,
                plagiarism_type=PlagiarismType.SEMANTIC,
                similarity=1.0,
                details={
                    'original_function': fa['name'],
                    'matched_function': fb['name'],
                },
                description=f"Semantic equivalent: {fa['name']} ↔ {fb['name']}",
            ))
            used_b_idx.add(j)
            break

    return matches


# ---------------------------------------------------------------------------
# Match merging
# ---------------------------------------------------------------------------

def _merge_matches(matches: List[Match], gap: int = 0) -> List[Match]:
    """
    Merge adjacent matches that are of the SAME plagiarism type.

    Only merges matches with identical plagiarism_type to avoid
    swallowing Type 4 (semantic) lines into surrounding Type 1 (exact) regions.
    """
    if not matches:
        return []

    matches = sorted(matches, key=lambda m: (m.file1['start_line'], m.file2['start_line']))
    merged = [Match(
        file1=dict(matches[0].file1),
        file2=dict(matches[0].file2),
        kgram_count=matches[0].kgram_count,
        plagiarism_type=matches[0].plagiarism_type,
        similarity=matches[0].similarity,
        details=matches[0].details,
        description=matches[0].description,
    )]

    for m in matches[1:]:
        prev = merged[-1]
        f1_adj = m.file1['start_line'] <= prev.file1['end_line'] + gap + 1
        f2_adj = m.file2['start_line'] <= prev.file2['end_line'] + gap + 1
        same_type = m.plagiarism_type == prev.plagiarism_type

        if f1_adj and f2_adj and same_type:
            prev.file1['end_line'] = max(prev.file1['end_line'], m.file1['end_line'])
            prev.file2['end_line'] = max(prev.file2['end_line'], m.file2['end_line'])
            prev.kgram_count += m.kgram_count
            # Merge details
            if m.details:
                if prev.details:
                    for k, v in m.details.items():
                        if k in prev.details and isinstance(prev.details[k], list) and isinstance(v, list):
                            prev.details[k].extend(v)
                        else:
                            prev.details[k] = v
                else:
                    prev.details = m.details
        else:
            merged.append(Match(
                file1=dict(m.file1),
                file2=dict(m.file2),
                kgram_count=m.kgram_count,
                plagiarism_type=m.plagiarism_type,
                similarity=m.similarity,
                details=m.details,
                description=m.description,
            ))

    return merged


# ---------------------------------------------------------------------------
# Line coverage helper
# ---------------------------------------------------------------------------

def _covered_lines(matches: List[Match], is_file1: bool) -> Set[int]:
    """Get the set of covered line indices (0-indexed) from matches."""
    covered: Set[int] = set()
    for m in matches:
        region = m.file1 if is_file1 else m.file2
        for line in range(region['start_line'], region['end_line'] + 1):
            covered.add(line)
    return covered


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def detect_plagiarism(
    source_a: str,
    source_b: str,
    lang_code: str = 'python',
    min_match_lines: int = 2,
) -> List[Match]:
    """
    Run the full multi-level plagiarism detection pipeline.

    Returns a list of Match objects, each annotated with:
      - plagiarism_type (1-4)
      - similarity (0.0-1.0)
      - details (renames, transformations)
      - description (human-readable)

    The pipeline:
      1. Line-level matching (Type 1 exact + Type 2 renamed)
      2. Function-level structural matching (Type 3 reordered / Type 2 renamed)
      3. Semantic canonicalization matching (Type 4)
    """
    lines_a = source_a.split('\n')
    lines_b = source_b.split('\n')

    # Parse once, reuse across all match phases
    try:
        tree_a, bytes_a = parse_file_once_from_string(source_a, lang_code)
        tree_b, bytes_b = parse_file_once_from_string(source_b, lang_code)
    except Exception:
        logger.warning("Failed to parse sources (lang=%s), falling back to unoptimized path", lang_code, exc_info=True)
        tree_a, bytes_a, tree_b, bytes_b = None, None, None, None

    # Generate shadow (identifier-normalized) lines using pre-parsed trees
    shadow_a = _make_shadow_lines(source_a, lang_code, tree_a, bytes_a)
    shadow_b = _make_shadow_lines(source_b, lang_code, tree_b, bytes_b)

    # Level 1+2: Line-level matching
    line_matches = _line_level_matches(
        lines_a, lines_b, shadow_a, shadow_b, min_match_lines
    )

    # Track covered lines
    covered_a = _covered_lines(line_matches, True)
    covered_b = _covered_lines(line_matches, False)

    # Level 3: Function-level matching (Type 3 / Type 2) — reuse parsed trees
    func_matches = _function_level_matches(
        source_a, source_b, covered_a, covered_b, lang_code,
        tree_a=tree_a, bytes_a=bytes_a, tree_b=tree_b, bytes_b=bytes_b,
    )
    covered_a = covered_a | _covered_lines(func_matches, True)
    covered_b = covered_b | _covered_lines(func_matches, False)

    # Level 4a: Line-level semantic matching (per-line canonicalization)
    # Use min_match_lines=1 since individual lines can be Type 4 matches
    sem_line_matches = _semantic_line_matches(
        source_a, source_b, covered_a, covered_b,
        lines_a, lines_b, shadow_a, shadow_b,
        min_match_lines=1, lang_code=lang_code,
    )
    covered_a = covered_a | _covered_lines(sem_line_matches, True)
    covered_b = covered_b | _covered_lines(sem_line_matches, False)

    # Level 4b: Function-level semantic matching — reuse parsed trees
    sem_func_matches = _semantic_function_matches(
        source_a, source_b, covered_a, covered_b, lang_code,
        tree_a=tree_a, bytes_a=bytes_a, tree_b=tree_b, bytes_b=bytes_b,
    )

    # Combine all matches
    all_matches = line_matches + func_matches + sem_line_matches + sem_func_matches

    # Merge only truly adjacent (gap=0) same-type matches.
    # Using gap>0 would swallow single-line mismatches and incorrectly
    # classify them as the surrounding match type.
    all_matches = _merge_matches(all_matches, gap=0)

    # Sort by file A line
    all_matches.sort(key=lambda m: m.file1['start_line'])

    return all_matches


def detect_plagiarism_from_files(
    file_a: str,
    file_b: str,
    lang_code: str = 'python',
    min_match_lines: int = 2,
) -> List[Match]:
    """Convenience wrapper that reads files from disk."""
    with open(file_a, 'r', encoding='utf-8', errors='ignore') as f:
        source_a = f.read()
    with open(file_b, 'r', encoding='utf-8', errors='ignore') as f:
        source_b = f.read()
    return detect_plagiarism(source_a, source_b, lang_code, min_match_lines)
