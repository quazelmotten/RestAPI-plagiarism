"""
Semantic line matching matcher (Type 4).

Matches lines that are semantically equivalent after canonicalization.
Applies Type 4 transformations (for↔while, comprehension↔loop, etc.).
"""

from ..normalization.canonicalizer import SemanticCanonicalizer
from ..parsing.parser import ParsedFile
from .base import BaseMatcher
from ..models import Match, PlagiarismType, Region, Point


class SemanticLineMatcher(BaseMatcher):
    """Matches lines after semantic canonicalization (Type 4)."""

    MATCH_TYPE = PlagiarismType.SEMANTIC

    def run(
        self, file_a: ParsedFile, file_b: ParsedFile, covered_a: set[int], covered_b: set[int]
    ) -> list[Match]:
        """
        Find semantically equivalent lines.

        This matcher operates on the remaining (uncovered) lines after
        exact, renamed, and structural matchers have run.
        """
        # For simplicity, we'll canonicalize each file to a sequence of line-level IR strings.
        # In a more advanced version, we could do block-level canonicalization.

        # Convert each file to a list of canonical IR strings per line
        canonical_a = self._canonicalize_file(file_a)
        canonical_b = self._canonicalize_file(file_b)

        # Now find matching lines between these canonical sequences
        matches = self._find_matching_lines(
            canonical_a,
            canonical_b,
            file_a,
            file_b,
            covered_a,
            covered_b,
            min_length=self.config.min_match_lines,
        )

        # Set type to SEMANTIC
        for m in matches:
            object.__setattr__(m, "plagiarism_type", PlagiarismType.SEMANTIC)
            if not m.description:
                object.__setattr__(m, "description", "Semantic equivalence")

        return matches

    def _canonicalize_file(self, parsed: ParsedFile) -> list[str]:
        """
        Canonicalize each line of the file to a semantic IR string.

        This is a simplified approach: line-by-line canonicalization.
        More precise version would work on AST statements.
        """
        # Get the source lines with original line numbers
        source = parsed.source_bytes.decode("utf-8", errors="ignore")
        lines = source.splitlines()

        # For each line, parse its AST and convert to canonical IR?
        # That would be expensive. Instead, we can apply some heuristic transformations:
        #  - Replace known patterns: "for x in y:" -> "LOOP_FOR_VAR_ITER"
        #  - Replace comparison operators with canonical form
        #  - Replace augmented assignments with simple assignment
        # But the proper way is to use the SemanticCanonicalizer on the whole AST
        # and then map IR nodes back to line numbers.

        # Since this is a complex problem, I'll implement a simplified version that works
        # on the textual level with regex replacements for common Type 4 patterns.
        # In full implementation, the canonicalizer would produce IR with source mappings.

        # Simplified: normalize each line to lowercase, normalize operators, ignore variable names
        normalized = []
        for line in lines:
            # Basic normalization: strip, lower, normalize operators and keywords
            line_norm = line.strip().lower()
            # Replace augmented assignments: +=, -=, etc. -> =
            import re

            line_norm = re.sub(r"\s*(\+=-|=-\*|/=|%=|\*\*=)\s*", " = ", line_norm)
            # Replace comparison operators with placeholder
            line_norm = re.sub(r"\s*(==|!=|<=|>=|<|>)\s*", " COMP ", line_norm)
            # Replace boolean operators
            line_norm = re.sub(r"\s+(and|or|&&|\|)\s+", " BOOL_OP ", line_norm)
            # Replace for/while with LOOP
            line_norm = re.sub(r"^\s*for\s+", "LOOP ", line_norm)
            line_norm = re.sub(r"^\s*while\s+", "LOOP ", line_norm)
            # Replace return
            line_norm = re.sub(r"^\s*return\s+", "RETURN ", line_norm)
            # Replace if
            line_norm = re.sub(r"^\s*if\s+", "COND ", line_norm)
            # Replace literals with placeholders (keep type hint)
            line_norm = re.sub(r"\b\d+\b", "NUM", line_norm)
            line_norm = re.sub(r"\b\d+\.\d+\b", "FLOAT", line_norm)
            line_norm = re.sub(r'".*?"', "STR", line_norm)
            line_norm = re.sub(r"'.*?'", "STR", line_norm)
            # Replace identifiers (except keywords) with ID
            # This is tricky without parsing; but we can remove anything that looks like a variable
            # Actually, we already replaced numbers and strings; remaining words are mostly identifiers and keywords
            # Let's keep keywords known and replace rest
            keywords = {
                "for",
                "while",
                "if",
                "else",
                "return",
                "def",
                "class",
                "try",
                "except",
                "finally",
                "with",
                "as",
                "import",
                "from",
                "lambda",
                "yield",
                "in",
                "is",
                "not",
                "and",
                "or",
                "none",
                "true",
                "false",
                "pass",
                "break",
                "continue",
            }
            tokens = line_norm.split()
            new_tokens = []
            for tok in tokens:
                if tok in keywords:
                    new_tokens.append(tok.upper())
                elif tok in ("COMP", "BOOL_OP", "LOOP", "RETURN", "COND", "NUM", "FLOAT", "STR"):
                    new_tokens.append(tok)
                elif tok.strip():
                    new_tokens.append("ID")
            normalized.append(" ".join(new_tokens))
        return normalized

    def _find_matching_lines(
        self,
        lines_a: list[str],
        lines_b: list[str],
        file_a: ParsedFile,
        file_b: ParsedFile,
        covered_a: set[int],
        covered_b: set[int],
        min_length: int = 3,
    ) -> list[Match]:
        """Find contiguous matching canonical lines."""
        matches = []
        n, m = len(lines_a), len(lines_b)
        visited_a = set(covered_a)
        visited_b = set(covered_b)

        i = 0
        while i < n:
            if i in visited_a:
                i += 1
                continue
            j = 0
            while j < m:
                if j in visited_b:
                    j += 1
                    continue
                match_len = 0
                while (
                    i + match_len < n
                    and j + match_len < m
                    and lines_a[i + match_len] == lines_b[j + match_len]
                    and (i + match_len) not in visited_a
                    and (j + match_len) not in visited_b
                ):
                    match_len += 1
                if match_len >= min_length:
                    match = Match(
                        file1_region=Region(start=Point(i, 0), end=Point(i + match_len - 1, 0)),
                        file2_region=Region(start=Point(j, 0), end=Point(j + match_len - 1, 0)),
                        kgram_count=match_len,
                        plagiarism_type=self.MATCH_TYPE,
                        similarity=0.9,  # approximate
                        description="Semantic line match",
                    )
                    matches.append(match)
                    for k in range(match_len):
                        visited_a.add(i + k)
                        visited_b.add(j + k)
                    j += match_len
                else:
                    j += 1
            i += 1

        return matches
