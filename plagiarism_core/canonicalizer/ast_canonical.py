"""AST-based semantic canonicalization engine."""

import logging

from tree_sitter import Node

from .semantic_map import (
    _ARITHMETIC_OPS,
    _COMPARISON_OPS,
    _IGNORABLE_NODE_TYPES,
    _LOGICAL_OPS,
    _get_child_by_type,
    _get_source_text,
    _is_ignorable,
    _semantic_node_type,
)

logger = logging.getLogger(__name__)


def _get_builtin_names():
    from ..fingerprinting.identifiers import BUILTIN_NAMES

    return BUILTIN_NAMES


def _extract_return_value(block_node: Node, source_bytes: bytes) -> str | None:
    for child in block_node.children:
        if child.type == "return_statement":
            for sub in child.children:
                if sub.type not in ("return", "comment"):
                    return _get_source_text(sub, source_bytes).strip()
    return None


def _normalize_if_chain(node: Node, source_bytes: bytes, depth: int) -> str | None:
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


def _emit_format_call(node: Node, source_bytes: bytes, depth: int) -> str | None:
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
    if template_text and template_text[0] in ('"', "'"):
        quote = template_text[0]
        if template_text.endswith(quote):
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
                fmt_args.append(_emit_canonical(child, source_bytes, depth + 1))
    parts = [repr(template_text)] + fmt_args
    return f"STRING_FORMAT({', '.join(parts)})"


def _emit_assignment_expression(node: Node, source_bytes: bytes, depth: int) -> str:
    ops = []
    operands = []
    for child in node.children:
        text = _get_source_text(child, source_bytes).strip()
        if text in ("+=", "-=", "*=", "/=", "%=", "<<=", ">>=", "&=", "|=", "^="):
            ops.append(text)
        elif text == "=":
            ops.append("=")
        elif child.type not in _IGNORABLE_NODE_TYPES:
            operands.append(_emit_canonical(child, source_bytes, depth + 1))
    if ops and len(operands) >= 2:
        op = ops[0]
        target = operands[0]
        value = operands[1]
        return f"ASSIGN({target}, {op}, {value})"
    parts = []
    for child in node.children:
        if child.type in _IGNORABLE_NODE_TYPES:
            continue
        parts.append(_emit_canonical(child, source_bytes, depth + 1))
    return "".join(parts) if parts else "ASSIGN()"


def _emit_binary_expression(node: Node, source_bytes: bytes, depth: int) -> str:
    ops = []
    operands = []
    for child in node.children:
        text = _get_source_text(child, source_bytes).strip()
        if text in _COMPARISON_OPS:
            ops.append(text)
        elif text in _ARITHMETIC_OPS:
            ops.append(text)
        elif text in _LOGICAL_OPS:
            ops.append(text)
        elif child.type not in ("comment",):
            operands.append(_emit_canonical(child, source_bytes, depth + 1))
    if not ops:
        parts = []
        for child in node.children:
            if child.type in _IGNORABLE_NODE_TYPES:
                continue
            parts.append(_emit_canonical(child, source_bytes, depth + 1))
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


def _emit_semantic_node(node: Node, source_bytes: bytes, sem_type: str, depth: int) -> str:
    if sem_type == "LOOP":
        iterable = ""
        if node.type == "for_statement":
            iter_node = _get_child_by_type(node, "iterable")
            if iter_node:
                iterable = _emit_canonical(iter_node, source_bytes, depth + 1)
            for_clause = _get_child_by_type(node, "for_clause")
            if for_clause:
                iterable = _emit_canonical(for_clause, source_bytes, depth + 1)
            range_clause = _get_child_by_type(node, "range_clause")
            if range_clause:
                iterable = _emit_canonical(range_clause, source_bytes, depth + 1)
        elif node.type == "for_range_loop":
            for child in node.children:
                if child.type == "identifier":
                    iterable = _emit_canonical(child, source_bytes, depth + 1)
        elif node.type == "enhanced_for_statement":
            identifiers = [c for c in node.children if c.type == "identifier"]
            if identifiers:
                iterable = _emit_canonical(identifiers[-1], source_bytes, depth + 1)
        elif node.type in ("while_statement", "while_expression"):
            cond_node = _get_child_by_type(node, "condition")
            if cond_node:
                iterable = _emit_canonical(cond_node, source_bytes, depth + 1)
            else:
                cond_clause = _get_child_by_type(node, "condition_clause")
                if cond_clause:
                    paren = _get_child_by_type(cond_clause, "parenthesized_expression")
                    if paren:
                        iterable = _emit_canonical(paren, source_bytes, depth + 1)
        elif node.type == "do_statement":
            paren = _get_child_by_type(node, "parenthesized_expression")
            if paren:
                iterable = _emit_canonical(paren, source_bytes, depth + 1)
        elif node.type == "for_expression":
            found_in = False
            for child in node.children:
                text = _get_source_text(child, source_bytes).strip()
                if text == "in":
                    found_in = True
                    continue
                if found_in and child.type == "identifier":
                    iterable = _emit_canonical(child, source_bytes, depth + 1)
                    break
        elif node.type == "loop_expression":
            iterable = "INFINITE"
        return f"LOOP({iterable})"

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
                    element = _emit_canonical(child, source_bytes, depth + 1)
            for child in node.children:
                if child.type == "for_in_clause":
                    for sub in child.children:
                        if sub.type == "identifier":
                            iter_src = _emit_canonical(sub, source_bytes, depth + 1)
        elif node.type == "generator_expression":
            for child in node.children:
                if child.type in ("(", ")"):
                    continue
                if child.type == "for_in_clause":
                    break
                if not element:
                    element = _emit_canonical(child, source_bytes, depth + 1)
            for child in node.children:
                if child.type == "for_in_clause":
                    for sub in child.children:
                        if sub.type == "identifier":
                            iter_src = _emit_canonical(sub, source_bytes, depth + 1)
        elif node.type == "call":
            func_node = _get_child_by_type(node, "function")
            if func_node:
                list_name = _get_source_text(func_node, source_bytes)
                if list_name == "list":
                    args_node = _get_child_by_type(node, "arguments")
                    if args_node:
                        first_arg = args_node.children[0] if args_node.children else None
                        if first_arg:
                            arg_sem = _semantic_node_type(first_arg)
                            if arg_sem == "COLLECTION":
                                return _emit_semantic_node(
                                    first_arg, source_bytes, "COLLECTION", depth + 1
                                )
                            elif first_arg.type == "call":
                                inner_func = _get_child_by_type(first_arg, "function")
                                if inner_func:
                                    inner_name = _get_source_text(inner_func, source_bytes)
                                    if "map" in inner_name or "filter" in inner_name:
                                        inner_args = _get_child_by_type(first_arg, "arguments")
                                        if inner_args and len(inner_args.children) >= 2:
                                            elem = _emit_canonical(
                                                inner_args.children[0], source_bytes, depth + 1
                                            )
                                            iterable = _emit_canonical(
                                                inner_args.children[1], source_bytes, depth + 1
                                            )
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
                key_expr = _emit_canonical(key_node, source_bytes, depth + 1)
            if val_node:
                val_expr = _emit_canonical(val_node, source_bytes, depth + 1)
        iter_node = _get_child_by_type(node, "iterable")
        if iter_node:
            iter_src = _emit_canonical(iter_node, source_bytes, depth + 1)
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
                            args.append(_emit_canonical(sub, source_bytes, depth + 1))
                elif child.type in ("string_start", "string_end"):
                    pass
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
        param_list = _get_child_by_type(node, "parameters")
        if not param_list:
            param_list = _get_child_by_type(node, "formal_parameters")
        if not param_list:
            param_list = _get_child_by_type(node, "closure_parameters")
        if not param_list:
            param_list = _get_child_by_type(node, "parameter_list")
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
        body_node = _get_child_by_type(node, "body")
        if not body_node:
            body_node = _get_child_by_type(node, "compound_statement")
        if not body_node:
            body_node = _get_child_by_type(node, "block")
        if not body_node and node.type == "arrow_function":
            for child in node.children:
                if child.type not in ("formal_parameters", "=>", "(", ")", ","):
                    body_node = child
                    break
        if body_node:
            body = _emit_canonical(body_node, source_bytes, depth + 1)
        return f"FUNC_LIT({params}, {body})"

    elif sem_type == "ASSIGN":
        target = ""
        op = ""
        value = ""
        children_list = [c for c in node.children if not _is_ignorable(c.type)]
        if len(children_list) >= 3:
            target = _emit_canonical(children_list[0], source_bytes, depth + 1)
            op = _get_source_text(children_list[1], source_bytes).strip()
            value = _emit_canonical(children_list[2], source_bytes, depth + 1)
        elif node.type == "update_expression" and len(children_list) >= 1:
            for child in children_list:
                text = _get_source_text(child, source_bytes).strip()
                if text in ("++", "--"):
                    op = text
                elif child.type == "identifier":
                    if not target:
                        target = _emit_canonical(child, source_bytes, depth + 1)
                    else:
                        value = _emit_canonical(child, source_bytes, depth + 1)
            if not value:
                value = "1"
        elif node.type == "inc_statement" and len(children_list) >= 1:
            for child in children_list:
                text = _get_source_text(child, source_bytes).strip()
                if text in ("++", "--"):
                    op = text
                elif child.type == "identifier":
                    target = _emit_canonical(child, source_bytes, depth + 1)
            value = "1"
        return f"ASSIGN({target}, {op}, {value})"

    elif sem_type == "COMPARISON":
        left = ""
        right = ""
        ops = []
        for child in node.children:
            text = _get_source_text(child, source_bytes).strip()
            if text in _COMPARISON_OPS or text in ("in", "not in", "is", "is not"):
                ops.append(text)
            elif not _is_ignorable(child.type):
                if not left:
                    left = _emit_canonical(child, source_bytes, depth + 1)
                else:
                    right = _emit_canonical(child, source_bytes, depth + 1)
        return f"COMPARE({left}, {', '.join(ops) if ops else '=='}, {right})"

    elif sem_type == "BOOLEAN_OP":
        ops = []
        operands = []
        for child in node.children:
            if child.type in ("and", "or", "not"):
                ops.append(child.type)
            else:
                operands.append(_emit_canonical(child, source_bytes, depth + 1))
        if "not" in ops:
            return f"BOOL_OP(NOT, {operands[0]})"
        return f"BOOL_OP({', '.join(operands)})"

    elif sem_type == "TERNARY":
        parts = []
        for child in node.children:
            text = _get_source_text(child, source_bytes).strip()
            if text in ("?", ":"):
                continue
            elif not _is_ignorable(child.type):
                parts.append(_emit_canonical(child, source_bytes, depth + 1))
        cond = parts[0] if len(parts) > 0 else ""
        true_val = parts[1] if len(parts) > 1 else ""
        false_val = parts[2] if len(parts) > 2 else ""
        return f"TERNARY({cond}, {true_val}, {false_val})"

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
                    then_block = _emit_canonical(child, source_bytes, depth + 1)
                continue
            if found_if and not then_block and child.type not in ("{", "}", "else", "else_clause"):
                cond = _emit_canonical(child, source_bytes, depth + 1)
        else_clause = _get_child_by_type(node, "else_clause")
        if else_clause:
            else_block_node = _get_child_by_type(else_clause, "block")
            if else_block_node:
                else_block = _emit_canonical(else_block_node, source_bytes, depth + 1)
        return f"COND({cond}, {then_block}, {else_block})"

    elif sem_type == "GROUP":
        paren = _get_child_by_type(node, "parenthesized_expression")
        if paren:
            return _emit_canonical(paren, source_bytes, depth + 1)
        parts = []
        for child in node.children:
            if not _is_ignorable(child.type) and child.type not in ("(", ")"):
                child_text = _emit_canonical(child, source_bytes, depth + 1)
                if child_text:
                    parts.append(child_text)
        return "".join(parts) if parts else "GROUP()"

    parts = []
    for child in node.children:
        if not _is_ignorable(child.type):
            child_text = _emit_canonical(child, source_bytes, depth + 1)
            if child_text:
                parts.append(child_text)
    return f"{sem_type}({', '.join(parts)})"


def _emit_canonical(node: Node, source_bytes: bytes, depth: int = 0) -> str:
    if depth > 50:
        return "<RECURSION_LIMIT>"

    sem_type = _semantic_node_type(node)
    if sem_type and sem_type not in (node.type,):
        return _emit_semantic_node(node, source_bytes, sem_type, depth)

    if node.type == "call":
        fmt_result = _emit_format_call(node, source_bytes, depth)
        if fmt_result is not None:
            return fmt_result

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
        return _emit_binary_expression(node, source_bytes, depth)

    if node.type == "assignment_expression":
        return _emit_assignment_expression(node, source_bytes, depth)

    if node.type == "if_statement":
        normalized = _normalize_if_chain(node, source_bytes, depth)
        if normalized is not None:
            return normalized

    if node.type == "assignment":
        children_list = [c for c in node.children if not _is_ignorable(c.type)]
        if len(children_list) >= 3 and children_list[2].type == "binary_operator":
            target = _emit_canonical(children_list[0], source_bytes, depth + 1)
            val_node = children_list[2]
            ops_found = []
            operands = []
            operand_texts = []
            for bc in val_node.children:
                text = _get_source_text(bc, source_bytes).strip()
                if text in _ARITHMETIC_OPS:
                    ops_found.append(text)
                elif not _is_ignorable(bc.type):
                    operands.append(_emit_canonical(bc, source_bytes, depth + 1))
                    operand_texts.append(text)
            if ops_found and len(operands) >= 2:
                op = ops_found[0] + "="
                target_text = _get_source_text(children_list[0], source_bytes).strip()
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
        if name in _get_builtin_names():
            return f"[builtin:{name}]"
        return "[identifier]"

    parts = []
    for child in node.children:
        if _is_ignorable(child.type):
            continue
        child_text = _emit_canonical(child, source_bytes, depth + 1)
        if child_text:
            parts.append(child_text)

    if not parts:
        return f"[{node.type}]"

    return "".join(parts)


def ast_canonicalize(source: str, lang_code: str = "python") -> str:
    try:
        tree, source_bytes = _parse_string_once(source, lang_code)
    except Exception:
        logger.warning(
            "Failed to parse source for AST canonicalization (lang=%s)", lang_code, exc_info=True
        )
        return source
    return _emit_canonical(tree.root_node, source_bytes)


def ast_canonicalize_with_identifiers(source: str, lang_code: str = "python") -> str:
    semantic_result = ast_canonicalize(source, lang_code)
    normalized = normalize_identifiers(semantic_result, lang_code)
    return normalized


def _parse_string_once(source, lang_code):
    from ..fingerprinting.parser import parse_string_once

    return parse_string_once(source, lang_code)


def normalize_identifiers(source, lang_code):
    from .identifier_norm import normalize_identifiers as _norm

    return _norm(source, lang_code)
