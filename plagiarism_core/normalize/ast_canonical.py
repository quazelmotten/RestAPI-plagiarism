"""AST-based semantic canonicalization for Type 4 plagiarism detection."""

import logging
from tree_sitter import Node

from ..parser import parse_string, get_language_profile
from ..canonicalizer.semantic_map import (
    _get_child_by_type,
    _get_source_text,
    _is_ignorable,
    _semantic_node_type,
    SEMANTIC_NODE_MAP,
    _COMPARISON_OPS,
    _ARITHMETIC_OPS,
    _LOGICAL_OPS,
)
from .identifier_norm import normalize_identifiers

logger = logging.getLogger(__name__)


def ast_canonicalize(source: str, lang: str = "python") -> str:
    """Canonicalize source code to a semantic normal form (Type 4)."""
    try:
        tree, source_bytes = parse_string(source, lang)
    except Exception:
        logger.warning("Failed to parse source for canonicalization (lang=%s)", lang, exc_info=True)
        return source
    try:
        builtins = get_language_profile(lang).builtin_names
    except Exception:
        builtins = set()
    return _emit_canonical(tree.root_node, source_bytes, builtins)


def canonicalize_type4(source: str, lang: str = "python") -> str:
    """Alias for ast_canonicalize (Type 4 normal form)."""
    return ast_canonicalize(source, lang)


def canonicalize_type4_light(source: str, lang: str = "python") -> str:
    """Lightweight canonicalization; same as ast_canonicalize."""
    return ast_canonicalize(source, lang)


def ast_canonicalize_with_identifiers(source: str, lang: str = "python") -> str:
    """Canonicalize and then normalize identifiers (combined)."""
    sem = ast_canonicalize(source, lang)
    return normalize_identifiers(sem, lang)


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------


def _extract_return_value(block_node: Node, source_bytes: bytes) -> str | None:
    """Extract the return value from a block if it ends with a return."""
    for child in block_node.children:
        if child.type == "return_statement":
            for sub in child.children:
                if sub.type not in ("return", "comment"):
                    return _get_source_text(sub, source_bytes).strip()
    return None


def _normalize_if_chain(node: Node, source_bytes: bytes, depth: int) -> str | None:
    """
    Normalize an if/elif/else chain that returns the same set of values.

    Returns a canonical string like RETURNS(v1, v2, ...) or None.
    """
    ret_vals = []
    body = _get_child_by_type(node, "block")
    if body is None:
        return None
    ret = _extract_return_value(body, source_bytes)
    if ret is None:
        return None
    ret_vals.append(ret)

    has_else = False
    for child in node.children:
        if child.type == "elif_clause":
            elif_body = _get_child_by_type(child, "block")
            if elif_body is None:
                return None
            elif_ret = _extract_return_value(elif_body, source_bytes)
            if elif_ret is None:
                return None
            ret_vals.append(elif_ret)
        elif child.type == "else_clause":
            else_body = _get_child_by_type(child, "block")
            if else_body is None:
                return None
            else_ret = _extract_return_value(else_body, source_bytes)
            if else_ret is None:
                return None
            ret_vals.append(else_ret)
            has_else = True

    if not has_else or len(ret_vals) < 2:
        return None
    ret_vals.sort()
    return f"RETURNS({', '.join(ret_vals)})"


def _emit_format_call(node: Node, source_bytes: bytes, depth: int, builtins: set[str]) -> str | None:
    """Detect string format calls and produce STRING_FORMAT(...) representation."""
    if node.type != "call":
        return None
    func_node = None
    args_node = None
    for child in node.children:
        if child.type == "attribute":
            func_node = child
        elif child.type == "argument_list":
            args_node = child
    if func_node is None:
        return None
    obj_node = None
    attr_name = None
    for child in func_node.children:
        if child.type == "string":
            obj_node = child
        elif child.type == "identifier":
            attr_name = _get_source_text(child, source_bytes)
    if obj_node is None or attr_name != "format":
        return None
    template_text = _get_source_text(obj_node, source_bytes)
    if template_text and template_text[0] in ('"', "'") and template_text.endswith(template_text[0]):
        template_text = template_text[1:-1]
    fmt_args = []
    if args_node:
        for child in args_node.children:
            if child.type in (
                "identifier",
                "string",
                "integer",
                "float",
                "true",
                "false",
                "none",
                "call",
                "attribute",
                "subscript",
                "binary_operator",
                "parenthesized_expression",
                "list",
                "dictionary",
                "set",
                "tuple",
                "list_comprehension",
                "generator_expression",
                "lambda",
                "not_operator",
                "boolean_operator",
                "comparison_operator",
                "conditional_expression",
            ):
                fmt_args.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
    parts = [repr(template_text)] + fmt_args
    return f"STRING_FORMAT({', '.join(parts)})"


def _emit_assignment_expression(node: Node, source_bytes: bytes, depth: int, builtins: set[str]) -> str:
    """Handle augmented assignments (e.g., x += y)."""
    ops = []
    operands = []
    for child in node.children:
        text = _get_source_text(child, source_bytes).strip()
        if text in ("+=", "-=", "*=", "/=", "%=", "<<=", ">>=", "&=", "|=", "^="):
            ops.append(text)
        elif text == "=":
            ops.append("=")
        elif child.type not in ("comment",):
            operands.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
    if ops and len(operands) >= 2:
        op = ops[0]
        target = operands[0]
        value = operands[1]
        return f"ASSIGN({target}, {op}, {value})"
    parts = []
    for child in node.children:
        if child.type in ("comment",):
            continue
        parts.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
    return "".join(parts) if parts else "ASSIGN()"


def _emit_binary_expression(node: Node, source_bytes: bytes, depth: int, builtins: set[str]) -> str:
    """Handle binary operations (arithmetic, comparison, logical)."""
    ops = []
    operands = []
    for child in node.children:
        text = _get_source_text(child, source_bytes).strip()
        if text in _COMPARISON_OPS or text in _ARITHMETIC_OPS or text in _LOGICAL_OPS:
            ops.append(text)
        elif child.type not in ("comment",):
            operands.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
    if not ops:
        parts = []
        for child in node.children:
            if child.type in ("comment",):
                continue
            parts.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
        return "".join(parts)
    op = ops[0]
    left = operands[0] if operands else ""
    right = operands[1] if len(operands) > 1 else ""
    if op in _COMPARISON_OPS:
        return f"COMPARE({left}, {op}, {right})"
    elif op in _ARITHMETIC_OPS:
        return f"ARITHMETIC({op}, {left}, {right})"
    else:
        return f"LOGICAL({op}, {left}, {right})"


def _emit_semantic_node(node: Node, source_bytes: bytes, sem_type: str, depth: int, builtins: set[str]) -> str:
    """Emit canonical representation for a node with a mapped semantic type."""
    if sem_type == "LOOP":
        iterable = ""
        body = ""
        if node.type == "for_statement":
            iter_node = _get_child_by_type(node, "iterable")
            if iter_node:
                iterable = _emit_canonical(iter_node, source_bytes, builtins, depth + 1)
            for_clause = _get_child_by_type(node, "for_clause")
            if for_clause:
                iterable = _emit_canonical(for_clause, source_bytes, builtins, depth + 1)
            range_clause = _get_child_by_type(node, "range_clause")
            if range_clause:
                iterable = _emit_canonical(range_clause, source_bytes, builtins, depth + 1)
            block = _get_child_by_type(node, "block")
            if block:
                body = _emit_canonical(block, source_bytes, builtins, depth + 1)
        elif node.type in ("while_statement", "while_expression"):
            cond_node = _get_child_by_type(node, "condition")
            if not cond_node:
                cond_node = _get_child_by_type(node, "condition_clause")
            if cond_node:
                paren = _get_child_by_type(cond_node, "parenthesized_expression")
                if paren:
                    iterable = _emit_canonical(paren, source_bytes, builtins, depth + 1)
                else:
                    iterable = _emit_canonical(cond_node, source_bytes, builtins, depth + 1)
            block = _get_child_by_type(node, "block")
            if block:
                body = _emit_canonical(block, source_bytes, builtins, depth + 1)
        elif node.type == "do_statement":
            block = _get_child_by_type(node, "block")
            if block:
                body = _emit_canonical(block, source_bytes, builtins, depth + 1)
            paren = _get_child_by_type(node, "parenthesized_expression")
            if paren:
                iterable = _emit_canonical(paren, source_bytes, builtins, depth + 1)
        elif node.type == "for_in_statement":
            iter_node = _get_child_by_type(node, "iterable")
            if iter_node:
                iterable = _emit_canonical(iter_node, source_bytes, builtins, depth + 1)
            block = _get_child_by_type(node, "block")
            if block:
                body = _emit_canonical(block, source_bytes, builtins, depth + 1)
        elif node.type == "for_range_loop":
            for child in node.children:
                if child.type == "identifier":
                    iterable = _emit_canonical(child, source_bytes, builtins, depth + 1)
                    break
            block = _get_child_by_type(node, "block")
            if block:
                body = _emit_canonical(block, source_bytes, builtins, depth + 1)
        elif node.type in ("for_expression", "enhanced_for_statement"):
            # Simplified generic handling
            children_processed = []
            for child in node.children:
                if _is_ignorable(child.type):
                    continue
                children_processed.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
            if len(children_processed) >= 2:
                iterable = children_processed[0]
                body = children_processed[1]
            elif children_processed:
                iterable = children_processed[0]
                body = ""
            else:
                iterable = ""
                body = ""
        elif node.type == "loop_expression":
            body = ""
            for child in node.children:
                if child.type not in ("loop", "(", ")"):
                    body = _emit_canonical(child, source_bytes, builtins, depth + 1)
            iterable = "INFINITE"
        return f"LOOP({iterable}, {body})"

    elif sem_type == "COLLECTION":
        element = ""
        iter_src = ""
        if node.type == "list_comprehension":
            for child in node.children:
                if child.type in ("[", "]"):
                    continue
                if child.type == "for_in_clause":
                    break
                if not element:
                    element = _emit_canonical(child, source_bytes, builtins, depth + 1)
            for child in node.children:
                if child.type == "for_in_clause":
                    for sub in child.children:
                        if sub.type == "identifier":
                            iter_src = _emit_canonical(sub, source_bytes, builtins, depth + 1)
        elif node.type == "generator_expression":
            for child in node.children:
                if child.type in ("(", ")"):
                    continue
                if child.type == "for_in_clause":
                    break
                if not element:
                    element = _emit_canonical(child, source_bytes, builtins, depth + 1)
            for child in node.children:
                if child.type == "for_in_clause":
                    for sub in child.children:
                        if sub.type == "identifier":
                            iter_src = _emit_canonical(sub, source_bytes, builtins, depth + 1)
        elif node.type == "call":
            func_node = _get_child_by_type(node, "function")
            if func_node:
                list_name = _get_source_text(func_node, source_bytes)
                if list_name == "list":
                    args_node = _get_child_by_type(node, "arguments")
                    if args_node and args_node.children:
                        first_arg = args_node.children[0]
                        inner_sem = _semantic_node_type(first_arg)
                        if inner_sem == "COLLECTION":
                            return _emit_semantic_node(first_arg, source_bytes, "COLLECTION", depth + 1, builtins)
                        if first_arg.type == "call":
                            inner_func = _get_child_by_type(first_arg, "function")
                            if inner_func:
                                inner_name = _get_source_text(inner_func, source_bytes)
                                if "map" in inner_name or "filter" in inner_name:
                                    inner_args = _get_child_by_type(first_arg, "arguments")
                                    if inner_args and len(inner_args.children) >= 2:
                                        elem = _emit_canonical(inner_args.children[0], source_bytes, builtins, depth + 1)
                                        iterable = _emit_canonical(inner_args.children[1], source_bytes, builtins, depth + 1)
                                        return f"COLLECT({elem}, {iterable})"
        return f"COLLECT({element}, {iter_src})"

    elif sem_type == "DICT_COLLECTION":
        key_expr = ""
        val_expr = ""
        iter_src = ""
        pair_node = _get_child_by_type(node, "pair")
        if pair_node:
            key_node = _get_child_by_type(pair_node, "key")
            val_node = _get_child_by_type(pair_node, "value")
            if key_node:
                key_expr = _emit_canonical(key_node, source_bytes, builtins, depth + 1)
            if val_node:
                val_expr = _emit_canonical(val_node, source_bytes, builtins, depth + 1)
        iter_node = _get_child_by_type(node, "iterable")
        if iter_node:
            iter_src = _emit_canonical(iter_node, source_bytes, builtins, depth + 1)
        return f"DICT_COLLECT({key_expr}, {val_expr}, {iter_src})"

    elif sem_type == "STRING_FORMAT":
        if node.type in ("fstring", "string"):
            template_parts = []
            args = []
            for child in node.children:
                if child.type == "string_content":
                    text = _get_source_text(child, source_bytes)
                    if text:
                        template_parts.append(text)
                elif child.type == "interpolation":
                    template_parts.append("{}")
                    for sub in child.children:
                        if sub.type not in ("{", "}"):
                            args.append(_emit_canonical(sub, source_bytes, builtins, depth + 1))
            template = "".join(template_parts)
            parts = [repr(template)] + args
            return f"STRING_FORMAT({', '.join(parts)})"
        elif node.type in (
            "string_literal",
            "raw_string_literal",
            "interpreted_string_literal",
            "string_fragment",
        ):
            return "STRING_FORMAT(STR)"
        return "STRING_FORMAT()"

    elif sem_type == "FUNCTION_LITERAL":
        params = ""
        body = ""
        param_list = (
            _get_child_by_type(node, "parameters")
            or _get_child_by_type(node, "formal_parameters")
            or _get_child_by_type(node, "closure_parameters")
            or _get_child_by_type(node, "parameter_list")
        )
        if not param_list:
            abs_decl = _get_child_by_type(node, "abstract_function_declarator")
            if abs_decl:
                param_list = _get_child_by_type(abs_decl, "parameter_list")
        if param_list:
            param_parts = []
            for child in param_list.children:
                if child.type in (
                    "identifier",
                    "parameter_declaration",
                    "type_identifier",
                    "primitive_type",
                    "required_parameter",
                    "optional_parameter",
                ):
                    if child.type in (
                        "parameter_declaration",
                        "required_parameter",
                        "optional_parameter",
                    ):
                        for sub in child.children:
                            if sub.type == "identifier":
                                param_parts.append("VAR")
                                break
                    elif child.type not in ("(", ")", ",", ":", "|"):
                        param_parts.append("VAR")
            params = ", ".join(param_parts)
        body_node = (
            _get_child_by_type(node, "body")
            or _get_child_by_type(node, "compound_statement")
            or _get_child_by_type(node, "block")
        )
        if not body_node and node.type == "arrow_function":
            for child in node.children:
                if child.type not in ("formal_parameters", "=>", "(", ")", ","):
                    body_node = child
                    break
        if body_node:
            body = _emit_canonical(body_node, source_bytes, builtins, depth + 1)
        return f"FUNC_LIT({params}, {body})"

    elif sem_type == "ASSIGN":
        target = ""
        op = ""
        value = ""
        children_list = [c for c in node.children if not _is_ignorable(c.type)]
        if len(children_list) >= 3:
            target_node = children_list[0]
            target = _emit_canonical(target_node, source_bytes, builtins, depth + 1)
            op_node = children_list[1]
            op = _get_source_text(op_node, source_bytes).strip()
            value_node = children_list[2]
            value = _emit_canonical(value_node, source_bytes, builtins, depth + 1)
            return f"ASSIGN({target}, {op}, {value})"
        parts = []
        for child in node.children:
            if not _is_ignorable(child.type):
                parts.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
        return "".join(parts) if parts else "ASSIGN()"

    elif sem_type == "COMPARISON":
        left = ""
        right = ""
        op = ""
        children_list = [c for c in node.children if not _is_ignorable(c.type)]
        if len(children_list) >= 3:
            left_node = children_list[0]
            op_node = children_list[1]
            right_node = children_list[2]
            left = _emit_canonical(left_node, source_bytes, builtins, depth + 1)
            op = _get_source_text(op_node, source_bytes).strip()
            right = _emit_canonical(right_node, source_bytes, builtins, depth + 1)
            return f"COMPARE({left}, {op}, {right})"
        parts = []
        for child in node.children:
            if not _is_ignorable(child.type):
                parts.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
        return "".join(parts)

    elif sem_type == "BOOLEAN_OP":
        operands = []
        ops = []
        for child in node.children:
            if child.type in ("and", "or", "&&", "||"):
                ops.append(child.type)
            elif not _is_ignorable(child.type):
                operands.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
        if "not" in ops or node.type == "not_operator":
            if operands:
                return f"BOOL_OP(NOT, {operands[0]})"
            return "BOOL_OP(NOT)"
        if ops and operands:
            return f"BOOL_OP({', '.join(operands)})"
        return "".join(operands) if operands else "BOOL_OP()"

    elif sem_type == "TERNARY":
        parts = []
        for child in node.children:
            if child.type in ("?", ":"):
                continue
            elif not _is_ignorable(child.type):
                parts.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
        if len(parts) >= 3:
            return f"TERNARY({parts[0]}, {parts[1]}, {parts[2]})"
        return "TERNARY"

    elif sem_type == "COND":
        cond = ""
        then_block = ""
        else_block = ""
        found_if = False
        for child in node.children:
            text = _get_source_text(child, source_bytes).strip()
            if text == "if":
                found_if = True
                continue
            if found_if and child.type == "block":
                if not then_block:
                    then_block = _emit_canonical(child, source_bytes, builtins, depth + 1)
                continue
            if found_if and not then_block and child.type not in ("{", "}", "else", "else_clause"):
                cond = _emit_canonical(child, source_bytes, builtins, depth + 1)
        else_clause = _get_child_by_type(node, "else_clause")
        if else_clause:
            else_block_node = _get_child_by_type(else_clause, "block")
            if else_block_node:
                else_block = _emit_canonical(else_block_node, source_bytes, builtins, depth + 1)
        return f"COND({cond}, {then_block}, {else_block})"

    elif sem_type == "GROUP":
        paren = _get_child_by_type(node, "parenthesized_expression")
        if paren:
            return _emit_canonical(paren, source_bytes, builtins, depth + 1)
        parts = []
        for child in node.children:
            if not _is_ignorable(child.type) and child.type not in ("(", ")"):
                parts.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
        return "".join(parts) if parts else "GROUP()"

    else:
        # Generic fallback: use semantic type as wrapper
        parts = []
        for child in node.children:
            if not _is_ignorable(child.type):
                parts.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
        if not parts:
            return f"[{sem_type}]"
        return f"{sem_type}({', '.join(parts)})"


def _emit_canonical(node: Node, source_bytes: bytes, builtins: set[str], depth: int = 0) -> str:
    if depth > 50:
        return "<RECURSION_LIMIT>"
    sem_type = _semantic_node_type(node)
    if sem_type and sem_type not in (node.type,):
        return _emit_semantic_node(node, source_bytes, sem_type, depth, builtins)

    if node.type == "call":
        fmt = _emit_format_call(node, source_bytes, depth, builtins)
        if fmt is not None:
            return fmt
        return _emit_semantic_node(node, source_bytes, "CALL", depth, builtins)

    if node.type == "integer":
        text = _get_source_text(node, source_bytes)
        return f"[int:{text}]"
    if node.type == "float":
        text = _get_source_text(node, source_bytes)
        return f"[float:{text}]"
    if node.type in ("true", "false"):
        return f"[bool:{_get_source_text(node, source_bytes)}]"
    if node.type == "none":
        return "[none]"

    if node.type == "binary_expression":
        return _emit_binary_expression(node, source_bytes, depth, builtins)
    if node.type == "assignment_expression":
        return _emit_assignment_expression(node, source_bytes, depth, builtins)
    if node.type == "if_statement":
        normalized = _normalize_if_chain(node, source_bytes, depth)
        if normalized is not None:
            return normalized
    if node.type == "assignment":
        children_list = [c for c in node.children if not _is_ignorable(c.type)]
        if len(children_list) >= 3 and children_list[2].type == "binary_operator":
            target_node = children_list[0]
            target = _emit_canonical(target_node, source_bytes, builtins, depth + 1)
            target_text = _get_source_text(target_node, source_bytes).strip()
            op_node = children_list[2]
            ops_found = []
            operands = []
            operand_texts = []
            for bc in op_node.children:
                text = _get_source_text(bc, source_bytes).strip()
                if text in _ARITHMETIC_OPS:
                    ops_found.append(text)
                elif not _is_ignorable(bc.type):
                    operands.append(_emit_canonical(bc, source_bytes, builtins, depth + 1))
                    operand_texts.append(text)
            if ops_found and len(operands) >= 2:
                op = ops_found[0] + "="
                value = ""
                for k, otext in enumerate(operand_texts):
                    if otext != target_text:
                        value = operands[k]
                        break
                if not value:
                    value = operands[-1]
                return f"ASSIGN({target}, {op}, {value})"

    if node.type == "identifier" and not node.children:
        name = _get_source_text(node, source_bytes)
        if name in builtins:
            return f"[builtin:{name}]"
        return "[identifier]"

    parts = []
    for child in node.children:
        if _is_ignorable(child.type):
            continue
        parts.append(_emit_canonical(child, source_bytes, builtins, depth + 1))
    if not parts:
        return f"[{node.type}]"
    return "".join(parts)
