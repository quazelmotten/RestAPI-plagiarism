"""Return pattern and collection extraction."""

from ...canonicalizer import _get_child_by_type


def _extract_return_chain_signature(node, source_bytes) -> str | None:
    ret_vals = []
    body = _get_child_by_type(node, "block")
    if body is None:
        body = _get_child_by_type(node, "compound_statement")
    if body is None:
        body = _get_child_by_type(node, "statement_block")
    if body is None:
        return None
    from .conditionals import _extract_return_value

    ret = _extract_return_value(body, source_bytes)
    if ret is None:
        return None
    ret_vals.append(ret)
    has_else = False
    for child in node.children:
        if child.type == "elif_clause":
            elif_body = _get_child_by_type(child, "block")
            if elif_body is None:
                elif_body = _get_child_by_type(child, "compound_statement")
            if elif_body is None:
                return None
            elif_ret = _extract_return_value(elif_body, source_bytes)
            if elif_ret is None:
                return None
            ret_vals.append(elif_ret)
        elif child.type == "else_clause":
            else_body = _get_child_by_type(child, "block")
            if else_body is None:
                else_body = _get_child_by_type(child, "compound_statement")
            if else_body is None:
                else_body = _get_child_by_type(child, "statement_block")
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


def _extract_tuple_return_signature(stmts, source_bytes) -> str | None:
    if len(stmts) == 1 and stmts[0].type == "return_statement":
        ret = stmts[0]
        for child in ret.children:
            if child.type == "tuple":
                elems = []
                for sub in child.children:
                    if sub.type not in ("(", ",", ")"):
                        elem = (
                            source_bytes[sub.start_byte : sub.end_byte]
                            .decode("utf-8", errors="ignore")
                            .strip()
                        )
                        if elem:
                            elems.append(elem)
                if elems:
                    return f"RETURNS_TUPLE({', '.join(elems)})"
    if len(stmts) >= 2:
        last = stmts[-1]
        if last.type == "return_statement":
            tuple_node = None
            for child in last.children:
                if child.type == "tuple":
                    tuple_node = child
                    break
            if tuple_node:
                ret_vars = []
                for sub in tuple_node.children:
                    if sub.type == "identifier":
                        var = (
                            source_bytes[sub.start_byte : sub.end_byte]
                            .decode("utf-8", errors="ignore")
                            .strip()
                        )
                        ret_vars.append(var)
                if len(ret_vars) >= 2:
                    assignments = []
                    for i in range(len(stmts) - 1):
                        stmt = stmts[i]
                        if stmt.type == "expression_statement":
                            assign = _get_child_by_type(stmt, "assignment")
                            if assign:
                                target = None
                                for c in assign.children:
                                    if c.type == "identifier":
                                        target = (
                                            source_bytes[c.start_byte : c.end_byte]
                                            .decode("utf-8", errors="ignore")
                                            .strip()
                                        )
                                        break
                                if target:
                                    after_eq = False
                                    value_node = None
                                    for c in assign.children:
                                        if after_eq and c.type not in ("comment",):
                                            value_node = c
                                            break
                                        if c.type == "=":
                                            after_eq = True
                                    if value_node:
                                        assignments.append((target, value_node))
                    if len(assignments) == len(ret_vars):
                        all_match = True
                        for (t, _), rv in zip(assignments, ret_vars, strict=False):
                            if t != rv:
                                all_match = False
                                break
                        if all_match:
                            exprs = []
                            for _, val_node in assignments:
                                expr = (
                                    source_bytes[val_node.start_byte : val_node.end_byte]
                                    .decode("utf-8", errors="ignore")
                                    .strip()
                                )
                                exprs.append(expr)
                            return f"RETURNS_TUPLE({', '.join(exprs)})"
    return None


def _extract_dict_pattern(stmts, source_bytes) -> str | None:
    if len(stmts) == 1 and stmts[0].type == "return_statement":
        for child in stmts[0].children:
            if child.type == "dict_comprehension":
                key_expr = ""
                val_expr = ""
                iter_expr = ""
                pair_node = _get_child_by_type(child, "pair")
                if pair_node:
                    for sub in pair_node.children:
                        if sub.type == "key":
                            key_expr = (
                                source_bytes[sub.start_byte : sub.end_byte]
                                .decode("utf-8", errors="ignore")
                                .strip()
                            )
                        elif sub.type == "value":
                            val_expr = (
                                source_bytes[sub.start_byte : sub.end_byte]
                                .decode("utf-8", errors="ignore")
                                .strip()
                            )
                for sub in child.children:
                    if sub.type == "for_in_clause":
                        for ss in sub.children:
                            if ss.type in ("call", "identifier", "attribute"):
                                text = (
                                    source_bytes[ss.start_byte : ss.end_byte]
                                    .decode("utf-8", errors="ignore")
                                    .strip()
                                )
                                if "range" in text or "enumerate" in text or "items" in text:
                                    iter_expr = text
                if key_expr and val_expr and iter_expr:
                    return f"DICT_COLLECT({key_expr}, {val_expr}, {iter_expr})"
    if len(stmts) >= 3:
        first = stmts[0]
        if first.type == "expression_statement":
            first = _get_child_by_type(first, "assignment")
        if first and first.type == "assignment":
            children = [c for c in first.children if c.type not in ("comment",)]
            if len(children) >= 3 and children[2].type == "dictionary":
                dict_children = [c for c in children[2].children if c.type not in ("comment",)]
                if len(dict_children) == 2:
                    target = (
                        source_bytes[children[0].start_byte : children[0].end_byte]
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )
                    for s in stmts[1:-1]:
                        for_node = _get_child_by_type(s, "for_statement")
                        if for_node:
                            body = _get_child_by_type(for_node, "block")
                            if body:
                                for bstmt in body.children:
                                    if bstmt.type == "expression_statement":
                                        assign = _get_child_by_type(bstmt, "assignment")
                                        if assign:
                                            achildren = [
                                                c
                                                for c in assign.children
                                                if c.type not in ("comment",)
                                            ]
                                            if len(achildren) >= 3:
                                                lhs = source_bytes[
                                                    achildren[0].start_byte : achildren[0].end_byte
                                                ].decode("utf-8", errors="ignore")
                                                if "[" in lhs and lhs.startswith(target):
                                                    key_expr = lhs.split("[")[1].rstrip("]").strip()
                                                    val_expr = (
                                                        source_bytes[
                                                            achildren[2].start_byte : achildren[
                                                                2
                                                            ].end_byte
                                                        ]
                                                        .decode("utf-8", errors="ignore")
                                                        .strip()
                                                    )
                                                    iter_expr = ""
                                                    for fc in for_node.children:
                                                        if fc.type in (
                                                            "call",
                                                            "identifier",
                                                            "attribute",
                                                        ):
                                                            text = (
                                                                source_bytes[
                                                                    fc.start_byte : fc.end_byte
                                                                ]
                                                                .decode("utf-8", errors="ignore")
                                                                .strip()
                                                            )
                                                            if fc.type != "identifier":
                                                                iter_expr = text
                                                    if iter_expr:
                                                        return f"DICT_COLLECT({key_expr}, {val_expr}, {iter_expr})"
    return None
