"""
Semantic line matching matcher (Type 4).

Matches lines that are semantically equivalent after canonicalization.
Applies Type 4 transformations (for↔while, comprehension↔loop, etc.).
"""

import re

from ..models import Match, PlagiarismType, Point, Region
from ..parsing.parser import ParsedFile
from .base import BaseMatcher

# Language-specific keyword sets — identifiers not in these sets get replaced with ID
_LANGUAGE_KEYWORDS: dict[str, frozenset[str]] = {
    "python": frozenset(
        {
            "for",
            "while",
            "if",
            "else",
            "elif",
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
            "async",
            "await",
            "raise",
            "assert",
            "global",
            "nonlocal",
        }
    ),
    "cpp": frozenset(
        {
            "for",
            "while",
            "do",
            "if",
            "else",
            "return",
            "class",
            "struct",
            "try",
            "catch",
            "throw",
            "switch",
            "case",
            "default",
            "break",
            "continue",
            "goto",
            "true",
            "false",
            "nullptr",
            "null",
            "and",
            "or",
            "not",
            "&&",
            "||",
            "!",
            "new",
            "delete",
            "this",
            "const",
            "auto",
            "void",
            "int",
            "float",
            "double",
            "char",
            "bool",
            "public",
            "private",
            "protected",
            "virtual",
            "override",
            "final",
            "template",
            "typename",
            "namespace",
            "using",
            "static",
            "extern",
            "inline",
            "constexpr",
            "noexcept",
            "volatile",
            "mutable",
            "explicit",
            "friend",
            "typedef",
            "enum",
            "union",
        }
    ),
    "c": frozenset(
        {
            "for",
            "while",
            "do",
            "if",
            "else",
            "return",
            "struct",
            "union",
            "enum",
            "switch",
            "case",
            "default",
            "break",
            "continue",
            "goto",
            "true",
            "false",
            "null",
            "&&",
            "||",
            "!",
            "const",
            "void",
            "int",
            "float",
            "double",
            "char",
            "static",
            "extern",
            "inline",
            "volatile",
            "register",
            "typedef",
            "sizeof",
        }
    ),
    "java": frozenset(
        {
            "for",
            "while",
            "do",
            "if",
            "else",
            "return",
            "class",
            "interface",
            "try",
            "catch",
            "finally",
            "throw",
            "throws",
            "switch",
            "case",
            "default",
            "break",
            "continue",
            "true",
            "false",
            "null",
            "&&",
            "||",
            "!",
            "new",
            "this",
            "super",
            "public",
            "private",
            "protected",
            "static",
            "final",
            "abstract",
            "synchronized",
            "volatile",
            "transient",
            "native",
            "extends",
            "implements",
            "instanceof",
            "void",
            "int",
            "float",
            "double",
            "char",
            "boolean",
            "byte",
            "short",
            "long",
            "import",
            "package",
        }
    ),
    "javascript": frozenset(
        {
            "for",
            "while",
            "do",
            "if",
            "else",
            "return",
            "class",
            "try",
            "catch",
            "finally",
            "throw",
            "switch",
            "case",
            "default",
            "break",
            "continue",
            "true",
            "false",
            "null",
            "undefined",
            "nan",
            "infinity",
            "&&",
            "||",
            "!",
            "new",
            "this",
            "delete",
            "typeof",
            "instanceof",
            "var",
            "let",
            "const",
            "function",
            "extends",
            "async",
            "await",
            "yield",
            "import",
            "export",
            "from",
            "void",
        }
    ),
    "typescript": frozenset(
        {
            "for",
            "while",
            "do",
            "if",
            "else",
            "return",
            "class",
            "interface",
            "try",
            "catch",
            "finally",
            "throw",
            "switch",
            "case",
            "default",
            "break",
            "continue",
            "true",
            "false",
            "null",
            "undefined",
            "nan",
            "infinity",
            "&&",
            "||",
            "!",
            "new",
            "this",
            "delete",
            "typeof",
            "instanceof",
            "var",
            "let",
            "const",
            "function",
            "extends",
            "implements",
            "async",
            "await",
            "yield",
            "import",
            "export",
            "from",
            "type",
            "enum",
            "namespace",
            "declare",
            "public",
            "private",
            "protected",
            "readonly",
            "void",
            "never",
            "unknown",
            "any",
        }
    ),
    "tsx": frozenset(
        {
            "for",
            "while",
            "do",
            "if",
            "else",
            "return",
            "class",
            "interface",
            "try",
            "catch",
            "finally",
            "throw",
            "switch",
            "case",
            "default",
            "break",
            "continue",
            "true",
            "false",
            "null",
            "undefined",
            "&&",
            "||",
            "!",
            "new",
            "this",
            "var",
            "let",
            "const",
            "function",
            "extends",
            "implements",
            "async",
            "await",
            "yield",
            "import",
            "export",
            "from",
            "type",
            "enum",
            "namespace",
            "void",
            "never",
            "unknown",
            "any",
        }
    ),
    "go": frozenset(
        {
            "for",
            "if",
            "else",
            "return",
            "switch",
            "case",
            "default",
            "break",
            "continue",
            "fallthrough",
            "true",
            "false",
            "nil",
            "&&",
            "||",
            "!",
            "defer",
            "go",
            "select",
            "chan",
            "map",
            "struct",
            "interface",
            "type",
            "func",
            "package",
            "import",
            "var",
            "const",
            "range",
            "int",
            "int8",
            "int16",
            "int32",
            "int64",
            "uint",
            "uint8",
            "uint16",
            "uint32",
            "uint64",
            "float32",
            "float64",
            "complex64",
            "complex128",
            "byte",
            "rune",
            "string",
            "bool",
        }
    ),
    "rust": frozenset(
        {
            "for",
            "while",
            "loop",
            "if",
            "else",
            "return",
            "match",
            "break",
            "continue",
            "true",
            "false",
            "&&",
            "||",
            "!",
            "fn",
            "let",
            "mut",
            "const",
            "static",
            "struct",
            "enum",
            "trait",
            "impl",
            "type",
            "pub",
            "use",
            "mod",
            "crate",
            "super",
            "self",
            "async",
            "await",
            "move",
            "ref",
            "dyn",
            "i8",
            "i16",
            "i32",
            "i64",
            "i128",
            "isize",
            "u8",
            "u16",
            "u32",
            "u64",
            "u128",
            "usize",
            "f32",
            "f64",
            "bool",
            "char",
            "str",
            "some",
            "none",
            "ok",
            "err",
        }
    ),
}


def _get_keywords_for_language(lang_code: str) -> frozenset[str]:
    """Get the keyword set for a language, falling back to Python keywords."""
    return _LANGUAGE_KEYWORDS.get(lang_code, _LANGUAGE_KEYWORDS["python"])


# Language-specific regex patterns for semantic normalization
def _apply_language_patterns(line: str, lang_code: str) -> str:
    """Apply language-specific regex patterns for semantic normalization."""

    # Common patterns across all languages
    line = re.sub(r"\s*(\+=|-=|\*=|/=|%=)\s*", " = ", line)
    line = re.sub(r"\s*(==|!=|<=|>=)\s*", " COMP ", line)
    line = re.sub(r"\s+(and|or|&&|\|\|)\s+", " BOOL_OP ", line)
    line = re.sub(r"\b\d+\.\d+\b", "FLOAT", line)
    line = re.sub(r"\b\d+\b", "NUM", line)

    # String literals — handle multiple quote styles
    line = re.sub(r'""".*?"""', "STR", line, flags=re.DOTALL)
    line = re.sub(r"'''.*?'''", "STR", line, flags=re.DOTALL)
    line = re.sub(r'"[^"]*"', "STR", line)
    line = re.sub(r"'[^']*'", "STR", line)

    # C++/C/Java/JS: single char literals
    if lang_code in ("cpp", "c", "java", "javascript", "typescript", "tsx"):
        line = re.sub(r"'.'", "CHAR", line)

    # C++/C: pointer and reference operators
    if lang_code in ("cpp", "c"):
        line = re.sub(r"->", " ARROW ", line)
        line = re.sub(r"::", " SCOPE ", line)

    # Go: short variable declaration
    if lang_code == "go":
        line = re.sub(r":=", " = ", line)

    # Rust: mutable binding
    if lang_code == "rust":
        line = re.sub(r"\blet\s+mut\b", "LET_MUT", line)

    # Loop normalization (language-aware)
    if lang_code == "python":
        line = re.sub(r"^\s*for\s+", "LOOP ", line)
        line = re.sub(r"^\s*while\s+", "LOOP ", line)
    elif lang_code in ("cpp", "c", "java"):
        line = re.sub(r"^\s*for\s*\(", "LOOP(", line)
        line = re.sub(r"^\s*for\s*\(", "LOOP(", line)
        line = re.sub(r"^\s*while\s*\(", "LOOP(", line)
        line = re.sub(r"^\s*do\s*\{", "LOOP{", line)
    elif lang_code == "go":
        line = re.sub(r"^\s*for\b", "LOOP", line)
    elif lang_code == "rust":
        line = re.sub(r"^\s*for\b", "LOOP", line)
        line = re.sub(r"^\s*while\b", "LOOP", line)
        line = re.sub(r"^\s*loop\b", "LOOP", line)
    else:
        line = re.sub(r"^\s*for\s+", "LOOP ", line)
        line = re.sub(r"^\s*while\s+", "LOOP ", line)

    # Return normalization
    line = re.sub(r"^\s*return\s+", "RETURN ", line)

    # Conditional normalization
    line = re.sub(r"^\s*if\s+", "COND ", line)
    line = re.sub(r"^\s*elif\s+", "COND ", line)

    # C++/Java/JS ternary: already handled by COMP above

    # C++ stream operators (cout/cin)
    if lang_code in ("cpp", "c"):
        line = re.sub(r"<<", " OUT ", line)
        line = re.sub(r">>", " IN ", line)

    return line


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
        canonical_a = self._canonicalize_file(file_a)
        canonical_b = self._canonicalize_file(file_b)

        matches = self._find_matching_lines(
            canonical_a,
            canonical_b,
            file_a,
            file_b,
            covered_a,
            covered_b,
            min_length=self.config.min_match_lines,
        )

        for m in matches:
            object.__setattr__(m, "plagiarism_type", PlagiarismType.SEMANTIC)
            if not m.description:
                object.__setattr__(m, "description", "Semantic equivalence")

        return matches

    def _canonicalize_file(self, parsed: ParsedFile) -> list[str]:
        """
        Canonicalize each line of the file to a semantic IR string.

        Uses language-specific keyword sets and patterns.
        """
        source = parsed.source_bytes.decode("utf-8", errors="ignore")
        lines = source.splitlines()
        lang_code = getattr(parsed, "language", "python")
        keywords = _get_keywords_for_language(lang_code)

        normalized = []
        for line in lines:
            line_norm = line.strip().lower()

            # Apply language-specific patterns
            line_norm = _apply_language_patterns(line_norm, lang_code)

            # Replace identifiers (not keywords) with ID
            tokens = line_norm.split()
            new_tokens = []
            for tok in tokens:
                if tok in keywords:
                    new_tokens.append(tok.upper())
                elif tok in (
                    "COMP",
                    "BOOL_OP",
                    "LOOP",
                    "RETURN",
                    "COND",
                    "NUM",
                    "FLOAT",
                    "STR",
                    "CHAR",
                    "OUT",
                    "IN",
                    "ARROW",
                    "SCOPE",
                    "LET_MUT",
                ):
                    new_tokens.append(tok)
                elif tok.startswith("LOOP(") or tok.startswith("LOOP{"):
                    new_tokens.append("LOOP")
                elif tok.strip():
                    new_tokens.append("ID")
            normalized.append(" ".join(new_tokens))
        return normalized

    def _is_trivial_line(self, canonical_line: str) -> bool:
        """Check if a canonical line is too generic to be meaningful.

        Rejects lines that are just boilerplate patterns like:
        - Type declarations: int x; double y;
        - Simple assignments: a = b; x = 0;
        - Bare for/while/return with no body content
        - Lines with only keywords and single ID
        """
        tokens = canonical_line.split()
        if not tokens:
            return True

        # Trivial: only 1-2 tokens
        if len(tokens) <= 2:
            return True

        # Trivial: all tokens are the same structural keyword
        unique_tokens = set(tokens)
        structural_only = {"LOOP", "RETURN", "COND", "ID", "NUM", "STR", "CHAR"}
        if unique_tokens <= structural_only and len(unique_tokens) <= 2:
            return True

        # Trivial: just a single ID or ID pattern
        if tokens == ["ID"] or tokens == ["ID", "ID"] or tokens == ["ID", "NUM"]:
            return True

        # C/C++/Java/Go/Rust type declarations: TYPE ID, TYPE ID = NUM, etc.
        type_keywords = {
            "INT",
            "FLOAT",
            "DOUBLE",
            "CHAR",
            "BOOL",
            "VOID",
            "LONG",
            "SHORT",
            "STRING",
            "AUTO",
            "CONST",
            "SIGNED",
            "UNSIGNED",
            "STATIC",
            "EXTERN",
        }
        if len(tokens) >= 2:
            # Pattern: TYPE ID (possibly with = NUM or = ID)
            if tokens[0] in type_keywords and tokens[1] == "ID":
                # Only trivial if rest is just = NUM or = ID
                rest = tokens[2:]
                if not rest or rest == ["ID"] or rest == ["NUM"] or rest == ["STR"]:
                    return True
                if rest == ["ID", "ID"] or rest == ["ID", "NUM"]:
                    return True

        # Trivial: common boilerplate patterns
        trivial_patterns = [
            "LOOP ID",
            "LOOP ID NUM",
            "RETURN ID",
            "RETURN NUM",
            "COND ID",
            "COND ID COMP",
            "LOOP ID NUM COMP ID",
            "LOOP ID NUM COMP NUM",
            "LOOP ID COMP ID",
            "ID OP ID",
            "ID OP NUM",
            "ID = ID",
            "ID = NUM",
            "ID = STR",
            "ID . ID",
            "ID IN ID",
            "ID OUT ID",
        ]
        line_prefix = " ".join(tokens[:5])
        for pattern in trivial_patterns:
            if line_prefix.startswith(pattern):
                return True

        return False

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
            # Skip trivial lines that would produce false matches
            if self._is_trivial_line(lines_a[i]):
                i += 1
                continue
            j = 0
            while j < m:
                if j in visited_b:
                    j += 1
                    continue
                # Skip trivial lines in B too
                if self._is_trivial_line(lines_b[j]):
                    j += 1
                    continue
                match_len = 0
                while (
                    i + match_len < n
                    and j + match_len < m
                    and lines_a[i + match_len] == lines_b[j + match_len]
                    and (i + match_len) not in visited_a
                    and (j + match_len) not in visited_b
                    and not self._is_trivial_line(lines_a[i + match_len])
                ):
                    match_len += 1
                if match_len >= min_length:
                    match = Match(
                        file1_region=Region(start=Point(i, 0), end=Point(i + match_len - 1, 0)),
                        file2_region=Region(start=Point(j, 0), end=Point(j + match_len - 1, 0)),
                        kgram_count=match_len,
                        plagiarism_type=self.MATCH_TYPE,
                        similarity=0.9,
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
