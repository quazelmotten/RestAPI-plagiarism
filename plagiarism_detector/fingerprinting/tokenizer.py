"""
Tokenization for plagiarism detection.

Converts source code into a stream of tokens for fingerprinting.
"""

from dataclasses import dataclass
from typing import ClassVar, Iterator

from tree_sitter import Node

from ..parsing.parser import ParsedFile


@dataclass(frozen=True)
class Token:
    """A token extracted from source."""

    type: str
    value: str
    line: int
    col: int


class Tokenizer:
    """Tokenizes source code for fingerprinting."""

    # Token type mappings based on AST node types or regex patterns
    TOKEN_TYPE_MAP: ClassVar[dict[str, str]] = {
        # Literals
        "string": "LITERAL",
        "integer": "LITERAL",
        "float": "LITERAL",
        "char": "LITERAL",
        "true": "LITERAL",
        "false": "LITERAL",
        "nil": "LITERAL",
        "null": "LITERAL",
        # Identifiers
        "identifier": "IDENT",
        # Operators
        "binary_operator": "OP",
        "unary_operator": "OP",
        "comparison_operator": "OP",
        "boolean_operator": "OP",
        "assignment_operator": "OP",
        # Keywords
        "if": "KW",
        "else": "KW",
        "for": "KW",
        "while": "KW",
        "return": "KW",
        "def": "KW",
        "class": "KW",
        "try": "KW",
        "except": "KW",
        "finally": "KW",
        "with": "KW",
        "as": "KW",
        "import": "KW",
        "from": "KW",
        "lambda": "KW",
        "yield": "KW",
        "async": "KW",
        "await": "KW",
        # Delimiters
        "(": "DELIM",
        ")": "DELIM",
        "[": "DELIM",
        "]": "DELIM",
        "{": "DELIM",
        "}": "DELIM",
        ",": "DELIM",
        ".": "DELIM",
        ";": "DELIM",
        ":": "DELIM",
        "+": "OP",
        "-": "OP",
        "*": "OP",
        "/": "OP",
        "%": "OP",
        "=": "OP",
        "==": "OP",
        "!=": "OP",
        "<": "OP",
        ">": "OP",
        "<=": "OP",
        ">=": "OP",
        "and": "OP",
        "or": "OP",
        "not": "OP",
        "is": "OP",
        "in": "OP",
    }

    def __init__(self, parsed_file: ParsedFile, use_semantic_types: bool = False):
        """
        Initialize tokenizer.

        Args:
            parsed_file: ParsedFile with syntax tree
            use_semantic_types: If True, use semantic node type mapping; else use raw types
        """
        self.parsed = parsed_file
        self.use_semantic_types = use_semantic_types

    def tokenize(self) -> list[Token]:
        """
        Tokenize the source code.

        Returns:
            List of Token objects in source order
        """
        tokens = []
        self._visit_node(self.parsed.get_root_node(), tokens)
        return tokens

    def _visit_node(self, node: Node, tokens: list[Token]) -> None:
        """Recursively visit AST nodes and collect tokens."""
        # Determine token type
        token_type = self._get_token_type(node)

        if token_type is not None:
            # Get position
            line = node.start_point[0]
            col = node.start_point[1]
            value = self.parsed.get_source_text(node).strip()

            tokens.append(Token(type=token_type, value=value, line=line, col=col))

        # Recurse to children
        for child in node.children:
            self._visit_node(child, tokens)

    def _get_token_type(self, node: Node) -> str | None:
        """Determine token type for a node."""
        node_type = node.type

        # Skip ignorable types
        if node_type in (
            "comment",
            "line_continue",
            "indent",
            "dedent",
            "NEWLINE",
            "END_MARKER",
            "whitespace",
        ):
            return None

        # Use semantic mapping if requested
        if self.use_semantic_types:
            from .normalization.canonicalizer import SemanticCanonicalizer

            semantic_type = SemanticCanonicalizer.SEMANTIC_MAP.get(node_type)
            if semantic_type:
                return semantic_type

        # Look up in token type map
        if node_type in self.TOKEN_TYPE_MAP:
            return self.TOKEN_TYPE_MAP[node_type]

        # For unknown types, use the node type itself as category
        return node_type.upper()


def tokenize(parsed_file: ParsedFile, use_semantic: bool = False) -> list[Token]:
    """Convenience function to tokenize a parsed file."""
    tokenizer = Tokenizer(parsed_file, use_semantic=use_semantic)
    return tokenizer.tokenize()
