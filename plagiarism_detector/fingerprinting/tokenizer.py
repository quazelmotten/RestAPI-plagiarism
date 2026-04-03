"""
Tokenization for plagiarism detection.

Converts source code into a stream of tokens for fingerprinting.
"""

from dataclasses import dataclass
from typing import ClassVar

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
        "number_literal": "LITERAL",
        "int_literal": "LITERAL",
        "float_literal": "LITERAL",
        "char_literal": "LITERAL",
        "string_literal": "LITERAL",
        "boolean_literal": "LITERAL",
        "decimal_integer_literal": "LITERAL",
        "decimal_floating_point_literal": "LITERAL",
        # Identifiers
        "identifier": "IDENT",
        "field_identifier": "IDENT",
        "type_identifier": "IDENT",
        "namespace_identifier": "IDENT",
        "property_identifier": "IDENT",
        "shorthand_property_identifier": "IDENT",
        # Operators
        "binary_operator": "OP",
        "unary_operator": "OP",
        "comparison_operator": "OP",
        "boolean_operator": "OP",
        "assignment_operator": "OP",
        "update_expression": "OP",
        "ternary_operator": "OP",
        # Python keywords
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
        # C/C++/Java/JS keywords
        "do": "KW",
        "switch": "KW",
        "case": "KW",
        "default": "KW",
        "break": "KW",
        "continue": "KW",
        "goto": "KW",
        "throw": "KW",
        "catch": "KW",
        "new": "KW",
        "delete": "KW",
        "this": "KW",
        "super": "KW",
        "extends": "KW",
        "implements": "KW",
        "interface": "KW",
        "enum": "KW",
        "typedef": "KW",
        "struct": "KW",
        "union": "KW",
        # C++ specific
        "namespace": "KW",
        "template": "KW",
        "typename": "KW",
        "virtual": "KW",
        "override": "KW",
        "final": "KW",
        "constexpr": "KW",
        "noexcept": "KW",
        "friend": "KW",
        "mutable": "KW",
        "explicit": "KW",
        "using": "KW",
        # Go specific
        "func": "KW",
        "defer": "KW",
        "go": "KW",
        "select": "KW",
        "chan": "KW",
        "map": "KW",
        "range": "KW",
        "package": "KW",
        # Rust specific
        "fn": "KW",
        "let": "KW",
        "mut": "KW",
        "match": "KW",
        "impl": "KW",
        "trait": "KW",
        "mod": "KW",
        "pub": "KW",
        "use": "KW",
        "crate": "KW",
        "self": "KW",
        "ref": "KW",
        "move": "KW",
        # Type keywords
        "void": "KW",
        "const": "KW",
        "static": "KW",
        "extern": "KW",
        "volatile": "KW",
        "register": "KW",
        "inline": "KW",
        "auto": "KW",
        "public": "KW",
        "private": "KW",
        "protected": "KW",
        "abstract": "KW",
        "synchronized": "KW",
        "transient": "KW",
        "native": "KW",
        "var": "KW",
        "function": "KW",
        "type": "KW",
        "declare": "KW",
        "readonly": "KW",
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
        "&&": "OP",
        "||": "OP",
        "!": "OP",
        "++": "OP",
        "--": "OP",
        "+=": "OP",
        "-=": "OP",
        "*=": "OP",
        "/=": "OP",
        "%=": "OP",
        "->": "OP",
        "::": "OP",
        "=>": "OP",
        "?": "OP",
        "<<": "OP",
        ">>": "OP",
        "&": "OP",
        "|": "OP",
        "^": "OP",
        "~": "OP",
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
