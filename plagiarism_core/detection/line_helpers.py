"""Line normalization helpers."""

from ..fingerprints import stable_hash


def _strip_comments(line: str, lang_code: str = "python") -> str:
    """Remove single-line comments, respecting string literals.

    Supports:
      - Python/Ruby/Bash: #
      - C/C++/Java/JS/TS/Go/Rust: //
      - SQL/Lua: --
    Block comments (/* */) are not handled per-line — they are
    uncommon in student submissions and would require cross-line state.
    """
    # Choose the line-comment marker for this language
    if lang_code in ("python", "ruby", "perl", "bash", "shell"):
        comment_prefix = "#"
    elif lang_code in ("sql", "lua"):
        comment_prefix = "--"
    else:
        # C, cpp, java, javascript, typescript, go, rust, etc.
        comment_prefix = "//"

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
            elif line[i : i + len(comment_prefix)] == comment_prefix and (
                i == 0 or line[i - 1] != "\\"
            ):
                break
            else:
                result.append(ch)
        else:
            result.append(ch)
            if ch == string_char and (i == 0 or line[i - 1] != "\\"):
                in_string = False
        i += 1
    return "".join(result).strip()


def _make_shadow_lines(
    source: str, lang_code: str = "python", tree=None, source_bytes: bytes = None
) -> list[str]:
    """Produce identifier-normalized lines (shadow version).

    Uses global normalization so that rename detection at the line level
    works correctly (different function names produce different VAR_N).
    Per-function normalization is used separately for scope-local shadow
    exclusion in _semantic_line_matches.
    """
    from ..canonicalizer import (
        _normalize_identifiers_from_tree,
        normalize_identifiers,
    )

    if tree is not None and source_bytes is not None:
        normalized = _normalize_identifiers_from_tree(tree, source_bytes, source)
    else:
        normalized = normalize_identifiers(source, lang_code)
    return normalized.split("\n")


def _make_exact_lines(source: str, lang_code: str = "python") -> list[str]:
    """Produce whitespace-and-comment-normalized lines."""
    import re

    lines = []
    for line in source.split("\n"):
        stripped = _strip_comments(line, lang_code)
        if not stripped:
            lines.append("")
        else:
            lines.append(re.sub(r"\s+", " ", stripped))
    return lines


def _line_hash(line: str) -> int:
    """Fast int hash for a normalized line using xxhash for consistency."""
    if not line:
        return 0
    return stable_hash(line)
