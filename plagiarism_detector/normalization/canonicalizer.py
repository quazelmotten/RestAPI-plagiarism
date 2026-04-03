"""
Semantic canonicalization for Type 4 detection.

Converts AST to a normalized intermediate representation (IR) that maps semantically
equivalent constructs to the same canonical form.
"""

from dataclasses import dataclass
from typing import ClassVar

from tree_sitter import Node

from ..parsing.parser import ParsedFile


@dataclass(frozen=True)
class IRNode:
    """A node in the intermediate representation."""

    type: str
    children: list["IRNode"] = ()
    value: str | None = None  # for literals, identifiers, etc.

    def __str__(self) -> str:
        return self._to_string()

    def _to_string(self, indent: int = 0) -> str:
        """Serialize IR to string (for hashing/comparison)."""
        prefix = "  " * indent
        if self.children:
            children_str = " ".join(child._to_string(indent + 1) for child in self.children)
            return f"{prefix}({self.type} {children_str})"
        else:
            value_part = f" {self.value}" if self.value else ""
            return f"{prefix}({self.type}{value_part})"


class SemanticCanonicalizer:
    """Converts AST to semantic canonical IR."""

    # Mapping from raw AST node types to semantic types
    SEMANTIC_MAP: ClassVar[dict[str, str]] = {
        "for_statement": "LOOP_FOR",
        "while_statement": "LOOP_WHILE",
        "do_statement": "LOOP_DO",
        "for_in_statement": "LOOP_FOR_IN",
        "enhanced_for_statement": "LOOP_ENHANCED_FOR",
        "list_comprehension": "COMPREHENSION_LIST",
        "generator_expression": "COMPREHENSION_GENERATOR",
        "set_comprehension": "COMPREHENSION_SET",
        "dict_comprehension": "COMPREHENSION_DICT",
        "fstring": "STRING_INTERPOLATION",
        "string": "STRING_LITERAL",  # tree-sitter uses 'string' for f-strings in Python
        "lambda": "FUNCTION_LITERAL",
        "lambda_expression": "FUNCTION_LITERAL",
        "augmented_assignment": "ASSIGN_AUGMENTED",
        "augmented_assignment_expression": "ASSIGN_AUGMENTED",
        "comparison_operator": "OP_COMPARISON",
        "boolean_operator": "OP_BOOLEAN",
        "binary_operator": "OP_BINARY",
        "unary_operator": "OP_UNARY",
    }

    IGNORABLE_TYPES: ClassVar[set[str]] = {
        "comment",
        "line_continue",
        "indent",
        "dedent",
        "NEWLINE",
        "END_MARKER",
        "whitespace",
    }

    def __init__(self, parsed_file: ParsedFile):
        self.parsed = parsed_file
        self.node_counter = 0

    def canonicalize(self) -> str:
        """
        Convert AST to canonical IR string.

        Returns:
            Canonical IR representation as string (suitable for hashing)
        """
        root = self.parsed.get_root_node()
        ir_root = self._convert_node(root)
        return str(ir_root)

    def _convert_node(self, node: Node) -> IRNode:
        """Convert a tree-sitter node to an IRNode."""
        # Skip ignorable nodes
        if node.type in self.IGNORABLE_TYPES:
            # Merge children if any
            children = []
            for child in node.children:
                if child.type not in self.IGNORABLE_TYPES:
                    children.append(self._convert_node(child))
            if len(children) == 1:
                return children[0]
            return IRNode("SEQ", children) if children else IRNode("EMPTY")

        # Check for semantic mapping
        semantic_type = self.SEMANTIC_MAP.get(node.type)
        if semantic_type:
            # Map to semantic type; normalize children
            children = [self._convert_node(child) for child in node.children]
            return IRNode(semantic_type, children=children)

        # Handle literals
        if node.type in ("string", "integer", "float", "char", "true", "false", "nil", "null"):
            value = self.parsed.get_source_text(node).strip()
            return IRNode("LITERAL", value=value)

        # Handle identifiers
        if node.type == "identifier":
            value = self.parsed.get_source_text(node)
            return IRNode("IDENT", value=value)

        # Handle operators
        if node.type in (
            "binary_operator",
            "unary_operator",
            "comparison_operator",
            "boolean_operator",
        ):
            value = self.parsed.get_source_text(node).strip()
            return IRNode("OP", value=value)

        # Default: convert children recursively
        children = [self._convert_node(child) for child in node.children]
        if not children:
            return IRNode("EMPTY")
        return IRNode(node.type, children=children)
