"""Semantic node type maps and shared helpers for canonicalization."""

from tree_sitter import Node

SEMANTIC_NODE_MAP: dict[str, str] = {
    "for_statement": "LOOP",
    "while_statement": "LOOP",
    "do_statement": "LOOP",
    "for_in_statement": "LOOP",
    "enhanced_for_statement": "LOOP",
    "for_range_loop": "LOOP",
    "for_expression": "LOOP",
    "loop_expression": "LOOP",
    "while_expression": "LOOP",
    "if_expression": "COND",
    "ternary_expression": "TERNARY",
    "conditional_expression": "TERNARY",
    "list_comprehension": "COLLECTION",
    "generator_expression": "COLLECTION",
    "set_comprehension": "COLLECTION",
    "dict_comprehension": "DICT_COLLECTION",
    "fstring": "STRING_FORMAT",
    "string": "STRING_FORMAT",
    "raw_string_literal": "STRING_FORMAT",
    "string_literal": "STRING_FORMAT",
    "interpreted_string_literal": "STRING_FORMAT",
    "lambda": "FUNCTION_LITERAL",
    "lambda_expression": "FUNCTION_LITERAL",
    "closure_expression": "FUNCTION_LITERAL",
    "func_literal": "FUNCTION_LITERAL",
    "arrow_function": "FUNCTION_LITERAL",
    "augmented_assignment": "ASSIGN",
    "augmented_assignment_expression": "ASSIGN",
    "update_expression": "ASSIGN",
    "inc_statement": "ASSIGN",
    "comparison_operator": "COMPARISON",
    "boolean_operator": "BOOLEAN_OP",
    "parenthesized_expression": "GROUP",
}

_IGNORABLE_NODE_TYPES: frozenset[str] = frozenset(
    {
        "comment",
        "line_continue",
        "indent",
        "dedent",
        "NEWLINE",
        "END_MARKER",
        "whitespace",
    }
)

_COMPARISON_OPS = frozenset({"==", "!=", "<", ">", "<=", ">="})
_ARITHMETIC_OPS = frozenset({"+", "-", "*", "/", "%", "//", "**"})
_LOGICAL_OPS = frozenset({"and", "or", "&&", "||", "!"})


def _semantic_node_type(node: Node) -> str:
    if node.type in SEMANTIC_NODE_MAP:
        return SEMANTIC_NODE_MAP[node.type]
    if node.type in _IGNORABLE_NODE_TYPES:
        return ""
    return node.type


def _get_child_by_type(node: Node, child_type: str) -> Node | None:
    for child in node.children:
        if child.type == child_type:
            return child
    return None


def _get_source_text(node: Node, source_bytes: bytes) -> str:
    return source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def _is_ignorable(node_type: str) -> bool:
    return node_type in _IGNORABLE_NODE_TYPES
