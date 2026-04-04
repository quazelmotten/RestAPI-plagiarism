"""AST hashing, function extraction, and related helpers."""

from tree_sitter import Node

from ..canonicalizer import _get_child_by_type, _semantic_node_type
from ..fingerprints import stable_hash


class _FilteredNode:
    """Lightweight wrapper around a tree-sitter Node that overrides children.

    Used to present a filtered view of an AST node (e.g., parameters node
    with self/this removed) without modifying the original tree.
    """

    __slots__ = (
        "type",
        "start_point",
        "end_point",
        "start_byte",
        "end_byte",
        "children",
        "child_count",
        "is_named",
    )

    def __init__(self, node: Node, filtered_children: list):
        self.type = node.type
        self.start_point = node.start_point
        self.end_point = node.end_point
        self.start_byte = node.start_byte
        self.end_byte = node.end_byte
        self.children = filtered_children
        self.child_count = len(filtered_children)
        self.is_named = node.is_named


def _strip_self_from_params(node: Node, source_bytes: bytes, lang_code: str = "python") -> Node:
    """Return a view of a function node with self/this removed from parameters.

    For Python: removes the first 'self' identifier and its trailing comma.
    For Java/JS/TS: removes the first 'this' identifier (if present).
    Other languages: returns node unchanged.
    """
    if lang_code != "python":
        return node

    # Find the function_definition node (skip decorated_definition wrapper)
    fn_node = node
    while fn_node.type == "decorated_definition":
        found = False
        for child in fn_node.children:
            if child.type == "function_definition":
                fn_node = child
                found = True
                break
        if not found:
            return node

    # Find the parameters node
    params_node = None
    for child in fn_node.children:
        if child.type == "parameters":
            params_node = child
            break

    if params_node is None:
        return node

    children = list(params_node.children)
    if len(children) < 5:
        return node  # need at least ( self , x )

    # Check if first non-paren child is 'self' or 'this'
    first = children[1]
    if first.type != "identifier" or first.children:
        return node

    name = source_bytes[first.start_byte : first.end_byte].decode("utf-8", errors="ignore")
    if name not in ("self", "this"):
        return node

    # Verify there's a comma after it (multi-param method)
    if children[2].type != ",":
        return node  # only param, don't strip

    # Remove self and its trailing comma: [0]= (, [1]=self, [2]=,, [3]=x, [4]=)
    new_children = [children[0]] + children[3:]
    filtered_params = _FilteredNode(params_node, new_children)

    # Rebuild the function node's children with filtered params
    new_fn_children = []
    for child in fn_node.children:
        if child is params_node:
            new_fn_children.append(filtered_params)
        else:
            new_fn_children.append(child)

    if fn_node is node:
        return _FilteredNode(fn_node, new_fn_children)

    filtered_fn = _FilteredNode(fn_node, new_fn_children)
    # Rebuild decorated_definition children
    new_dec_children = []
    for child in node.children:
        if child is fn_node:
            new_dec_children.append(filtered_fn)
        else:
            new_dec_children.append(child)
    return _FilteredNode(node, new_dec_children)


def _hash_ast_subtree(node: Node, use_semantic: bool = False) -> int:
    """
    Hash a subtree's structure, optionally using semantic normalization.

    If use_semantic=True, semantically equivalent constructs (for/while loops,
    list comprehensions/map calls, etc.) produce the same hash, enabling better
    Type 4 detection at the AST level.

    With use_semantic=False (default), the function ignores identifier names,
    so two functions with different variable names produce identical hashes
    (for Type 2 detection).

    Operator and keyword leaf values are included in the hash so that
    functions with different operators (e.g., a+b vs a-b) produce different
    hashes, preventing incorrect function pairing.
    """
    if node.type == "comment":
        return 0

    # Get the effective node type for hashing
    if use_semantic:
        hash_type = _semantic_node_type(node) or node.type
    else:
        hash_type = node.type

    if not node.children:
        if hash_type == "identifier":
            return 0  # ignore names entirely
        # Include operator and keyword leaf values in the hash
        # so that +, -, *, /, ==, etc. produce different hashes
        leaf_value = hash_type
        if node.type in (
            "+",
            "-",
            "*",
            "/",
            "%",
            "//",
            "**",
            "==",
            "!=",
            "<",
            ">",
            "<=",
            ">=",
            "and",
            "or",
            "not",
            "is",
            "in",
        ):
            leaf_value = f"{hash_type}:{node.type}"
        return stable_hash(leaf_value)

    child_hashes = []
    for child in node.children:
        ch = _hash_ast_subtree(child, use_semantic)
        if ch:
            child_hashes.append(ch)

    if not child_hashes:
        return 0

    rep = hash_type + "(" + ",".join(str(h) for h in child_hashes) + ")"
    return stable_hash(rep)


def _hash_ast_subtree_semantic(node: Node) -> int:
    """
    Hash a subtree using semantic normalization (Approach A).

    Semantically equivalent code constructs produce identical hashes:
      - for loops and while loops → same hash (LOOP)
      - list comprehensions and map() calls → same hash (COLLECTION)
      - f-strings and .format() → same hash (STRING_FORMAT)
    """
    return _hash_ast_subtree(node, use_semantic=True)


def _get_function_node_types(lang_code: str) -> tuple[str, ...]:
    """Get function node types for a language from the profile registry."""
    from ..fingerprinting.languages import get_language_profile

    return get_language_profile(lang_code).function_node_types


def _get_class_node_types(lang_code: str) -> tuple[str, ...]:
    """Get class node types for a language from the profile registry."""
    from ..fingerprinting.languages import get_language_profile

    return get_language_profile(lang_code).class_node_types


# Backward-compat aliases (deprecated — use _get_*_node_types(lang_code) instead)
_FUNCTION_NODE_TYPES = {
    "python": ("function_definition", "decorated_definition"),
    "c": ("function_definition",),
    "cpp": ("function_definition",),
    "java": ("method_declaration", "constructor_declaration"),
    "javascript": ("function_declaration", "arrow_function", "method_definition"),
    "typescript": ("function_declaration", "arrow_function", "method_definition"),
    "tsx": ("function_declaration", "arrow_function", "method_definition"),
    "go": ("function_declaration", "method_declaration"),
    "rust": ("function_item",),
}
_CLASS_NODE_TYPES = {
    "python": ("class_definition",),
    "c": ("struct_specifier",),
    "cpp": ("class_specifier", "struct_specifier"),
    "java": ("class_declaration", "interface_declaration"),
    "javascript": ("class_declaration",),
    "typescript": ("class_declaration", "interface_declaration"),
    "tsx": ("class_declaration", "interface_declaration"),
    "go": ("type_declaration",),
    "rust": ("struct_item", "enum_item", "trait_item", "impl_item"),
}


def _extract_name(node: Node, source_bytes: bytes) -> str | None:
    """Extract the name identifier from a function/class node."""
    for sub in node.children:
        if sub.type == "identifier":
            return source_bytes[sub.start_byte : sub.end_byte].decode("utf-8", errors="ignore")
        # For decorated definitions (Python), descend into the actual function
        if sub.type == "function_definition":
            return _extract_name(sub, source_bytes)
        # For C/C++: name is inside function_declarator
        if sub.type == "function_declarator":
            return _extract_name(sub, source_bytes)
        # For Java: method_declaration has identifier directly
        if sub.type == "formal_parameters":
            # Already past the name, look at siblings
            pass
    return None


def _extract_functions(
    root_node: Node, source_bytes: bytes, lang_code: str = "python"
) -> list[dict]:
    """Extract function and class definitions with structural and semantic hashes.

    Also extracts methods from inside class bodies to detect method reordering.
    Recursively traverses all nodes to find function/class definitions at any depth.
    """
    func_types = _get_function_node_types(lang_code)
    class_types = _get_class_node_types(lang_code)
    all_types = set(func_types) | set(class_types)

    def _collect(node: Node, parent_name: str = "") -> list[dict]:
        results = []
        for child in node.children:
            # Detect top-level lambda assignments as functions (for scenarios like 8b)
            if parent_name == "" and child.type == "expression_statement":
                assign = _get_child_by_type(child, "assignment")
                if assign:
                    after_eq = False
                    value_node = None
                    for c in assign.children:
                        if c.type == "=":
                            after_eq = True
                        elif after_eq and c.type not in ("comment",):
                            value_node = c
                            break
                    if value_node and value_node.type == "lambda":
                        # Extract the target identifier name
                        target_node = None
                        for c in assign.children:
                            if c.type == "identifier":
                                target_node = c
                                break
                        if target_node:
                            name = (
                                source_bytes[target_node.start_byte : target_node.end_byte]
                                .decode("utf-8", errors="ignore")
                                .strip()
                            )
                            # Compute hashes on the lambda node
                            struct_hash = _hash_ast_subtree(value_node)
                            semantic_hash = _hash_ast_subtree_semantic(value_node)
                            results.append(
                                {
                                    "name": name,
                                    "start_line": child.start_point[0],
                                    "end_line": child.end_point[0],
                                    "struct_hash": struct_hash,
                                    "semantic_hash": semantic_hash,
                                    "node": value_node,
                                }
                            )
                            # Skip further processing of this child
                            continue
            if child.type in all_types:
                name = _extract_name(child, source_bytes)
                if parent_name:
                    qualified = f"{parent_name}.{name}" if name else f"{parent_name}.<anonymous>"
                else:
                    qualified = name or "<anonymous>"

                # Strip self/this from parameters for structural hash
                # so standalone functions and methods with same body match
                if child.type in func_types:
                    hash_node = _strip_self_from_params(child, source_bytes, lang_code)
                else:
                    hash_node = child
                struct_hash = _hash_ast_subtree(hash_node)
                semantic_hash = _hash_ast_subtree_semantic(hash_node)
                results.append(
                    {
                        "name": qualified,
                        "start_line": child.start_point[0],
                        "end_line": child.end_point[0],
                        "struct_hash": struct_hash,
                        "semantic_hash": semantic_hash,
                        "node": child,
                    }
                )

                # Recurse into child to find nested functions/methods
                results.extend(
                    _collect(child, qualified if child.type in class_types else parent_name)
                )
            else:
                # Traverse intermediate nodes (block, declaration_list, etc.)
                # to find nested function/class definitions
                results.extend(_collect(child, parent_name))

        return results

    return _collect(root_node)


def _is_main_block(node: Node, source_bytes: bytes, lang_code: str = "python") -> bool:
    """Check if a node is an entry-point block.

    Python: if __name__ == "__main__":
    C/C++/Java/Go/Rust: int main() / func main() / fn main()
    """
    if lang_code == "python" and node.type == "if_statement":
        for child in node.children:
            if child.type == "comparison_operator":
                text = source_bytes[child.start_byte : child.end_byte].decode(
                    "utf-8", errors="ignore"
                )
                if "__name__" in text and "__main__" in text:
                    return True

    elif lang_code in ("cpp", "c") and node.type == "function_definition":
        for child in node.children:
            if child.type == "function_declarator":
                for sub in child.children:
                    if sub.type == "identifier":
                        name = source_bytes[sub.start_byte : sub.end_byte].decode(
                            "utf-8", errors="ignore"
                        )
                        if name == "main":
                            return True

    elif lang_code == "java" and node.type == "method_declaration":
        for child in node.children:
            if child.type == "identifier":
                name = source_bytes[child.start_byte : child.end_byte].decode(
                    "utf-8", errors="ignore"
                )
                if name == "main":
                    return True

    elif lang_code == "go" and node.type == "function_declaration":
        for child in node.children:
            if child.type == "identifier":
                name = source_bytes[child.start_byte : child.end_byte].decode(
                    "utf-8", errors="ignore"
                )
                if name == "main":
                    return True

    elif lang_code == "rust" and node.type == "function_item":
        for child in node.children:
            if child.type == "identifier":
                name = source_bytes[child.start_byte : child.end_byte].decode(
                    "utf-8", errors="ignore"
                )
                if name == "main":
                    return True

    return False


def _extract_main_block(
    root_node: Node, source_bytes: bytes, lang_code: str = "python"
) -> dict | None:
    """Extract the entry-point block as a pseudo-function.

    Python: if __name__ == "__main__": body
    C/C++/Java/Go/Rust: main() function body

    Returns a dict with start_line, end_line, body, and hashes.
    """
    for child in root_node.children:
        if _is_main_block(child, source_bytes, lang_code):
            body_node = None
            if lang_code == "python":
                for sub in child.children:
                    if sub.type == "block":
                        body_node = sub
                        break
            elif lang_code in ("cpp", "c"):
                body_node = _get_child_by_type(child, "compound_statement")
            elif lang_code == "java":
                body_node = _get_child_by_type(child, "block")
            elif lang_code == "go":
                body_node = _get_child_by_type(child, "block")
            elif lang_code == "rust":
                body_node = _get_child_by_type(child, "block")

            if body_node is None:
                continue

            struct_hash = _hash_ast_subtree(body_node)
            semantic_hash = _hash_ast_subtree_semantic(body_node)

            return {
                "name": "__main__",
                "start_line": body_node.start_point[0],
                "end_line": body_node.end_point[0],
                "if_start_line": child.start_point[0],
                "struct_hash": struct_hash,
                "semantic_hash": semantic_hash,
                "node": body_node,
            }
    return None
