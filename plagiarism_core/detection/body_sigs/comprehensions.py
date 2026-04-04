"""Comprehension and loop pattern extraction."""

from ...canonicalizer import _get_child_by_type, parse_file_once_from_string


def _extract_comprehension_pattern(source: str, lang_code: str = "python") -> dict | None:
    if lang_code != "python":
        return None
    try:
        tree, source_bytes = parse_file_once_from_string(source, lang_code)
    except Exception:
        return None
    root = tree.root_node
    for child in root.children:
        if child.type == "function_definition":
            body_node = _get_child_by_type(child, "block")
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
        if child.type == "decorated_definition":
            fn = _get_child_by_type(child, "function_definition")
            if fn:
                body_node = _get_child_by_type(fn, "block")
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
    stmts = [c for c in root.children if c.type not in ("comment", "NEWLINE", "")]
    if len(stmts) == 1 and stmts[0].type == "return_statement":
        ret = stmts[0]
        for child in ret.children:
            if child.type == "list_comprehension":
                return _extract_comprehension_parts(child, source_bytes)
    if len(stmts) >= 3:
        first = stmts[0]
        if first.type == "expression_statement":
            first = _get_child_by_type(first, "assignment")
        if first and first.type == "assignment":
            children = [c for c in first.children if c.type not in ("comment", "NEWLINE")]
            if len(children) >= 3 and children[2].type == "list":
                list_node = children[2]
                list_children = [c for c in list_node.children if c.type not in ("comment",)]
                if len(list_children) == 2:
                    target_name = source_bytes[
                        children[0].start_byte : children[0].end_byte
                    ].decode("utf-8", errors="ignore")
                    for_stmt = None
                    for s in stmts[1:-1]:
                        if s.type == "for_statement":
                            for_stmt = s
                            break
                    if for_stmt is None:
                        for s in stmts[1:-1]:
                            inner = _get_child_by_type(s, "for_statement")
                            if inner:
                                for_stmt = inner
                                break
                    if for_stmt:
                        result = _extract_loop_append_pattern(for_stmt, target_name, source_bytes)
                        if result:
                            last = stmts[-1]
                            if last.type == "return_statement":
                                for child in last.children:
                                    if child.type == "identifier":
                                        ret_name = source_bytes[
                                            child.start_byte : child.end_byte
                                        ].decode("utf-8", errors="ignore")
                                        if ret_name == target_name:
                                            return result
    return None


def _extract_comprehension_parts(comp_node, source_bytes) -> dict | None:
    iterable_text = None
    var_text = None
    element_text = None
    filter_text = None
    for child in comp_node.children:
        if child.type == "for_in_clause":
            for sub in child.children:
                if sub.type == "identifier":
                    if var_text is None:
                        var_text = source_bytes[sub.start_byte : sub.end_byte].decode(
                            "utf-8", errors="ignore"
                        )
                elif sub.type in (
                    "call",
                    "attribute",
                    "subscript",
                    "binary_operator",
                    "integer",
                    "float",
                    "identifier",
                    "list",
                    "parenthesized_expression",
                ):
                    if var_text is not None and iterable_text is None:
                        iterable_text = source_bytes[sub.start_byte : sub.end_byte].decode(
                            "utf-8", errors="ignore"
                        )
        elif child.type == "if_clause":
            for sub in child.children:
                if sub.type not in ("if",):
                    filter_text = (
                        source_bytes[sub.start_byte : sub.end_byte]
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )
    for child in comp_node.children:
        if child.type not in ("[", "]", "(", ")", "for_in_clause", "for", "if_clause"):
            element_text = source_bytes[child.start_byte : child.end_byte].decode(
                "utf-8", errors="ignore"
            )
            break
    if iterable_text and var_text and element_text:
        result = {
            "pattern": "comprehension",
            "iterable": iterable_text.strip(),
            "variable": var_text.strip(),
            "element": element_text.strip(),
        }
        if filter_text:
            result["filter"] = filter_text
        return result
    return None


def _extract_loop_append_pattern(for_stmt, target_name: str, source_bytes) -> dict | None:
    var_text = None
    iterable_text = None
    element_text = None
    for child in for_stmt.children:
        if child.type == "identifier" and var_text is None:
            var_text = source_bytes[child.start_byte : child.end_byte].decode(
                "utf-8", errors="ignore"
            )
        elif child.type in (
            "call",
            "attribute",
            "subscript",
            "binary_operator",
            "identifier",
            "list",
            "parenthesized_expression",
            "range",
        ):
            if var_text is not None and iterable_text is None:
                iterable_text = source_bytes[child.start_byte : child.end_byte].decode(
                    "utf-8", errors="ignore"
                )
    body = _get_child_by_type(for_stmt, "block")
    filter_text = None
    if body:
        append_call = None
        guard_if_stmt = None
        for stmt in body.children:
            if stmt.type == "if_statement":
                if_body = _get_child_by_type(stmt, "block")
                if if_body:
                    for substmt in if_body.children:
                        call_node = _get_child_by_type(substmt, "call")
                        if call_node:
                            func = _get_child_by_type(call_node, "attribute")
                            if func:
                                func_text = source_bytes[func.start_byte : func.end_byte].decode(
                                    "utf-8", errors="ignore"
                                )
                                if func_text.startswith(target_name + ".append"):
                                    append_call = call_node
                                    guard_if_stmt = stmt
                                    break
                if append_call:
                    break
            elif stmt.type == "expression_statement":
                call_node = _get_child_by_type(stmt, "call")
                if call_node:
                    func = _get_child_by_type(call_node, "attribute")
                    if func:
                        func_text = source_bytes[func.start_byte : func.end_byte].decode(
                            "utf-8", errors="ignore"
                        )
                        if func_text.startswith(target_name + ".append"):
                            append_call = call_node
                            break
        if append_call:
            args = _get_child_by_type(append_call, "argument_list")
            if args:
                for arg in args.children:
                    if arg.type not in ("(", ")", ","):
                        element_text = source_bytes[arg.start_byte : arg.end_byte].decode(
                            "utf-8", errors="ignore"
                        )
                        break
            if guard_if_stmt:
                for child in guard_if_stmt.children:
                    if child.type not in ("if", ":", "block", "else_clause", "comment"):
                        filter_text = (
                            source_bytes[child.start_byte : child.end_byte]
                            .decode("utf-8", errors="ignore")
                            .strip()
                        )
                        break
    if iterable_text and var_text and element_text:
        result = {
            "pattern": "loop_append",
            "iterable": iterable_text.strip(),
            "variable": var_text.strip(),
            "element": element_text.strip(),
        }
        if filter_text:
            result["filter"] = filter_text
        return result
    return None


def _extract_map_lambda_parts(map_call_node, source_bytes) -> dict | None:
    arg_list = _get_child_by_type(map_call_node, "argument_list")
    if not arg_list:
        return None
    args = [c for c in arg_list.children if c.type not in ("(", ",", ")")]
    if len(args) < 2:
        return None
    lambda_node = args[0]
    if lambda_node.type != "lambda":
        return None
    iterable_node = args[1]
    params_node = None
    for sub in lambda_node.children:
        if sub.type == "parameters":
            params_node = sub
            break
    var_name = ""
    if params_node:
        for pchild in params_node.children:
            if pchild.type == "identifier":
                var_name = (
                    source_bytes[pchild.start_byte : pchild.end_byte]
                    .decode("utf-8", errors="ignore")
                    .strip()
                )
                break
    if not var_name:
        return None
    body_node = None
    for sub in lambda_node.children:
        if sub.type not in ("lambda", "parameters", ":", "comment"):
            body_node = sub
            break
    if not body_node:
        return None
    element_text = (
        source_bytes[body_node.start_byte : body_node.end_byte]
        .decode("utf-8", errors="ignore")
        .strip()
    )
    iterable_text = (
        source_bytes[iterable_node.start_byte : iterable_node.end_byte]
        .decode("utf-8", errors="ignore")
        .strip()
    )
    return {
        "iterable": iterable_text,
        "variable": var_name,
        "element": element_text,
    }
