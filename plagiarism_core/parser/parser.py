"""Parser helpers for tree-sitter."""

from typing import Any, Optional, Tuple

from tree_sitter import Language, Parser, Tree

from .languages import get_language, detect_language_from_extension, get_supported_languages


class CodeParser:
    """Unified parser with language support."""

    def __init__(self):
        self._languages: dict[str, Language] = {}
        # Preload all languages lazily

    def get_language(self, lang: str) -> Language:
        """Get tree-sitter Language object for given language code."""
        if lang not in self._languages:
            self._languages[lang] = get_language(lang)
        return self._languages[lang]

    def detect_language(self, filename: str) -> str:
        """Detect language from file extension."""
        return detect_language_from_extension(filename)

    def parse(self, source: str, lang: str) -> Tuple[Tree, bytes]:
        """Parse source code string to AST + original bytes."""
        language = self.get_language(lang)
        parser = Parser(language)  # create new parser with language
        source_bytes = source.encode("utf-8")
        tree = parser.parse(source_bytes)
        return tree, source_bytes

    def parse_file(self, path: str, lang: Optional[str] = None) -> Tuple[Tree, bytes]:
        """Parse file to AST + bytes. Auto-detects language if not specified."""
        if lang is None:
            lang = self.detect_language(path)
        with open(path, encoding="utf-8", errors="ignore") as f:
            source = f.read()
        return self.parse(source, lang)

    def extract_functions(self, tree: Tree, source_bytes: bytes, lang: str) -> list[dict]:
        """
        Extract all function definitions from AST.

        Returns list of dicts with keys:
            start_line, end_line, start_byte, end_byte
        """
        profile = get_language_profile(lang)
        function_types = profile.get_function_node_types()
        functions = []

        def visit(node: Any) -> None:
            if node.type in function_types:
                functions.append({
                    "start_line": node.start_point[0],
                    "end_line": node.end_point[0],
                    "start_byte": node.start_byte,
                    "end_byte": node.end_byte,
                })
            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return functions

    def get_supported_languages(self) -> list[str]:
        """Get list of supported language codes."""
        return get_supported_languages()


# Convenience functions for backward compatibility
_default_parser = CodeParser()


def parse_file(path: str, lang: Optional[str] = None) -> Tuple[Tree, bytes]:
    """Parse a file and return (tree, source_bytes)."""
    return _default_parser.parse_file(path, lang)


def parse_string(source: str, lang: str = "python") -> Tuple[Tree, bytes]:
    """Parse a source string and return (tree, source_bytes)."""
    return _default_parser.parse(source, lang)


def get_language_obj(lang: str) -> Language:
    """Get tree-sitter Language object."""
    return _default_parser.get_language(lang)


def detect_language(filename: str) -> str:
    """Detect language from file extension."""
    return _default_parser.detect_language(filename)
