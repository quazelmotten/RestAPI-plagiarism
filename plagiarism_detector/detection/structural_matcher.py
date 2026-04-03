"""
Structural function-level matcher (Type 2 and Type 3).

Matches functions based on structural similarity (ignoring identifier names).
Uses AST subtree hashing with scope-normalized identifiers.
Also performs line-level exact and renamed matching within matched function bodies.
"""

from ..models import FunctionInfo, Match, PlagiarismType, Point, Region
from ..normalization.identifiers import normalize_identifiers
from ..parsing.parser import ParsedFile
from .base import BaseMatcher


class StructuralFunctionMatcher(BaseMatcher):
    """Matches functions via structural hash (Type 2/3)."""

    MATCH_TYPE = PlagiarismType.RENAMED  # default; may become REORDERED based on position

    def __init__(self, config):
        super().__init__(config)
        # No additional state needed; using legacy function extraction.

    def run(
        self, file_a: ParsedFile, file_b: ParsedFile, covered_a: set[int], covered_b: set[int]
    ) -> list[Match]:
        """
        Find matching functions via structural hashing.

        Returns both function-level matches (Type 2/3) and line-level matches
        (Type 1 for exact, Type 2 for renamed) for the interior of matched functions.
        """
        # Precompute full lines and shadow lines for both files (to get interior matches)
        lines_a_full = file_a.source_bytes.decode("utf-8", errors="ignore").splitlines()
        lines_b_full = file_b.source_bytes.decode("utf-8", errors="ignore").splitlines()
        shadow_a_full = normalize_identifiers(file_a).splitlines()
        shadow_b_full = normalize_identifiers(file_b).splitlines()

        # Extract functions from both files
        funcs_a = self._extract_functions(file_a)
        funcs_b = self._extract_functions(file_b)

        # Build index of B functions by structural hash
        index_b: dict[str, list[FunctionInfo]] = {}
        for func in funcs_b:
            if func.structural_hash:
                index_b.setdefault(func.structural_hash, []).append(func)

        matches: list[Match] = []
        used_b: set[int] = set()  # indices of B functions already matched

        for func_a in funcs_a:
            # Skip if function body already covered
            func_lines_a = set(range(func_a.region.start.line, func_a.region.end.line + 1))
            if func_lines_a & covered_a:
                continue
            if not func_a.structural_hash:
                continue

            candidates = index_b.get(func_a.structural_hash, [])
            for func_b in candidates:
                if id(func_b) in used_b:
                    continue
                func_lines_b = set(range(func_b.region.start.line, func_b.region.end.line + 1))
                if func_lines_b & covered_b:
                    continue

                # Classify function-level match
                is_reordered = abs(func_a.region.start.line - func_b.region.start.line) > 2
                is_renamed = func_a.name != func_b.name

                if is_renamed:
                    ptype = PlagiarismType.RENAMED
                    desc = f"Function renamed: {func_a.name} → {func_b.name}"
                elif is_reordered:
                    ptype = PlagiarismType.REORDERED
                    desc = f"Function reordered: {func_a.name}"
                else:
                    ptype = PlagiarismType.EXACT
                    desc = None

                # Add function-level match
                func_match = Match(
                    file1_region=func_a.region,
                    file2_region=func_b.region,
                    kgram_count=func_a.region.line_count,
                    plagiarism_type=ptype,
                    similarity=1.0,
                    details={"original_name": func_a.name, "renamed_name": func_b.name}
                    if is_renamed
                    else None,
                    description=desc,
                )
                matches.append(func_match)

                # Line-level matching within these matched function bodies
                # Extract line slices
                start_a = func_a.region.start.line
                end_a = func_a.region.end.line + 1
                start_b = func_b.region.start.line
                end_b = func_b.region.end.line + 1

                orig_a = lines_a_full[start_a:end_a]
                orig_b = lines_b_full[start_b:end_b]
                shad_a = shadow_a_full[start_a:end_a]
                shad_b = shadow_b_full[start_b:end_b]

                # Find both exact and renamed line matches
                line_matches = self._match_lines_combined(
                    orig_a,
                    orig_b,
                    shad_a,
                    shad_b,
                    offset_a=start_a,
                    offset_b=start_b,
                    min_lines=self.config.min_match_lines,
                )
                matches.extend(line_matches)

                used_b.add(id(func_b))
                break  # one-to-one matching

        return matches

    def _extract_functions(self, parsed: ParsedFile) -> list[FunctionInfo]:
        """Extract functions from parsed file using legacy robust implementation."""
        from plagiarism_core.plagiarism_detector import _extract_functions as legacy_extract

        # legacy_extract returns list of dicts with keys: name, start_line, end_line,
        # struct_hash, semantic_hash, node
        legacy_funcs = legacy_extract(parsed.get_root_node(), parsed.source_bytes, parsed.language)

        funcs = []
        for f in legacy_funcs:
            region = Region(start=Point(f["start_line"], 0), end=Point(f["end_line"], 0))
            funcs.append(
                FunctionInfo(
                    name=f["name"],
                    qualified_name=f["name"],  # could enhance with class name if needed
                    region=region,
                    structural_hash=f["struct_hash"],
                    semantic_hash=f["semantic_hash"],
                    node=f["node"],
                )
            )
        return funcs

    def _match_lines_combined(
        self,
        orig_a: list[str],
        orig_b: list[str],
        shad_a: list[str],
        shad_b: list[str],
        offset_a: int,
        offset_b: int,
        min_lines: int = 3,
    ) -> list[Match]:
        """
        Find contiguous line matches considering both exact and renamed (shadow) matches.
        Returns matches with appropriate types (EXACT or RENAMED).
        """
        n, m = len(orig_a), len(orig_b)

        # Build hash indices for shadow lines of B
        shadow_b_hashes = [hash(s.strip()) for s in shad_b]
        shadow_b_index: dict[int, list[int]] = {}
        for j, h in enumerate(shadow_b_hashes):
            if h:
                shadow_b_index.setdefault(h, []).append(j)

        # Build exact hashes for A and B
        exact_a_hashes = [hash(o.strip()) for o in orig_a]
        exact_b_hashes = [hash(o.strip()) for o in orig_b]

        # Build map of A shadow hashes and their positions
        shadow_a_hashes = [hash(s.strip()) for s in shad_a]
        pair_map: dict[int, list[int]] = {}
        for i, h in enumerate(shadow_a_hashes):
            if h and h in shadow_b_index:
                pair_map[i] = shadow_b_index[h]

        # Extend to contiguous matches
        raw: list[tuple[int, int, int]] = []  # (start_a, start_b, length, has_exact)
        visited: set[int] = set()

        for start_a in sorted(pair_map.keys()):
            if start_a in visited:
                continue
            candidates = pair_map[start_a]
            best_b, best_len, best_has_exact = candidates[0], 0, False
            for start_b in candidates:
                length = 0
                has_exact = False
                ia, ib = start_a, start_b
                while (
                    ia < n
                    and ib < m
                    and shadow_a_hashes[ia] != 0
                    and shadow_b_hashes[ib] != 0
                    and shadow_a_hashes[ia] == shadow_b_hashes[ib]
                ):
                    # Check if this line is also exactly equal
                    if exact_a_hashes[ia] != 0 and exact_a_hashes[ia] == exact_b_hashes[ib]:
                        has_exact = True
                    length += 1
                    ia += 1
                    ib += 1
                if length > best_len:
                    best_b, best_len, best_has_exact = start_b, length, has_exact
            if best_len >= min_lines:
                for offset in range(best_len):
                    visited.add(start_a + offset)
                raw.append((start_a, best_b, best_len, best_has_exact))

        # Sort by length descending for greedy selection
        raw.sort(key=lambda x: -x[2])
        used_a: set[int] = set()
        used_b: set[int] = set()
        matches: list[Match] = []

        for sa, sb, length, has_exact in raw:
            ra = set(range(sa, sa + length))
            rb = set(range(sb, sb + length))
            if ra & used_a or rb & used_b:
                # Trim overlapping edges similar to original
                while (sa in used_a or sb in used_b) and length > 0:
                    sa += 1
                    sb += 1
                    length -= 1
                while ((sa + length - 1) in used_a or ((sb + length - 1) in used_b)) and length > 0:
                    length -= 1
                if length < min_lines:
                    continue
                # Re-evaluate has_exact for trimmed? For simplicity, keep original.
            ptype = PlagiarismType.EXACT if has_exact else PlagiarismType.RENAMED
            m = Match(
                file1_region=Region(
                    start=Point(offset_a + sa, 0), end=Point(offset_a + sa + length - 1, 0)
                ),
                file2_region=Region(
                    start=Point(offset_b + sb, 0), end=Point(offset_b + sb + length - 1, 0)
                ),
                kgram_count=length,
                plagiarism_type=ptype,
                similarity=1.0,
                description=f"{'Exact' if has_exact else 'Renamed'} lines within function",
            )
            matches.append(m)
            used_a.update(range(sa, sa + length))
            used_b.update(range(sb, sb + length))

        return matches
