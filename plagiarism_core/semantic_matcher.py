"""Semantic matcher for Type 2 (renamed), Type 3 (reordered), and Type 4 (semantic)."""

import logging
from collections import Counter
from typing import List

from .models import Match, PlagiarismType
from .parser import parse_string
from .detection.ast_helpers import _extract_functions
from .detection.line_helpers import _make_shadow_lines, _line_hash

logger = logging.getLogger(__name__)


class SemanticMatcher:
    """Function-level matching using structural and semantic hashes."""

    def __init__(self, min_function_lines: int = 3):
        self.min_lines = min_function_lines

    def match(
        self,
        source_a: str,
        source_b: str,
        lang: str = "python",
        structural_matches: List[Match] = None,
    ) -> List[Match]:
        """
        Detect function-level matches.

        Args:
            source_a, source_b: source code strings
            lang: language code
            structural_matches: optional matches from structural matcher to exclude

        Returns:
            List of Match objects (EXACT, RENAMED, REORDERED, SEMANTIC).
        """
        # Parse
        tree_a, bytes_a = parse_string(source_a, lang)
        tree_b, bytes_b = parse_string(source_b, lang)

        # Extract functions
        funcs_a = _extract_functions(tree_a.root_node, bytes_a, lang)
        funcs_b = _extract_functions(tree_b.root_node, bytes_b, lang)

        # Build indices for B
        struct_index_b = {}
        for j, fb in enumerate(funcs_b):
            h = fb.get("struct_hash")
            if h:
                struct_index_b.setdefault(h, []).append(j)

        sem_index_b = {}
        for j, fb in enumerate(funcs_b):
            h = fb.get("semantic_hash")
            if h:
                sem_index_b.setdefault(h, []).append(j)

        # Compute covered lines from structural_matches
        covered_a = set()
        covered_b = set()
        if structural_matches:
            for m in structural_matches:
                covered_a.update(range(m.file1["start_line"], m.file1["end_line"] + 1))
                covered_b.update(range(m.file2["start_line"], m.file2["end_line"] + 1))

        matches: List[Match] = []
        used_b: set[int] = set()
        used_a: set[int] = set()

        # First pass: structural hash matching (Type 1,2,3)
        for i, fa in enumerate(funcs_a):
            # Skip short functions
            if fa["end_line"] - fa["start_line"] + 1 < self.min_lines:
                continue
            func_lines_a = set(range(fa["start_line"], fa["end_line"] + 1))
            if func_lines_a & covered_a:
                continue

            struct_hash = fa.get("struct_hash")
            if not struct_hash:
                continue

            candidates = struct_index_b.get(struct_hash, [])
            matched = False
            for j in candidates:
                if j in used_b:
                    continue
                fb = funcs_b[j]
                func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
                if func_lines_b & covered_b:
                    continue

                # Classify based on name and position change (matching baseline behavior)
                is_renamed = fa["name"] != fb["name"]
                position_shift = abs(fa["start_line"] - fb["start_line"])
                # Baseline uses >2 lines shift as threshold for REORDERED
                is_reordered = position_shift > 2
                if is_renamed:
                    ptype = PlagiarismType.RENAMED
                    details = {"original_name": fa["name"], "renamed_name": fb["name"]}
                    desc = f"Function renamed: {fa['name']} → {fb['name']}"
                elif is_reordered:
                    ptype = PlagiarismType.REORDERED
                    details = None
                    desc = f"Function reordered: {fa['name']}"
                else:
                    ptype = PlagiarismType.EXACT
                    details = None
                    desc = None

                match = Match(
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
                    plagiarism_type=ptype,
                    similarity=1.0,
                    details=details,
                    description=desc,
                )
                matches.append(match)
                used_b.add(j)
                used_a.add(i)
                matched = True
                break  # one match per function A

            # If not matched via struct hash, try semantic hash (Type 4)
            if not matched:
                sem_hash = fa.get("semantic_hash")
                if sem_hash:
                    for j in sem_index_b.get(sem_hash, []):
                        if j in used_b:
                            continue
                        fb = funcs_b[j]
                        func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
                        if func_lines_b & covered_b:
                            continue
                        # Ensure struct hashes differ
                        if fa.get("struct_hash") == fb.get("struct_hash"):
                            continue
                        match = Match(
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
                            similarity=1.0,
                            details={"original_function": fa["name"], "matched_function": fb["name"]},
                            description=f"Semantic equivalent: {fa['name']} ↔ {fb['name']}",
                        )
                        matches.append(match)
                        used_b.add(j)
                        used_a.add(i)
        # Phase 2: Reordering detection via shadow line multiset matching for unmatched functions
        # Compute full shadow lines (identifier-normalized, comment-stripped)
        shadow_a_all = _make_shadow_lines(source_a, lang)
        shadow_b_all = _make_shadow_lines(source_b, lang)

        # Helper: multiset Jaccard similarity
        def _jaccard_similarity(c1: Counter, c2: Counter) -> float:
            if not c1 and not c2:
                return 1.0
            inter = sum(min(c1[h], c2.get(h, 0)) for h in c1)
            union = sum(max(c1.get(h, 0), c2.get(h, 0)) for h in set(c1) | set(c2))
            return inter / union if union else 0.0

        # Build candidate unmatched function lists with their shadow line hash counters
        unmatched_a = []
        for i, fa in enumerate(funcs_a):
            if i in used_a:
                continue
            func_len = fa["end_line"] - fa["start_line"] + 1
            if func_len < self.min_lines:
                continue
            start = fa["start_line"]
            end = fa["end_line"]
            counter = Counter()
            for line_idx in range(start, min(end + 1, len(shadow_a_all))):
                line = shadow_a_all[line_idx]
                if line:
                    h = _line_hash(line)
                    if h:
                        counter[h] += 1
            if counter:
                unmatched_a.append((i, counter, func_len))

        unmatched_b = []
        for j, fb in enumerate(funcs_b):
            if j in used_b:
                continue
            func_len = fb["end_line"] - fb["start_line"] + 1
            if func_len < self.min_lines:
                continue
            start = fb["start_line"]
            end = fb["end_line"]
            counter = Counter()
            for line_idx in range(start, min(end + 1, len(shadow_b_all))):
                line = shadow_b_all[line_idx]
                if line:
                    h = _line_hash(line)
                    if h:
                        counter[h] += 1
            if counter:
                unmatched_b.append((j, counter, func_len))

        # Try to match functions with high multiset similarity and similar length
        for i, counter_a, len_a in unmatched_a:
            best_j = None
            best_sim = 0.0
            for j, counter_b, len_b in unmatched_b:
                if j in used_b:
                    continue
                if abs(len_a - len_b) > max(10, int(0.7 * len_a)):
                    continue
                sim = _jaccard_similarity(counter_a, counter_b)
                if sim > best_sim:
                    best_sim = sim
                    best_j = j
            if best_j is not None and best_sim >= 0.60:
                fa = funcs_a[i]
                fb = funcs_b[best_j]
                match = Match(
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
                    kgram_count=len_a,
                    plagiarism_type=PlagiarismType.REORDERED,
                    similarity=1.0,
                    details=None,
                    description=f"Function reordered: {fa['name']}",
                )
                matches.append(match)
                used_a.add(i)
                used_b.add(best_j)

        return matches
