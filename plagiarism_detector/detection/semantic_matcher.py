"""
Semantic function-level matcher (Type 4).

Matches functions based on semantic hash (ignoring identifier names and
normalizing equivalent constructs like for↔while, comprehensions, etc.).
"""

from ..models import FunctionInfo, Match, PlagiarismType, Point, Region
from ..parsing.parser import ParsedFile
from .base import BaseMatcher


class SemanticFunctionMatcher(BaseMatcher):
    """Matches functions via semantic hash (Type 4)."""

    MATCH_TYPE = PlagiarismType.SEMANTIC

    def run(
        self, file_a: ParsedFile, file_b: ParsedFile, covered_a: set[int], covered_b: set[int]
    ) -> list[Match]:
        """
        Find semantically equivalent functions.

        Uses the semantic hash computed during function extraction.
        """
        # Extract functions (we need the semantic hashes)
        funcs_a = self._extract_functions(file_a)
        funcs_b = self._extract_functions(file_b)

        # Index B by semantic hash
        index_b: dict[str, list[FunctionInfo]] = {}
        for func in funcs_b:
            if func.semantic_hash:
                index_b.setdefault(func.semantic_hash, []).append(func)

        matches: list[Match] = []
        used_b: set[int] = set()

        for func_a in funcs_a:
            # Skip if already covered
            func_lines_a = set(range(func_a.region.start.line, func_a.region.end.line + 1))
            if func_lines_a & covered_a:
                continue
            if not func_a.semantic_hash:
                continue

            candidates = index_b.get(func_a.semantic_hash, [])
            for func_b in candidates:
                if id(func_b) in used_b:
                    continue
                func_lines_b = set(range(func_b.region.start.line, func_b.region.end.line + 1))
                if func_lines_b & covered_b:
                    continue

                # Only match if structural hashes differ (true semantic equivalence)
                if func_a.structural_hash == func_b.structural_hash:
                    continue

                # Semantic match
                match = Match(
                    file1_region=func_a.region,
                    file2_region=func_b.region,
                    kgram_count=func_a.region.line_count,
                    plagiarism_type=PlagiarismType.SEMANTIC,
                    similarity=0.95,
                    description=f"Semantically equivalent functions: {func_a.name} ≈ {func_b.name}",
                )
                matches.append(match)
                used_b.add(id(func_b))
                break

        return matches

    def _extract_functions(self, parsed: ParsedFile) -> list[FunctionInfo]:
        """Extract functions using legacy robust implementation (both struct & semantic hashes)."""
        from plagiarism_core.plagiarism_detector import _extract_functions as legacy_extract

        legacy_funcs = legacy_extract(parsed.get_root_node(), parsed.source_bytes, parsed.language)
        funcs = []
        for f in legacy_funcs:
            region = Region(start=Point(f["start_line"], 0), end=Point(f["end_line"], 0))
            funcs.append(
                FunctionInfo(
                    name=f["name"],
                    qualified_name=f["name"],
                    region=region,
                    structural_hash=f["struct_hash"],
                    semantic_hash=f["semantic_hash"],
                    node=f["node"],
                )
            )
        return funcs

    def _compute_semantic_hash(self, parsed: ParsedFile, func_node) -> str:
        """Compute semantic hash for a function node."""
        # Use a similar fallback as in structural matcher
        types = []
        from ..normalization.canonicalizer import SemanticCanonicalizer

        def walk(n):
            sem_type = SemanticCanonicalizer.SEMANTIC_MAP.get(n.type, n.type)
            if sem_type not in SemanticCanonicalizer.IGNORABLE_TYPES:
                types.append(sem_type)
            for c in n.children:
                walk(c)

        walk(func_node)
        type_str = "->".join(types)
        import hashlib

        return hashlib.md5(type_str.encode()).hexdigest()[:16]

    def _extract_name(self, node, source_bytes) -> str | None:
        """Extract identifier name."""
        for sub in node.children:
            if sub.type == "identifier":
                return source_bytes[sub.start_byte : sub.end_byte].decode("utf-8", errors="ignore")
            if sub.type == "function_definition":
                return self._extract_name(sub, source_bytes)
        return None
