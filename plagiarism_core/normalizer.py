"""Semantic normalization with tree-sitter query-based rewrite rules.

Provides an improved canonicalize_type4 that handles the three critical
Type 4 equivalence patterns that the base canonicalizer misses:
  1. while-iter-next → for loop
  2. list(map(lambda)) → list comprehension
  3. x is None → x == None normalization
"""

import logging
import re

logger = logging.getLogger(__name__)


def _find_iterator_while_patterns(
    source: str, lang: str = "python",
    tree=None, source_bytes: bytes = None,
) -> list[dict]:
    """Find while-True-try-next-except-StopIteration patterns using tree-sitter.

    Returns list of dicts with:
      byte_start, byte_end: position of the while statement
      var_name: the variable being assigned from next()
      iter_name: the iterator being iterated over
      pattern_source: the source inside the while body (excluding the try)
    """
    if tree is None or source_bytes is None:
        from .fingerprinting.parser import parse_string_once
        try:
            tree, source_bytes = parse_string_once(source, lang)
        except Exception:
            return []

    results = []
    root = tree.root_node

    def _find_child_by_type(node, child_type):
        for child in node.children:
            if child.type == child_type:
                return child
        return None

    def visit(node):
        if node.type == "while_statement":
            cond = node.child_by_field_name("condition")
            if cond is None:
                cond = _find_child_by_type(node, "condition")
            if cond is None:
                cond = _find_child_by_type(node, "true")
            if cond:
                cond_text = source_bytes[cond.start_byte:cond.end_byte].decode("utf-8", errors="ignore")
                if cond_text.strip() == "True":
                    body_node = node.child_by_field_name("body")
                    if body_node is None:
                        body_node = _find_child_by_type(node, "block")
                    if body_node:
                        _analyze_while_body(node, body_node, source_bytes, results)
        cursor = node.walk()
        if cursor.goto_first_child():
            while True:
                visit(cursor.node)
                if not cursor.goto_next_sibling():
                    break

    visit(root)
    return results


def _analyze_while_body(while_node, body_node, source_bytes, results):
    """Analyze a while-loop body for the iterator pattern."""
    while_children = [c for c in body_node.children if c.type != "block"] if body_node.type == "block" else body_node.children

    for idx, child in enumerate(while_children):
        if child.type == "try_statement":
            try_body = child.child_by_field_name("body")
            if try_body is None:
                for c in child.children:
                    if c.type in ("body", "block"):
                        try_body = c
                        break

            if not try_body:
                continue

            # Extract the assignment from inside the try body
            var_name = None
            iter_name = None
            for tc in try_body.children:
                if tc.type == "expression_statement":
                    expr = tc.children[0] if tc.children else None
                    if expr and expr.type == "assignment":
                        left = expr.children[0] if expr.children else None
                        right = expr.children[2] if len(expr.children) > 2 else None
                        if left and right and right.type == "call":
                            fn = right.children[0] if right.children else None
                            args_node = right.children[1] if len(right.children) > 1 else None
                            if fn and fn.type == "identifier":
                                fn_name = source_bytes[fn.start_byte:fn.end_byte].decode("utf-8", errors="ignore")
                                if fn_name == "next" and args_node:
                                    named_args = [c for c in args_node.children if c.is_named]
                                    arg = named_args[0] if named_args else None
                                    if arg and arg.type == "identifier":
                                        var_name = source_bytes[left.start_byte:left.end_byte].decode("utf-8", errors="ignore")
                                        iter_name = source_bytes[arg.start_byte:arg.end_byte].decode("utf-8", errors="ignore")
                                        break

            if not var_name:
                continue

            # Check except handler catches StopIteration with break
            has_stop_iteration = False
            for c in child.children:
                if c.type in ("except_clause", "handler"):
                    handler_body = c.child_by_field_name("body")
                    if handler_body is None:
                        for cc in c.children:
                            if cc.type in ("body", "block"):
                                handler_body = cc
                                break
                    exc_type = None
                    for cc in c.children:
                        if cc.type == "identifier":
                            exc_type = source_bytes[cc.start_byte:cc.end_byte].decode("utf-8", errors="ignore")
                            break
                    if exc_type == "StopIteration" and handler_body:
                        for hc in handler_body.children:
                            if hc.type == "break_statement":
                                has_stop_iteration = True
                                break
                    if has_stop_iteration:
                        break

            if not has_stop_iteration:
                continue

            # Found the pattern! Build the replacement using statements AFTER the try
            body_source = ""
            for remaining in while_children[idx + 1:]:
                body_source += source_bytes[remaining.start_byte:remaining.end_byte].decode("utf-8", errors="ignore") + "\n"

            # Try to find the assignment that creates the iterator
            # e.g., child_it = iter(node.children) -> extract 'node.children'
            iterable_source = iter_name
            p = while_node.prev_sibling
            while p is not None:
                if p.type == "expression_statement":
                    for pc in p.children:
                        if pc.type == "assignment":
                            al = pc.children[0] if pc.children else None
                            ar = pc.children[2] if len(pc.children) > 2 else None
                            if al and al.type == "identifier":
                                left_name = source_bytes[al.start_byte:al.end_byte].decode("utf-8", errors="ignore")
                                if left_name == iter_name and ar and ar.type == "call":
                                    ac_fn = ar.children[0] if ar.children else None
                                    if ac_fn and ac_fn.type == "identifier":
                                        ac_name = source_bytes[ac_fn.start_byte:ac_fn.end_byte].decode("utf-8", errors="ignore")
                                        if ac_name == "iter":
                                            # Extract the actual iterable expression
                                            ac_args = ar.children[1] if len(ar.children) > 1 else None
                                            if ac_args:
                                                named = [c for c in ac_args.children if c.is_named]
                                                if named:
                                                    iterable_source = source_bytes[named[0].start_byte:named[0].end_byte].decode("utf-8", errors="ignore")
                                            break
                p = p.prev_sibling

            results.append({
                "byte_start": while_node.start_byte,
                "byte_end": while_node.end_byte,
                "var_name": var_name,
                "iter_name": iterable_source,
                "orig_iter_name": iter_name,
                "body_source": body_source.strip(),
            })
            return  # only one such pattern per while


def _apply_iterator_while_rewrite(
    source: str, lang: str = "python",
    tree=None, source_bytes: bytes = None,
) -> str:
    """Replace while-True-try-next-except-StopIteration with equivalent for-loop strings."""
    patterns = _find_iterator_while_patterns(source, lang, tree=tree, source_bytes=source_bytes)
    if not patterns:
        return source

    # Work with lines for indentation-safe replacement
    lines = source.splitlines()
    patterns.sort(key=lambda p: p["byte_start"], reverse=True)

    for p in patterns:
        # Detect the while statement's indentation from the source
        # Find which line contains the while statement
        cum = 0
        while_line_idx = -1
        for i, line in enumerate(lines):
            next_cum = cum + len(line) + 1
            if cum <= p["byte_start"] < next_cum:
                while_line_idx = i
                break
            cum = next_cum

        if while_line_idx < 0:
            continue

        while_line = lines[while_line_idx]
        while_indent = len(while_line) - len(while_line.lstrip())
        body_indent = while_indent + 4  # body of for-loop gets +4

        # Build the replacement for-loop using proper indentation
        body_source = p["body_source"]
        body_lines = body_source.split("\n")
        reindented_body = []
        for bl in body_lines:
            if bl.strip():
                # Dedent by the original while body's indent level
                # The body_source was extracted from AST, so it has its original indentation
                # We need to re-indent it to the for-loop body level
                stripped = bl.strip()
                reindented_body.append(" " * body_indent + stripped)
            else:
                reindented_body.append("")

        replacement_line = " " * while_indent + f"for {p['var_name']} in {p['iter_name']}:"
        replacement_body = "\n".join(reindented_body)

        # Find the iter assignment line to remove
        iter_assign_line_idx = None
        orig_iter = p.get("orig_iter_name", "")
        if orig_iter and while_line_idx > 0:
            prev_line = lines[while_line_idx - 1].strip()
            if prev_line.startswith(f"{orig_iter} = ") or prev_line.startswith(f"{orig_iter}="):
                if "iter(" in prev_line:
                    iter_assign_line_idx = while_line_idx - 1

        # Rebuild lines
        new_lines = []
        skip_while_statement = False

        for i, line in enumerate(lines):
            # Skip the iter assignment line
            if i == iter_assign_line_idx:
                # Skip it and don't add to output
                continue

            # When we reach the while statement line, replace it with the for loop
            if i == while_line_idx:
                new_lines.append(replacement_line)
                if replacement_body.strip():
                    new_lines.append(replacement_body)
                skip_while_statement = True
                continue

            # Skip lines that are part of the while body (they're inside the removed while)
            if skip_while_statement:
                # The while body lines end when we reach a line with the same or less indentation
                line_indent = len(line) - len(line.lstrip())
                if not line.strip() or line_indent > while_indent:
                    continue
                else:
                    skip_while_statement = False

            new_lines.append(line)

        lines = new_lines

    return "\n".join(lines)


def _find_map_lambda_patterns(
    source: str, lang: str = "python",
    tree=None, source_bytes: bytes = None,
) -> list[dict]:
    """Find list(map(lambda ...)) or list(filter(lambda ...)) patterns."""
    if tree is None or source_bytes is None:
        from .fingerprinting.parser import parse_string_once
        try:
            tree, source_bytes = parse_string_once(source, lang)
        except Exception:
            return []

    results = []

    def visit(node):
        if node.type == "call":
            fn = node.child_by_field_name("function")
            if fn is None:
                fn = node.children[0] if node.children else None
            args_node = node.child_by_field_name("arguments")
            if args_node is None:
                args_node = node.children[1] if len(node.children) > 1 else None
            if fn and fn.type == "identifier":
                fn_name = source_bytes[fn.start_byte:fn.end_byte].decode("utf-8", errors="ignore")
                if fn_name == "list" and args_node:
                    named_args = [c for c in args_node.children if c.is_named]
                    inner = named_args[0] if named_args else None
                    # Handle simple argument (no gunk)
                    if inner and inner.type == "call":
                        inner_fn = inner.child_by_field_name("function")
                        if inner_fn is None:
                            inner_fn = inner.children[0] if inner.children else None
                        inner_args = inner.child_by_field_name("arguments")
                        if inner_args is None:
                            inner_args = inner.children[1] if len(inner.children) > 1 else None
                        if inner_fn and inner_fn.type == "identifier":
                            inner_name = source_bytes[inner_fn.start_byte:inner_fn.end_byte].decode("utf-8", errors="ignore")
                            if inner_name in ("map", "filter") and inner_args:
                                named_inner = [c for c in inner_args.children if c.is_named]
                                lambda_node = named_inner[0] if len(named_inner) > 0 else None
                                iter_node = named_inner[1] if len(named_inner) > 1 else None
                                if lambda_node and lambda_node.type == "lambda" and iter_node:
                                    lambda_params = lambda_node.child_by_field_name("parameters")
                                    if lambda_params is None:
                                        for c in lambda_node.children:
                                            if c.type in ("lambda_parameters", "parameters"):
                                                lambda_params = c
                                                break
                                    lambda_body = lambda_node.child_by_field_name("body")
                                    if lambda_body is None:
                                        for c in lambda_node.children:
                                            if c.is_named and c.type in ("body", "expression"):
                                                lambda_body = c
                                                break
                                    if lambda_params and lambda_body:
                                        param_text = source_bytes[lambda_params.start_byte:lambda_params.end_byte].decode("utf-8", errors="ignore")
                                        body_text = source_bytes[lambda_body.start_byte:lambda_body.end_byte].decode("utf-8", errors="ignore")
                                        iter_text = source_bytes[iter_node.start_byte:iter_node.end_byte].decode("utf-8", errors="ignore")
                                        param_clean = param_text.strip().lstrip("(").rstrip(")")
                                        results.append({
                                            "byte_start": node.start_byte,
                                            "byte_end": node.end_byte,
                                            "param": param_clean,
                                            "body": body_text.strip(),
                                            "iter": iter_text.strip(),
                                            "is_map": inner_name == "map",
                                        })
        cursor = node.walk()
        if cursor.goto_first_child():
            while True:
                visit(cursor.node)
                if not cursor.goto_next_sibling():
                    break

    visit(tree.root_node)
    return results


def _apply_map_lambda_rewrite(
    source: str, lang: str = "python",
    tree=None, source_bytes: bytes = None,
) -> str:
    """Replace list(map(lambda x: expr, iter)) with [expr for x in iter]."""
    patterns = _find_map_lambda_patterns(source, lang, tree=tree, source_bytes=source_bytes)
    if not patterns:
        return source

    source_bytes = source.encode("utf-8")
    patterns.sort(key=lambda p: p["byte_start"], reverse=True)

    for p in patterns:
        if p["is_map"]:
            replacement = f"[{p['body']} for {p['param']} in {p['iter']}]"
        else:
            replacement = f"[{p['param']} for {p['param']} in {p['iter']} if {p['body']}]"
        before = source_bytes[:p["byte_start"]]
        after = source_bytes[p["byte_end"]:]
        source_bytes = before + replacement.encode("utf-8") + after

    return source_bytes.decode("utf-8", errors="ignore")


def _normalize_identity_comparisons(source: str, lang: str = "python") -> str:
    """Normalize x is None -> x == None and x is not None -> x != None."""
    # Simple string-level replacement for common identity comparison patterns
    lines = source.splitlines()
    result = []
    for line in lines:
        line = re.sub(r'\bis\s+None\b', '== None', line)
        line = re.sub(r'\bis\s+not\s+None\b', '!= None', line)
        result.append(line)
    return "\n".join(result)


def canonicalize_type4_v2(
    source: str, lang_code: str = "python",
    tree=None, source_bytes: bytes = None,
) -> str:
    """Improved Type 4 canonicalization with rewrite rules.

    Applies three critical rewrite rules before the base canonicalizer:
    1. while-iter-next patterns → for loops
    2. list(map(lambda)) patterns → list comprehensions
    3. Identity comparison normalization

    This improves recall on Type 4 pairs that the base canonicalizer misses.
    """
    if not source or not source.strip():
        return "[empty]"

    # Apply rewrite rules in sequence.
    # Each rule may modify the source string, making the original tree stale,
    # so only pass tree to the first rule (which runs on the unmodified source).
    if lang_code == "python":
        source = _apply_iterator_while_rewrite(source, lang_code, tree=tree, source_bytes=source_bytes)
        source = _apply_map_lambda_rewrite(source, lang_code)
        source = _normalize_identity_comparisons(source, lang_code)

    # Delegate to base canonicalizer (parses the modified source)
    from .canonicalizer import canonicalize_type4 as _base_canonicalize
    return _base_canonicalize(source, lang_code=lang_code)
