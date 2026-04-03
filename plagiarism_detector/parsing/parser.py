"""
Tree-sitter parser wrapper with caching and error handling.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from tree_sitter import Language, Parser, Tree

from ..languages import get_language_profile

if TYPE_CHECKING:
    from ..languages.base import LanguageProfile

# Cache for tree-sitter Language objects (expensive to create)
_language_cache: dict[str, Language] = {}
_language_lock = threading.Lock()


def get_tree_sitter_language(lang_code: str) -> Language:
    """Get or create a tree-sitter Language object for the given language code."""
    with _language_lock:
        if lang_code not in _language_cache:
            try:
                # Import language-specific tree-sitter modules dynamically
                if lang_code == "python":
                    import tree_sitter_python as ts_lang
                elif lang_code in ("c", "cpp"):
                    import tree_sitter_cpp as ts_lang
                elif lang_code == "java":
                    import tree_sitter_java as ts_lang
                elif lang_code == "javascript":
                    import tree_sitter_javascript as ts_lang
                elif lang_code == "typescript":
                    import tree_sitter_typescript as ts_lang
                elif lang_code == "tsx":
                    import tree_sitter_typescript as ts_lang

                    # TSX uses the typescript language but with JSX enabled
                    _language_cache[lang_code] = Language(ts_lang.language(), "typescript")
                    return _language_cache[lang_code]
                elif lang_code == "go":
                    import tree_sitter_go as ts_lang
                elif lang_code == "rust":
                    import tree_sitter_rust as ts_lang
                else:
                    raise ValueError(f"Unsupported language for tree-sitter: {lang_code}")

                if lang_code != "tsx":
                    _language_cache[lang_code] = Language(ts_lang.language())
            except ImportError as e:
                raise ImportError(
                    f"Tree-sitter parser for '{lang_code}' not installed. Install it with: pip install tree-sitter-{lang_code}"
                ) from e

        return _language_cache[lang_code]


@dataclass
class ParsedFile:
    """Result of parsing a file."""

    tree: Tree
    source_bytes: bytes
    language: str
    profile: LanguageProfile
    path: Path | None = None

    def get_root_node(self):
        """Get the root node of the syntax tree."""
        return self.tree.root_node

    def get_source_text(self, node) -> str:
        """Get source text for a node."""
        return self.source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


class ParserWrapper:
    """Wrapper around tree-sitter parser with caching and error handling."""

    @classmethod
    def parse(
        cls,
        source: str | bytes,
        lang_code: str,
        path: Path | None = None,
        timeout_ms: int = 5000,
    ) -> ParsedFile:
        """
        Parse source code with tree-sitter.

        Args:
            source: Source code string or bytes
            lang_code: Language code (e.g., "python", "java")
            path: Optional file path for error messages
            timeout_ms: Parse timeout in milliseconds (not currently enforced)

        Returns:
            ParsedFile object with tree and metadata

        Raises:
            ValueError: If language is not supported
            SyntaxError: If parsing fails
            UnicodeDecodeError: If source encoding is invalid
        """
        if isinstance(source, str):
            source_bytes = source.encode("utf-8")
        else:
            source_bytes = source

        # Get language and create parser with language
        ts_language = get_tree_sitter_language(lang_code)
        parser = Parser(ts_language)

        # Parse
        try:
            tree = parser.parse(source_bytes)
        except Exception as e:
            raise SyntaxError(f"Failed to parse {lang_code} code: {e}") from e

        # Check for errors in the tree
        root_node = tree.root_node
        if root_node.has_error:
            error_msg = f"Syntax error in {lang_code} code"
            if path:
                error_msg = f"{error_msg} at {path}"
            raise SyntaxError(error_msg)

        profile = get_language_profile(lang_code)

        return ParsedFile(
            tree=tree,
            source_bytes=source_bytes,
            language=lang_code,
            profile=profile,
            path=path,
        )

    @classmethod
    def parse_file(cls, file_path: Path | str, encoding: str = "utf-8") -> ParsedFile:
        """
        Parse a file from disk.

        Args:
            file_path: Path to the file
            encoding: File encoding (default: utf-8)

        Returns:
            ParsedFile object with tree and metadata
        """
        path = Path(file_path)
        try:
            with open(path, "rb") as f:
                source_bytes = f.read()
        except FileNotFoundError:
            raise
        except UnicodeDecodeError as e:
            raise UnicodeDecodeError(f"Failed to read {path}: invalid {encoding} encoding") from e

        # Detect language from extension or use provided
        lang_code = _infer_language_from_path(path)

        return cls.parse(source_bytes, lang_code, path=path)

    @classmethod
    def reset(cls) -> None:
        """Reset parser cache (useful for testing)."""
        with cls._parser_lock:
            cls._parser = None


def _infer_language_from_path(path: Path) -> str:
    """Infer language code from file extension."""
    ext = path.suffix.lower()
    mapping = {
        ".py": "python",
        ".java": "java",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".hpp": "cpp",
        ".hh": "cpp",
        ".hxx": "cpp",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "tsx",
        ".go": "go",
        ".rs": "rust",
    }
    if ext in mapping:
        return mapping[ext]
    raise ValueError(f"Could not infer language from extension: {ext}")
