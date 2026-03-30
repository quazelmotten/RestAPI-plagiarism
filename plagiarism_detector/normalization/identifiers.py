"""
Scope-aware identifier normalization (wrapper around legacy implementation).

This module uses the proven legacy logic from the original monolithic detector
to ensure correct handling across all supported languages.
"""

from typing import ClassVar

from ..parsing.parser import ParsedFile


def normalize_identifiers(parsed_file: ParsedFile) -> str:
    """
    Normalize identifiers in source code, replacing them with VAR_N placeholders.

    Uses the legacy implementation for correctness and language coverage.

    Args:
        parsed_file: ParsedFile object with syntax tree and source bytes

    Returns:
        Normalized source code
    """
    # Delegate to the legacy normalize_identifiers function
    # from plagiarism_core.canonicalizer, which handles language-specific nuances.
    from plagiarism_core.canonicalizer import normalize_identifiers as legacy_normalize

    source = parsed_file.source_bytes.decode("utf-8", errors="ignore")
    lang = parsed_file.language
    return legacy_normalize(source, lang)
