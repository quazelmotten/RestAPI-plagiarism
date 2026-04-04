"""
Tokenization for plagiarism detection.

Converts source code into a stream of tokens for fingerprinting.
"""

from dataclasses import dataclass
from typing import ClassVar

from tree_sitter import Node

from .parser import parse_string_once as _parse_string_once


@dataclass(frozen=True)
class Token:
    """A token extracted from source."""

    type: str
    value: str
    line: int
    col: int


class Tokenizer:
    """Tokenizes source code for fingerprinting."""

    TOKEN_TYPE_MAP: ClassVar[dict[str, str]] = {
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
        "identifier": "IDENT",
        "field_identifier": "IDENT",
        "type_identifier": "IDENT",
        "namespace_identifier": "IDENT",
        "property_identifier": "IDENT",
        "shorthand_property_identifier": "IDENT",
        "binary_operator": "OP",
        "unary_operator": "OP",
        "comparison_operator": "OP",
        "boolean_operator": "OP",
        "assignment_operator": "OP",
        "update_expression": "OP",
        "ternary_operator": "OP",
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
        "func": "KW",
        "defer": "KW",
        "go": "KW",
        "select": "KW",
        "chan": "KW",
        "map": "KW",
        "range": "KW",
        "package": "KW",
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

    def __init__(self, source, lang_code: str = "python", use_semantic_types: bool = False):
        self.use_semantic_types = use_semantic_types
        if hasattr(source, "get_root_node") and hasattr(source, "source_bytes"):
            self.tree = source.tree if hasattr(source, "tree") else None
            self.source_bytes = source.source_bytes
            self.lang_code = getattr(source, "language", lang_code)
            if self.tree is None:
                self.tree, _ = _parse_string_once(
                    source.source_bytes.decode("utf-8", errors="ignore"),
                    self.lang_code,
                )
        else:
            self.lang_code = lang_code
            self.tree, self.source_bytes = _parse_string_once(source, lang_code)

    def tokenize(self) -> list[Token]:
        tokens = []
        self._visit_node(self.tree.root_node, tokens)
        return tokens

    def _visit_node(self, node: Node, tokens: list[Token]) -> None:
        token_type = self._get_token_type(node)
        if token_type is not None:
            line = node.start_point[0]
            col = node.start_point[1]
            value = (
                self.source_bytes[node.start_byte : node.end_byte]
                .decode("utf-8", errors="ignore")
                .strip()
            )
            tokens.append(Token(type=token_type, value=value, line=line, col=col))
        for child in node.children:
            self._visit_node(child, tokens)

    def _get_token_type(self, node: Node) -> str | None:
        node_type = node.type
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
        if self.use_semantic_types:
            from ..canonicalizer import SEMANTIC_NODE_MAP

            semantic_type = SEMANTIC_NODE_MAP.get(node_type)
            if semantic_type:
                return semantic_type
        if node_type in self.TOKEN_TYPE_MAP:
            return self.TOKEN_TYPE_MAP[node_type]
        return node_type.upper()


def tokenize(source: str, lang_code: str = "python", use_semantic: bool = False) -> list[Token]:
    """Convenience function to tokenize source code."""
    tokenizer = Tokenizer(source, lang_code, use_semantic_types=use_semantic)
    return tokenizer.tokenize()
