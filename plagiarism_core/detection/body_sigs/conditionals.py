"""Conditional and control-flow pattern extraction."""

from ...canonicalizer import _get_child_by_type


def _extract_return_value(block_node, source_bytes) -> str | None:
    for child in block_node.children:
        if child.type == "return_statement":
            for sub in child.children:
                if sub.type not in ("return", "comment"):
                    return (
                        source_bytes[sub.start_byte : sub.end_byte]
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )
    return None


def _extract_conditional_assign_signature(stmts, source_bytes) -> str | None:
    if_node = stmts[0]
    if if_node.type != "if_statement":
        return None
    cond = _get_child_by_type(if_node, "comparison_operator")
    if not cond:
        cond = _get_child_by_type(if_node, "boolean_operator")
    if not cond:
        for child in if_node.children:
            if child.type not in ("if", ":", "block", "else_clause", "comment"):
                cond = child
                break
    if not cond:
        return None
    if_body = _get_child_by_type(if_node, "block")
    if not if_body:
        return None
    if_assign = None
    if_target = None
    for child in if_body.children:
        stmt = child
        if stmt.type == "expression_statement":
            stmt = _get_child_by_type(stmt, "assignment")
        if stmt and stmt.type == "assignment":
            children = [c for c in stmt.children if c.type not in ("comment",)]
            if len(children) >= 3:
                if_target = (
                    source_bytes[children[0].start_byte : children[0].end_byte]
                    .decode("utf-8", errors="ignore")
                    .strip()
                )
                if_assign = (
                    source_bytes[children[2].start_byte : children[2].end_byte]
                    .decode("utf-8", errors="ignore")
                    .strip()
                )
    if not if_assign or not if_target:
        return None
    else_assign = None
    else_target = None
    for child in if_node.children:
        if child.type == "else_clause":
            else_body = _get_child_by_type(child, "block")
            if else_body:
                for sub in else_body.children:
                    stmt = sub
                    if stmt.type == "expression_statement":
                        stmt = _get_child_by_type(stmt, "assignment")
                    if stmt and stmt.type == "assignment":
                        children = [c for c in stmt.children if c.type not in ("comment",)]
                        if len(children) >= 3:
                            else_target = (
                                source_bytes[children[0].start_byte : children[0].end_byte]
                                .decode("utf-8", errors="ignore")
                                .strip()
                            )
                            else_assign = (
                                source_bytes[children[2].start_byte : children[2].end_byte]
                                .decode("utf-8", errors="ignore")
                                .strip()
                            )
    if not else_assign or else_target != if_target:
        return None
    last = stmts[-1]
    if last.type == "return_statement":
        for child in last.children:
            if child.type == "identifier":
                ret_target = (
                    source_bytes[child.start_byte : child.end_byte]
                    .decode("utf-8", errors="ignore")
                    .strip()
                )
                if ret_target == if_target:
                    return f"COND_ASSIGN({if_assign}, {else_assign})"
    return None


def _extract_nested_if_signature(stmts, source_bytes) -> str | None:
    if_node = stmts[0]
    if if_node.type != "if_statement":
        return None
    cond_text = None
    bool_op = _get_child_by_type(if_node, "boolean_operator")
    if bool_op:
        cond_text = (
            source_bytes[bool_op.start_byte : bool_op.end_byte]
            .decode("utf-8", errors="ignore")
            .strip()
        )
    else:
        if_body = _get_child_by_type(if_node, "block")
        if if_body:
            inner_if = None
            for child in if_body.children:
                if child.type == "if_statement":
                    inner_if = child
                    break
                elif child.type == "expression_statement":
                    inner = _get_child_by_type(child, "if_statement")
                    if inner:
                        inner_if = inner
                        break
            if inner_if:
                outer_cond = None
                for child in if_node.children:
                    if child.type not in ("if", ":", "block", "comment"):
                        outer_cond = (
                            source_bytes[child.start_byte : child.end_byte]
                            .decode("utf-8", errors="ignore")
                            .strip()
                        )
                        break
                inner_cond = None
                for child in inner_if.children:
                    if child.type not in ("if", ":", "block", "comment"):
                        inner_cond = (
                            source_bytes[child.start_byte : child.end_byte]
                            .decode("utf-8", errors="ignore")
                            .strip()
                        )
                        break
                if outer_cond and inner_cond:
                    cond_text = f"{outer_cond} and {inner_cond}"
                    inner_body = _get_child_by_type(inner_if, "block")
                    if inner_body:
                        for child in inner_body.children:
                            if child.type == "return_statement":
                                for sub in child.children:
                                    if sub.type not in ("return",):
                                        true_val = (
                                            source_bytes[sub.start_byte : sub.end_byte]
                                            .decode("utf-8", errors="ignore")
                                            .strip()
                                        )
                                        false_val = None
                                        for s in stmts[1:]:
                                            if s.type == "return_statement":
                                                for ss in s.children:
                                                    if ss.type not in ("return",):
                                                        false_val = (
                                                            source_bytes[
                                                                ss.start_byte : ss.end_byte
                                                            ]
                                                            .decode("utf-8", errors="ignore")
                                                            .strip()
                                                        )
                                        if true_val and false_val:
                                            return (
                                                f"BOOL_CHECK({cond_text}, {true_val}, {false_val})"
                                            )
                                        return None
                return None
            else:
                return None
        if not cond_text:
            for child in if_node.children:
                if child.type not in ("if", ":", "block", "else_clause", "comment"):
                    cond_text = (
                        source_bytes[child.start_byte : child.end_byte]
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )
                    break
    if not cond_text:
        return None
    if_body = _get_child_by_type(if_node, "block")
    true_val = None
    if if_body:
        for child in if_body.children:
            if child.type == "return_statement":
                for sub in child.children:
                    if sub.type not in ("return",):
                        true_val = (
                            source_bytes[sub.start_byte : sub.end_byte]
                            .decode("utf-8", errors="ignore")
                            .strip()
                        )
                        break
    false_val = None
    for s in stmts[1:]:
        if s.type == "return_statement":
            for child in s.children:
                if child.type not in ("return",):
                    false_val = (
                        source_bytes[child.start_byte : child.end_byte]
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )
    if true_val and false_val:
        return f"BOOL_CHECK({cond_text}, {true_val}, {false_val})"
    return None


def _extract_lbyl_signature(stmts, source_bytes) -> str | None:
    if_node = stmts[0]
    cond = _get_child_by_type(if_node, "comparison_operator")
    if not cond:
        cond = _get_child_by_type(if_node, "boolean_operator")
    if not cond:
        for child in if_node.children:
            if child.type not in ("if", ":", "block", "comment"):
                cond = child
                break
    if not cond:
        return None
    if_body = _get_child_by_type(if_node, "block")
    fallback = None
    if if_body:
        for child in if_body.children:
            if child.type == "return_statement":
                for sub in child.children:
                    if sub.type not in ("return",):
                        fallback = (
                            source_bytes[sub.start_byte : sub.end_byte]
                            .decode("utf-8", errors="ignore")
                            .strip()
                        )
                        break
    main_op = None
    for s in stmts[1:]:
        if s.type == "return_statement":
            for sub in s.children:
                if sub.type not in ("return",):
                    main_op = (
                        source_bytes[sub.start_byte : sub.end_byte]
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )
    if fallback and main_op:
        return f"SAFE_OP({main_op}, {fallback})"
    return None


def _extract_try_signature(try_node, source_bytes) -> str | None:
    try_body = _get_child_by_type(try_node, "block")
    if not try_body:
        return None
    try_op = None
    for child in try_body.children:
        if child.type == "return_statement":
            for sub in child.children:
                if sub.type not in ("return",):
                    try_op = (
                        source_bytes[sub.start_byte : sub.end_byte]
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )
                    break
    if not try_op:
        return None
    fallback = None
    for child in try_node.children:
        if child.type == "except_clause":
            except_body = _get_child_by_type(child, "block")
            if except_body:
                for sub in except_body.children:
                    if sub.type == "return_statement":
                        for ss in sub.children:
                            if ss.type not in ("return",):
                                fallback = (
                                    source_bytes[ss.start_byte : ss.end_byte]
                                    .decode("utf-8", errors="ignore")
                                    .strip()
                                )
                                break
    if try_op and fallback:
        return f"SAFE_OP({try_op}, {fallback})"
    return None


def _extract_ternary_signature(node, source_bytes) -> str | None:
    children = [c for c in node.children if c.type not in ("if", "else")]
    if len(children) == 3:
        true_text = (
            source_bytes[children[0].start_byte : children[0].end_byte]
            .decode("utf-8", errors="ignore")
            .strip()
        )
        false_text = (
            source_bytes[children[2].start_byte : children[2].end_byte]
            .decode("utf-8", errors="ignore")
            .strip()
        )
        return f"COND_ASSIGN({true_text}, {false_text})"
    return None
