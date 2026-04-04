"""Body signature extraction dispatcher."""

from ...canonicalizer import parse_file_once_from_string
from .conditionals import (
    _extract_conditional_assign_signature,
    _extract_lbyl_signature,
    _extract_nested_if_signature,
    _extract_ternary_signature,
)
from .returns import (
    _extract_return_chain_signature,
)


def _extract_body_signature(source: str, lang_code: str = "python") -> str | None:
    try:
        tree, source_bytes = parse_file_once_from_string(source, lang_code)
    except Exception:
        return None
    root = tree.root_node
    if lang_code == "python":
        for child in root.children:
            fn_node = None
            if child.type == "function_definition":
                fn_node = child
            elif child.type == "decorated_definition":
                fn_node = _get_child_by_type(child, "function_definition")
            if fn_node:
                body_node = _get_child_by_type(fn_node, "block")
                if body_node:
                    source = source_bytes[body_node.start_byte : body_node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    try:
                        tree, source_bytes = parse_file_once_from_string(source, lang_code)
                        root = tree.root_node
                    except Exception:
                        return None
                break
    elif lang_code in ("cpp", "c"):
        for child in root.children:
            if child.type == "function_definition":
                body_node = _get_child_by_type(child, "compound_statement")
                if body_node:
                    source = source_bytes[body_node.start_byte : body_node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    try:
                        tree, source_bytes = parse_file_once_from_string(source, lang_code)
                        root = tree.root_node
                        if root.children and root.children[0].type == "compound_statement":
                            root = root.children[0]
                    except Exception:
                        return None
                break
    elif lang_code == "java":
        for child in root.children:
            if child.type in ("method_declaration", "constructor_declaration"):
                body_node = _get_child_by_type(child, "block")
                if body_node:
                    source = source_bytes[body_node.start_byte : body_node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    try:
                        tree, source_bytes = parse_file_once_from_string(source, lang_code)
                        root = tree.root_node
                        if root.children and root.children[0].type == "block":
                            root = root.children[0]
                    except Exception:
                        return None
                break
    elif lang_code in ("javascript", "typescript", "tsx"):
        for child in root.children:
            if child.type in (
                "function_declaration",
                "method_definition",
                "arrow_function",
                "function",
            ):
                body_node = _get_child_by_type(child, "statement_block")
                if not body_node:
                    body_node = _get_child_by_type(child, "expression")
                if body_node:
                    source = source_bytes[body_node.start_byte : body_node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    try:
                        tree, source_bytes = parse_file_once_from_string(source, lang_code)
                        root = tree.root_node
                        if root.children and root.children[0].type == "statement_block":
                            root = root.children[0]
                    except Exception:
                        return None
                break
    elif lang_code == "go":
        for child in root.children:
            if child.type == "function_declaration":
                body_node = _get_child_by_type(child, "block")
                if body_node:
                    source = source_bytes[body_node.start_byte : body_node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    try:
                        tree, source_bytes = parse_file_once_from_string(source, lang_code)
                        root = tree.root_node
                        if root.children and root.children[0].type == "block":
                            root = root.children[0]
                    except Exception:
                        return None
                break
    elif lang_code == "rust":
        for child in root.children:
            if child.type == "function_item":
                body_node = _get_child_by_type(child, "block")
                if body_node:
                    source = source_bytes[body_node.start_byte : body_node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    try:
                        tree, source_bytes = parse_file_once_from_string(source, lang_code)
                        root = tree.root_node
                        if root.children and root.children[0].type == "block":
                            root = root.children[0]
                    except Exception:
                        return None
                break
    stmts = [
        c
        for c in root.children
        if c.type not in ("comment", "NEWLINE", "", "whitespace", ";", "{", "}")
    ]
    if not stmts:
        return None
    if stmts[0].type == "if_statement":
        sig = _extract_return_chain_signature(stmts[0], source_bytes)
        if sig:
            return sig
    if stmts[0].type == "if_statement" and len(stmts) >= 2:
        sig = _extract_conditional_assign_signature(stmts, source_bytes)
        if sig:
            return sig
    if stmts[0].type == "if_statement":
        sig = _extract_nested_if_signature(stmts, source_bytes)
        if sig:
            return sig
    if stmts[0].type == "if_statement" and len(stmts) >= 2:
        sig = _extract_lbyl_signature(stmts, source_bytes)
        if sig:
            return sig
    if len(stmts) <= 2:
        for stmt in stmts:
            if stmt.type == "return_statement":
                for child in stmt.children:
                    if child.type in ("conditional_expression", "ternary_expression"):
                        sig = _extract_ternary_signature(child, source_bytes)
                        if sig:
                            return sig
                    elif child.type not in ("return", ";", "comment"):
                        expr = (
                            source_bytes[child.start_byte : child.end_byte]
                            .decode("utf-8", errors="ignore")
                            .strip()
                        )
                        if expr and expr != ";":
                            if child.type in (
                                "binary_expression",
                                "call",
                                "conditional_expression",
                                "ternary_expression",
                                "parenthesized_expression",
                            ):
                                return f"RETURNS({expr})"
            if stmt.type == "expression_statement":
                assign = _get_child_by_type(stmt, "assignment")
                if assign:
                    val_node = None
                    target_node = None
                    for sub in assign.children:
                        if sub.type == "identifier" and target_node is None:
                            target_node = sub
                        elif sub.type not in ("=",):
                            val_node = sub
                    if val_node and val_node.type in (
                        "conditional_expression",
                        "ternary_expression",
                    ):
                        sig = _extract_ternary_signature(val_node, source_bytes)
                        if sig:
                            return sig
    if len(stmts) == 1 and stmts[0].type == "return_statement":
        for child in stmts[0].children:
            if child.type not in ("return", ";", "comment"):
                expr = (
                    source_bytes[child.start_byte : child.end_byte]
                    .decode("utf-8", errors="ignore")
                    .strip()
                )
                if expr and expr != ";":
                    if child.type in (
                        "binary_expression",
                        "call",
                        "conditional_expression",
                        "ternary_expression",
                        "parenthesized_expression",
                        "unary_expression",
                    ):
                        return f"RETURNS({expr})"
    return None


def _get_child_by_type(node, child_type):
    from ...canonicalizer import _get_child_by_type as _gct

    return _gct(node, child_type)
