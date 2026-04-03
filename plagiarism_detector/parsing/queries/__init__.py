"""
Query patterns for common AST operations using tree-sitter S-expressions.
"""

import pkgutil
from pathlib import Path
from typing import ClassVar

from tree_sitter import Query

from ..parser import get_tree_sitter_language


class QueryCache:
    """Cache for compiled tree-sitter queries."""

    _cache: ClassVar[dict[tuple[str, str], Query]] = {}
    _lock = __import__("threading").Lock()

    @classmethod
    def get_query(cls, lang_code: str, query_name: str) -> Query:
        """
        Get a compiled query for the given language and query name.

        Queries are loaded from the `queries/` directory within this package.
        Query files are named like: python.scm (for language python)
        Each file can contain multiple named patterns.

        Args:
            lang_code: Language code
            query_name: Name of the query pattern to extract from the file

        Returns:
            Compiled tree-sitter Query object

        Raises:
            FileNotFoundError: If query file doesn't exist
            ValueError: If query pattern not found in file
        """
        cache_key = (lang_code, query_name)
        with cls._lock:
            if cache_key not in cls._cache:
                # Load query source from package data
                query_file = f"{lang_code}.scm"
                try:
                    query_source = pkgutil.get_data(__name__, query_file)
                    if query_source is None:
                        # Try to read from filesystem (development mode)
                        query_path = Path(__file__).parent / query_file
                        if query_path.exists():
                            query_source = query_path.read_text().encode("utf-8")
                        else:
                            raise FileNotFoundError(f"Query file not found: {query_file}")
                except FileNotFoundError as e:
                    raise FileNotFoundError(
                        f"Query file for language '{lang_code}' not found"
                    ) from e

                query_source_str = query_source.decode("utf-8")

                # Extract the specific query pattern named `query_name`
                # Query files can have multiple patterns separated by blank lines or comments
                # Each pattern starts with a pattern like: (function_definition ...)
                # We look for pattern that captures @name, etc.
                # Actually, tree-sitter query files contain multiple patterns with capture names
                # We need to extract the portion that matches the query_name
                # For simplicity, we'll load the entire file as one query for now
                # More advanced: support multi-query files with `; @name` comments

                # Build query from source
                ts_language = get_tree_sitter_language(lang_code)
                query = Query(ts_language, query_source_str)
                cls._cache[cache_key] = query

            return cls._cache[cache_key]

    @classmethod
    def clear_cache(cls) -> None:
        """Clear query cache (for testing)."""
        with cls._lock:
            cls._cache.clear()


def extract_functions_with_query(tree, source_bytes, lang_code: str):
    """
    Extract function definitions using a pre-defined query.

    This replaces manual AST traversal with declarative pattern matching.

    Returns:
        List of dicts with keys: node, name, start_line, end_line, params (list of identifiers)
    """
    query = QueryCache.get_query(lang_code, "function_definitions")
    matches = query.matches(tree.root_node)

    functions = []
    for match in matches:
        # match is dict: capture_name -> (node, index)
        func_node = match.get("function")  # the full function node
        name_node = match.get("name")
        param_nodes = match.get("params", [])

        if func_node is None or name_node is None:
            continue

        name = source_bytes[name_node.start_byte : name_node.end_byte].decode(
            "utf-8", errors="ignore"
        )
        params = []
        for param_node in param_nodes:
            param_name = source_bytes[param_node.start_byte : param_node.end_byte].decode(
                "utf-8", errors="ignore"
            )
            params.append(param_name)

        functions.append(
            {
                "node": func_node,
                "name": name,
                "start_line": func_node.start_point[0],
                "end_line": func_node.end_point[0],
                "params": params,
            }
        )

    return functions
