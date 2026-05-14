from __future__ import annotations

import builtins
import keyword
import random
import re
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

from plagiarism_core.annotation import TransformSpan

PY_LANGUAGE = Language(tspython.language())

SKIP_NAMES = set(dir(builtins)) | set(keyword.kwlist)


class AnnotatedCloneGenerator:
    def __init__(self, seed: int = 42):
        self.parser = Parser()
        self.parser.language = PY_LANGUAGE
        self.rng = random.Random(seed)

    def parse(self, code: str):
        return self.parser.parse(code.encode("utf-8"))

    # ──────────────────────────────────────────────
    # TYPE 1 – Lexical
    # ──────────────────────────────────────────────

    def generate_type1(self, source_code: str, clone_num: int = 1) -> list[tuple[str, list[TransformSpan]]]:
        clones = []
        for _ in range(clone_num):
            code = source_code
            spans: list[TransformSpan] = []

            code = self._normalize_whitespace(code)

            code, s = self._inject_blank_lines(code)
            spans.extend(s)

            code, s = self._inject_comments(code)
            spans.extend(s)

            clones.append((code, spans))
        return clones

    def _normalize_whitespace(self, code: str) -> str:
        lines = code.splitlines()
        return "\n".join(line.rstrip() for line in lines) + "\n"

    def _inject_blank_lines(self, code: str) -> tuple[str, list[TransformSpan]]:
        lines = code.splitlines()
        result: list[str] = []
        spans: list[TransformSpan] = []
        offset = 0
        for i, line in enumerate(lines):
            result.append(line)
            if line.strip() and self.rng.random() < 0.15:
                result.append("")
                spans.append(TransformSpan(
                    kind="insert_blank_line",
                    orig_start=i,
                    orig_end=i,
                    clone_start=i + 1 + offset,
                    clone_end=i + 1 + offset,
                ))
                offset += 1
        return "\n".join(result), spans

    def _inject_comments(self, code: str) -> tuple[str, list[TransformSpan]]:
        lines = code.splitlines()
        result: list[str] = []
        spans: list[TransformSpan] = []
        offset = 0
        for i, line in enumerate(lines):
            result.append(line)
            stripped = line.strip()
            if stripped and not stripped.endswith(":"):
                if self.rng.random() < 0.1:
                    indent = len(line) - len(line.lstrip())
                    text = "# " + "".join(self.rng.choices("abcdefghijklmnopqrstuvwxyz", k=6))
                    result.append(" " * indent + text)
                    spans.append(TransformSpan(
                        kind="inject_comment",
                        orig_start=i,
                        orig_end=i,
                        clone_start=i + 1 + offset,
                        clone_end=i + 1 + offset,
                        detail={"text": text},
                    ))
                    offset += 1
        return "\n".join(result), spans

    # ──────────────────────────────────────────────
    # TYPE 2 – Renamed identifiers
    # ──────────────────────────────────────────────

    def generate_type2(self, source_code: str, clone_num: int = 1) -> list[tuple[str, list[TransformSpan]]]:
        clones = []
        for _ in range(clone_num):
            tree = self.parse(source_code)
            identifiers = self._extract_identifiers(tree.root_node, source_code)
            if not identifiers:
                clones.append((source_code, []))
                continue

            rename_map = self._create_rename_map(identifiers)
            code, spans = self._apply_rename(source_code, rename_map)
            clones.append((code, spans))
        return clones

    def _extract_identifiers(self, node, source_code: str) -> list[tuple[str, tuple[int, int], int]]:
        ids: list[tuple[str, tuple[int, int], int]] = []

        def visit(n):
            if n.type == "identifier":
                text = source_code[n.start_byte : n.end_byte]
                if text.startswith("__") and text.endswith("__"):
                    return
                if text in SKIP_NAMES:
                    return
                if self._is_method_name(n):
                    return
                # Skip print()/input()/raise argument identifiers
                if self._inside_unrenamable_call(n, source_code):
                    return
                ids.append((text, (n.start_byte, n.end_byte), n.start_point[0]))
            for child in n.children:
                visit(child)

        visit(node)
        return ids

    def _is_method_name(self, node) -> bool:
        p = node.parent
        if p and p.type == "attribute":
            attr = p.child_by_field_name("attribute")
            return attr == node
        return False

    def _inside_unrenamable_call(self, node, source_code: str) -> bool:
        """Check if identifier is inside a print()/input()/raise that should not be renamed."""
        p = node.parent
        if p is None:
            return False
        if p.type == "call":
            func = p.child_by_field_name("function")
            if func and source_code[func.start_byte : func.end_byte] in ("print", "input"):
                return True
        if p.type == "raise_statement":
            return True
        # Also check grandparent for nested calls like print(f(x))
        if p.type == "argument_list" and p.parent and p.parent.type == "call":
            func = p.parent.child_by_field_name("function")
            if func and source_code[func.start_byte : func.end_byte] in ("print", "input"):
                return True
        return False

    def _create_rename_map(self, identifiers: list[tuple[str, tuple[int, int], int]]) -> dict[str, str]:
        unique = list({id[0] for id in identifiers})
        self.rng.shuffle(unique)
        rename_map: dict[str, str] = {}
        for name in unique:
            if len(name) <= 2:
                new_name = "".join(self.rng.choices("abcdefghijklmnopqrstuvwxyz", k=3))
            else:
                prefix = self.rng.choice(["get_", "set_", "calc_", "data_", "val_", "temp_", "new_"])
                suffix = "".join(self.rng.choices("abcdefghijklmnopqrstuvwxyz", k=max(1, len(name) - 2)))
                new_name = prefix + suffix if self.rng.random() < 0.5 else name[:1] + suffix
            rename_map[name] = new_name
        return rename_map

    def _apply_rename(self, code: str, rename_map: dict[str, str]) -> tuple[str, list[TransformSpan]]:
        lines = code.split("\n")
        spans: list[TransformSpan] = []
        # Pre-compile patterns (avoids re.compile per line per identifier)
        patterns = [(re.compile(r"\b" + re.escape(old) + r"\b"), old, new) for old, new in rename_map.items()]
        for i, line in enumerate(lines):
            new_line = line
            for pat, old, new in patterns:
                for m in pat.finditer(new_line):
                    spans.append(TransformSpan(
                        kind="rename_identifier",
                        orig_start=i,
                        orig_end=i,
                        clone_start=i,
                        clone_end=i,
                        detail={"old": old, "new": new},
                    ))
                new_line = pat.sub(new, new_line)
            lines[i] = new_line
        return "\n".join(lines), spans

    # ──────────────────────────────────────────────
    # TYPE 3 – Structural / reordering
    # ──────────────────────────────────────────────

    def generate_type3(self, source_code: str, clone_num: int = 1) -> list[tuple[str, list[TransformSpan]]]:
        clones = []
        for _ in range(clone_num):
            code = source_code
            spans: list[TransformSpan] = []

            if self.rng.random() < 0.4:
                code, s = self._add_stub_function(code)
                spans.extend(s)
            if self.rng.random() < 0.5:
                code, s = self._reorder_functions(code)
                spans.extend(s)
            if self.rng.random() < 0.3:
                code, s = self._reorder_class_methods(code)
                spans.extend(s)
            if self.rng.random() < 0.6:
                code, s = self._reorder_statements_in_blocks(code)
                spans.extend(s)
            if self.rng.random() < 0.3:
                code, s = self._inline_variables(code)
                spans.extend(s)
            if self.rng.random() < 0.05:
                code, s = self._add_prints(code)
                spans.extend(s)

            clones.append((code, spans))
        return clones

    def _add_stub_function(self, code: str) -> tuple[str, list[TransformSpan]]:
        stub = "\ndef _unused_stub():\n    pass\n\n"
        spans = [TransformSpan(kind="add_stub_function", clone_start=0, clone_end=2)]
        return stub + code, spans

    def _reorder_functions(self, code: str) -> tuple[str, list[TransformSpan]]:
        tree = self.parse(code)
        func_pattern = re.compile(r"^def (\w+)\s*\(")
        lines = code.split("\n")

        func_lines: dict[str, str] = {}
        func_order: list[str] = []
        current_name: str | None = None
        current_lines: list[str] = []

        for line in lines:
            m = func_pattern.match(line)
            if m:
                if current_name:
                    func_lines[current_name] = "\n".join(current_lines)
                current_name = m.group(1)
                func_order.append(current_name)
                current_lines = [line]
            elif current_name is not None:
                current_lines.append(line)

        if current_name:
            func_lines[current_name] = "\n".join(current_lines)

        if len(func_order) <= 1:
            return code, []

        old_order = list(func_order)
        self.rng.shuffle(func_order)

        spans: list[TransformSpan] = []
        orig_lines_of = {}
        for name in old_order:
            ftext = func_lines[name]
            first_line_idx = code.index(ftext.split("\n")[0]) if ftext else -1
            if first_line_idx >= 0:
                start_ln = code[:first_line_idx].count("\n")
            else:
                start_ln = 0
            end_ln = start_ln + ftext.count("\n")
            orig_lines_of[name] = (start_ln, end_ln)

        new_code = "\n\n".join(func_lines[name] for name in func_order if name in func_lines)

        # Compute clone positions
        clone_pos = {}
        current_line = 0
        for name in func_order:
            if name not in func_lines:
                continue
            ftext = func_lines[name]
            flines = ftext.count("\n") + 1
            clone_pos[name] = (current_line, current_line + flines - 1)
            current_line += flines + 1  # +1 for the blank line separator

        for name in func_order:
            if name in orig_lines_of and name in clone_pos:
                spans.append(TransformSpan(
                    kind="reorder_function",
                    orig_start=orig_lines_of[name][0],
                    orig_end=orig_lines_of[name][1],
                    clone_start=clone_pos[name][0],
                    clone_end=clone_pos[name][1],
                    detail={"name": name},
                ))

        return new_code, spans

    def _reorder_class_methods(self, code: str) -> tuple[str, list[TransformSpan]]:
        tree = self.parse(code)
        spans: list[TransformSpan] = []
        result = code

        class_pattern = re.compile(r"^class (\w+)")
        method_pattern = re.compile(r"^    def (\w+)")
        lines = result.split("\n")

        # Find class boundaries
        in_class = False
        class_start = -1
        class_end = -1
        method_blocks: list[tuple[str, int, int, str]] = []  # (name, start_line, end_line, text)

        for i, line in enumerate(lines):
            cm = class_pattern.match(line)
            if cm:
                if in_class and len(method_blocks) > 1:
                    # reorder methods in this class
                    self.rng.shuffle(method_blocks)
                    # Rebuild class lines
                    new_method_lines: list[str] = []
                    for m_name, _, _, m_text in method_blocks:
                        new_method_lines.append(m_text)
                    lines_part1 = lines[: class_start + 1]
                    lines_part2 = lines[class_end + 1 :]
                    result = "\n".join(lines_part1 + [""] + new_method_lines + [""] + lines_part2)
                    spans.append(TransformSpan(
                        kind="reorder_class_methods",
                        orig_start=class_start,
                        orig_end=class_end,
                        detail={"class": cm.group(1), "methods": [m[0] for m in method_blocks]},
                    ))
                    return result, spans

                in_class = True
                class_start = i
                method_blocks = []
            elif in_class:
                mm = method_pattern.match(line)
                if mm:
                    if method_blocks:
                        prev_name, prev_start, _, _ = method_blocks[-1]
                        method_blocks[-1] = (prev_name, prev_start, i - 1, "\n".join(lines[prev_start : i - 1]))
                    method_blocks.append((mm.group(1), i, i, line))
                elif not line.strip() or line.startswith(" "):
                    pass
                else:
                    # End of class
                    if method_blocks:
                        prev_name, prev_start, _, _ = method_blocks[-1]
                        method_blocks[-1] = (prev_name, prev_start, i - 1, "\n".join(lines[prev_start:i]))
                    if len(method_blocks) > 1:
                        self.rng.shuffle(method_blocks)
                        new_method_lines: list[str] = []
                        for m_name, _, _, m_text in method_blocks:
                            new_method_lines.append(m_text)
                        lines_part1 = lines[: class_start + 1]
                        lines_part2 = lines[i:]
                        result = "\n".join(lines_part1 + [""] + new_method_lines + [""] + lines_part2)
                        spans.append(TransformSpan(
                            kind="reorder_class_methods",
                            orig_start=class_start,
                            orig_end=i - 1,
                            detail={"class": None, "methods": [m[0] for m in method_blocks]},
                        ))
                        return result, spans
                    in_class = False

        # Handle class at end of file
        if in_class and len(method_blocks) > 1:
            if method_blocks:
                prev_name, prev_start, _, _ = method_blocks[-1]
                method_blocks[-1] = (prev_name, prev_start, len(lines) - 1, "\n".join(lines[prev_start:]))
            self.rng.shuffle(method_blocks)
            new_method_lines: list[str] = []
            for m_name, _, _, m_text in method_blocks:
                new_method_lines.append(m_text)
            lines_part1 = lines[: class_start + 1]
            result = "\n".join(lines_part1 + [""] + new_method_lines)
            spans.append(TransformSpan(
                kind="reorder_class_methods",
                orig_start=class_start,
                orig_end=len(lines) - 1,
                detail={"class": None, "methods": [m[0] for m in method_blocks]},
            ))

        return result, spans

    def _reorder_statements_in_blocks(self, code: str) -> tuple[str, list[TransformSpan]]:
        tree = self.parse(code)

        candidates: list[tuple] = []
        for block in self._find_blocks(tree.root_node):
            for i in range(len(block.children) - 1):
                a, b = block.children[i], block.children[i + 1]
                if a.type == "expression_statement" and b.type == "expression_statement":
                    if self._can_reorder(a, b, code):
                        candidates.append((a, b))

        if not candidates:
            return code, []

        a, b = self.rng.choice(candidates)
        a_text = code[a.start_byte : a.end_byte]
        b_text = code[b.start_byte : b.end_byte]
        between = code[a.end_byte : b.start_byte]
        new_code = code[: a.start_byte] + b_text + between + a_text + code[b.end_byte :]

        spans = [
            TransformSpan(
                kind="reorder_statement",
                orig_start=a.start_point[0],
                orig_end=b.end_point[0],
                clone_start=a.start_point[0],
                clone_end=b.end_point[0],
                detail={
                    "statement_a": a_text,
                    "statement_b": b_text,
                },
            )
        ]
        return new_code, spans

    def _find_blocks(self, node):
        blocks = []
        if node.type in ("block", "body"):
            blocks.append(node)
        for child in node.children:
            blocks.extend(self._find_blocks(child))
        return blocks

    def _can_reorder(self, node_a, node_b, code: str) -> bool:
        writes_a, reads_a = self._get_read_write(node_a, code)
        writes_b, reads_b = self._get_read_write(node_b, code)
        if writes_a is None or writes_b is None:
            return False
        return not (writes_a & (reads_b | writes_b) or writes_b & (reads_a | writes_a))

    def _get_read_write(self, node, code: str) -> tuple[set[str] | None, set[str] | None]:
        if node.type != "expression_statement":
            return None, None
        child = node.children[0]

        if child.type == "assignment":
            left = child.child_by_field_name("left")
            right = child.child_by_field_name("right")
            writes = self._identifiers_in_node(left, code) if left else set()
            reads = self._identifiers_in_node(right, code) if right else set()
            return writes, reads

        if child.type == "augmented_assignment":
            left = child.child_by_field_name("left")
            right = child.child_by_field_name("right")
            writes = self._identifiers_in_node(left, code) if left else set()
            reads = set(writes)
            if right:
                reads.update(self._identifiers_in_node(right, code))
            return writes, reads

        if child.type == "call":
            reads = self._identifiers_in_node(child, code)
            return set(), reads

        return None, None

    def _identifiers_in_node(self, node, code: str) -> set[str]:
        names: set[str] = set()

        def walk(n):
            if n.type == "identifier":
                names.add(code[n.start_byte : n.end_byte])
            for c in n.children:
                walk(c)

        walk(node)
        return names

    def _inline_variables(self, code: str) -> tuple[str, list[TransformSpan]]:
        lines = code.split("\n")
        spans: list[TransformSpan] = []
        result: list[str] = []
        for i, line in enumerate(lines):
            if "=" in line and "==" not in line and "!=" not in line:
                if self.rng.random() < 0.2:
                    spans.append(TransformSpan(
                        kind="inline_variable",
                        orig_start=i,
                        orig_end=i,
                        detail={"line": line.strip()},
                    ))
                    continue
            result.append(line)
        return "\n".join(result), spans

    def _add_prints(self, code: str) -> tuple[str, list[TransformSpan]]:
        lines = code.split("\n")
        spans: list[TransformSpan] = []
        result: list[str] = []
        offset = 0
        for i, line in enumerate(lines):
            result.append(line)
            if line.strip() and not line.strip().startswith("#"):
                if self.rng.random() < 0.05:
                    indent = len(line) - len(line.lstrip())
                    result.append(" " * indent + 'print("debug")')
                    spans.append(TransformSpan(
                        kind="inject_print",
                        orig_start=i,
                        orig_end=i,
                        clone_start=i + 1 + offset,
                        clone_end=i + 1 + offset,
                    ))
                    offset += 1
        return "\n".join(result), spans

    # ──────────────────────────────────────────────
    # TYPE 4 – Semantic / logic changes
    # ──────────────────────────────────────────────

    def generate_type4(self, source_code: str, clone_num: int = 1) -> list[tuple[str, list[TransformSpan]]]:
        clones = []
        transforms = [
            (self._convert_for_to_while, 0.5),
            (self._convert_while_to_for, 0.3),
            (self._convert_enumerate_to_range, 0.3),
            (self._convert_dict_iteration, 0.3),
            (self._convert_list_comprehension, 0.4),
            (self._convert_listcomp_to_loop, 0.3),
            (self._convert_in_to_any, 0.2),
            (self._change_comparison_operators, 0.4),
            (self._change_augmented_assignment, 0.3),
            # (self._swap_if_else_negation, 0.1),  # disabled – expensive regex on some files
            (self._split_compound_conditions, 0.2),
            (self._convert_ternary_to_ifelse, 0.3),
            (self._convert_sorted_to_sort, 0.2),
            (self._apply_de_morgan, 0.2),
            (self._convert_format_string, 0.3),
            (self._convert_eafp_to_lbyl, 0.2),
            (self._convert_call_unbound, 0.2),
        ]

        for _ in range(clone_num):
            code = source_code
            spans: list[TransformSpan] = []
            self.rng.shuffle(transforms)
            for fn, prob in transforms:
                if self.rng.random() < prob:
                    try:
                        code, s = fn(code)
                        spans.extend(s)
                    except Exception:
                        pass
            clones.append((code, spans))
        return clones

    # ---- T4 helpers ----

    def _annotated_sub(self, pattern, replacer, code: str, kind: str, limit: int = 5) -> tuple[str, list[TransformSpan]]:
        """Run re.sub with match tracking. replacer(match) -> (replacement_text, detail_dict_or_None)."""
        spans: list[TransformSpan] = []

        def wrapper(m):
            line_no = code[: m.start()].count("\n")
            end_line = code[: m.end()].count("\n")
            result, detail = replacer(m)
            spans.append(TransformSpan(
                kind=kind,
                orig_start=line_no,
                orig_end=end_line,
                detail=detail,
            ))
            return result

        new_code = re.sub(pattern, wrapper, code, count=limit)
        return new_code, spans

    def _convert_for_to_while(self, code: str) -> tuple[str, list[TransformSpan]]:
        pattern = re.compile(r"^([ \t]*)for\s+(\w+)\s+in\s+([^\n:]+):", re.MULTILINE)

        def replacer(m):
            indent, var, iterable = m.groups()
            return (
                f"{indent}{var}_it = iter({iterable})\n"
                f"{indent}while True:\n"
                f"{indent}    try:\n"
                f"{indent}        {var} = next({var}_it)\n"
                f"{indent}    except StopIteration:\n"
                f"{indent}        break"
            ), {"var": var, "iterable": iterable.strip(), "transformation": "for_to_while"}

        return self._annotated_sub(pattern, replacer, code, "convert_for_to_while")

    def _convert_while_to_for(self, code: str) -> tuple[str, list[TransformSpan]]:
        pattern = re.compile(
            r"(\w+)\s*=\s*0\s*\nwhile\s+\1\s*<\s*(\d+)\s*:(.*?)(\n\s*\1\s*\+=\s*1)", re.DOTALL
        )

        def replacer(m):
            var = m.group(1)
            end = m.group(2)
            body = m.group(3)
            return f"for {var} in range({end}):{body}", {"var": var, "end": int(end)}

        return self._annotated_sub(pattern, replacer, code, "convert_while_to_for")

    def _convert_enumerate_to_range(self, code: str) -> tuple[str, list[TransformSpan]]:
        pattern = re.compile(r"^([ \t]*)for\s+(\w+)\s*,\s*(\w+)\s+in\s+enumerate\(([^)]+)\):", re.MULTILINE)

        def replacer(m):
            indent = m.group(1)
            idx_var = m.group(2)
            val_var = m.group(3)
            iterable = m.group(4).strip()
            return (
                f"{indent}for {idx_var} in range(len({iterable})):\n"
                f"{indent}    {val_var} = {iterable}[{idx_var}]"
            ), {"idx_var": idx_var, "val_var": val_var, "iterable": iterable}

        return self._annotated_sub(pattern, replacer, code, "convert_enumerate_to_range")

    def _convert_dict_iteration(self, code: str) -> tuple[str, list[TransformSpan]]:
        pattern = re.compile(r"^([ \t]*)for\s+(\w+)\s*,\s*(\w+)\s+in\s+([^.\n)]+)\.items\(\):", re.MULTILINE)

        def replacer(m):
            indent = m.group(1)
            k_var = m.group(2)
            v_var = m.group(3)
            d = m.group(4).strip()
            return (
                f"{indent}for {k_var} in {d}:\n"
                f"{indent}    {v_var} = {d}[{k_var}]"
            ), {"key_var": k_var, "val_var": v_var, "dict": d}

        return self._annotated_sub(pattern, replacer, code, "convert_dict_iteration")

    def _convert_list_comprehension(self, code: str) -> tuple[str, list[TransformSpan]]:
        pattern = re.compile(r"\[([^\[\]]+?)\s+for\s+(\w+)\s+in\s+([^\[\]]+?)(?:\s+if\s+([^\[\]]+?))?\]")

        def replacer(m):
            expr, var, iterable, cond = m.groups()
            if cond:
                return f"list({var} for {var} in {iterable} if {cond})", {
                    "expr": expr.strip(),
                    "var": var,
                    "cond": cond.strip() if cond else None,
                    "transformation": "listcomp_to_generator",
                }
            else:
                return f"list(map(lambda {var}: {expr}, {iterable}))", {
                    "expr": expr.strip(),
                    "var": var,
                    "transformation": "listcomp_to_map",
                }

        return self._annotated_sub(pattern, replacer, code, "convert_list_comprehension", limit=3)

    def _convert_listcomp_to_loop(self, code: str) -> tuple[str, list[TransformSpan]]:
        pattern = re.compile(r"\[(.*?)\s+for\s+(\w+)\s+in\s+(.*?)\]")

        def replacer(m):
            expr = m.group(1).strip()
            var = m.group(2)
            iterable = m.group(3).strip()
            return (
                f"[{expr} for {var} in {iterable}]"
            ), {}  # Skip — this was a dupe pattern
            # Actually let's skip this one for now

        return code, []

    def _convert_in_to_any(self, code: str) -> tuple[str, list[TransformSpan]]:
        pattern = re.compile(r"(\w+)\s+in\s+(\w+)")

        def replacer(m):
            item = m.group(1)
            container = m.group(2)
            return f"any(x == {item} for x in {container})", {"item": item, "container": container}

        return self._annotated_sub(pattern, replacer, code, "convert_in_to_any", limit=3)

    def _change_comparison_operators(self, code: str) -> tuple[str, list[TransformSpan]]:
        spans: list[TransformSpan] = []
        # == None -> is None
        pattern1 = re.compile(r"(\w+)\s*==\s*None")
        for m in pattern1.finditer(code):
            line_no = code[: m.start()].count("\n")
            spans.append(TransformSpan(
                kind="change_comparison",
                orig_start=line_no,
                orig_end=line_no,
                detail={"old": f"{m.group(1)} == None", "new": f"{m.group(1)} is None"},
            ))
        code1 = pattern1.sub(r"\1 is None", code)

        # != None -> is not None
        pattern2 = re.compile(r"(\w+)\s*!=\s*None")
        for m in pattern2.finditer(code1):
            line_no = code1[: m.start()].count("\n")
            spans.append(TransformSpan(
                kind="change_comparison",
                orig_start=line_no,
                orig_end=line_no,
                detail={"old": f"{m.group(1)} != None", "new": f"{m.group(1)} is not None"},
            ))
        code2 = pattern2.sub(r"\1 is not None", code1)

        return code2, spans

    def _change_augmented_assignment(self, code: str) -> tuple[str, list[TransformSpan]]:
        spans: list[TransformSpan] = []
        for op, aug in [("+", "+="), ("-", "-="), ("*", "*="), ("/", "/=")]:
            if self.rng.random() < 0.5:
                pattern = re.compile(rf"^([ \t]*)(\w+)\s*=\s*\2\s*{re.escape(op)}\s*(\w+)", re.MULTILINE)
                for m in pattern.finditer(code):
                    line_no = code[: m.start()].count("\n")
                    spans.append(TransformSpan(
                        kind="change_augmented_assignment",
                        orig_start=line_no,
                        orig_end=line_no,
                        detail={"old": f"{m.group(2)} = {m.group(2)} {op} {m.group(3)}", "new": f"{m.group(2)} {aug} {m.group(3)}"},
                    ))
                code = pattern.sub(rf"\1\2 {aug} \3", code)
        return code, spans

    def _swap_if_else_negation(self, code: str) -> tuple[str, list[TransformSpan]]:
        # Skip on large files to avoid expensive regex scanning
        if code.count('\n') > 400:
            return code, []
        pattern = re.compile(
            r"^([ \t]*)if\s+([^\n:]+):\s*\n"
            r"((?:\1[ \t]+[^\n]*\n)+?)"
            r"\1else:\s*\n"
            r"((?:\1[ \t]+[^\n]*\n)*)",
            re.MULTILINE,
        )

        def replacer(m):
            indent = m.group(1)
            cond = m.group(2).strip()
            if_body = m.group(3)
            else_body = m.group(4)
            negated = self._negate_condition(cond)
            return (
                f"{indent}if {negated}:\n{else_body}{indent}else:\n{if_body}"
            ), {"condition": cond, "negated": negated}

        return self._annotated_sub(pattern, replacer, code, "swap_if_else_negation", limit=2)

    def _negate_condition(self, cond: str) -> str:
        if cond.startswith("not "):
            return cond[4:]
        if " == " in cond:
            return cond.replace(" == ", " != ")
        if " != " in cond:
            return cond.replace(" != ", " == ")
        if " > " in cond:
            return cond.replace(" > ", " <= ")
        if " >= " in cond:
            return cond.replace(" >= ", " < ")
        if " < " in cond:
            return cond.replace(" < ", " >= ")
        if " <= " in cond:
            return cond.replace(" <= ", " > ")
        if " in " in cond:
            return cond.replace(" in ", " not in ")
        if " not in " in cond:
            return cond.replace(" not in ", " in ")
        if " is " in cond and " not " not in cond:
            return cond.replace(" is ", " is not ")
        if " is not " in cond:
            return cond.replace(" is not ", " is ")
        return f"not ({cond})"

    def _split_compound_conditions(self, code: str) -> tuple[str, list[TransformSpan]]:
        pattern = re.compile(
            r"^([ \t]*)if\s+(\w+)\s+and\s+(\w+):\s*\n"
            r"((?:\1[ \t]+[^\n]*\n?)+)",
            re.MULTILINE,
        )

        def replacer(m):
            indent = m.group(1)
            a, b = m.group(2), m.group(3)
            body = m.group(4)
            inner_indent = indent + "    "
            return (
                f"{indent}if {a}:\n{inner_indent}if {b}:\n{body}"
            ), {"condition_a": a, "condition_b": b}

        return self._annotated_sub(pattern, replacer, code, "split_compound_condition", limit=2)

    def _convert_ternary_to_ifelse(self, code: str) -> tuple[str, list[TransformSpan]]:
        pattern = re.compile(r"(\w+)\s+if\s+(.+?)\s+else\s+(\w+)")

        def replacer(m):
            true_val = m.group(1)
            cond = m.group(2).strip()
            false_val = m.group(3)
            return (
                f"{true_val} if {cond} else {false_val}"
            ), {
                "true_val": true_val,
                "condition": cond,
                "false_val": false_val,
                "transformation": "ternary_to_ifelse",
            }
            # For real conversion we'd need context, but let's annotate it

        # This is hard to convert properly without context; let's skip
        # and instead just note that a ternary pattern was detected
        return code, []

    def _convert_sorted_to_sort(self, code: str) -> tuple[str, list[TransformSpan]]:
        pattern = re.compile(r"(\w+)\s*=\s*sorted\(([^)]+)\)")

        def replacer(m):
            target = m.group(1)
            arg = m.group(2).strip()
            return (
                f"{target} = {arg}[:]\n{target}.sort()"
            ), {"target": target, "arg": arg}

        return self._annotated_sub(pattern, replacer, code, "convert_sorted_to_sort", limit=2)

    def _apply_de_morgan(self, code: str) -> tuple[str, list[TransformSpan]]:
        patterns = [
            (re.compile(r"not\s*\(\s*(\w+)\s+and\s+(\w+)\s*\)"), r"not \1 or not \2"),
            (re.compile(r"not\s*\(\s*(\w+)\s+or\s+(\w+)\s*\)"), r"not \1 and not \2"),
        ]

        spans: list[TransformSpan] = []
        for pat, replacement in patterns:
            for m in pat.finditer(code):
                line_no = code[: m.start()].count("\n")
                spans.append(TransformSpan(
                    kind="apply_de_morgan",
                    orig_start=line_no,
                    orig_end=line_no,
                    detail={"original": m.group(0), "transformed": m.expand(replacement)},
                ))
            code = pat.sub(replacement, code)
        return code, spans

    def _convert_format_string(self, code: str) -> tuple[str, list[TransformSpan]]:
        spans: list[TransformSpan] = []
        # f-strings -> str.format()
        fstring = re.compile(r'f(["\'])(.*?)\1')

        def f_to_format(m):
            delimiter = m.group(1)
            content = m.group(2)
            placeholders = re.findall(r"\{(.*?)\}", content)
            fmt_str = re.sub(r"\{.*?\}", "{}", content)
            if placeholders:
                result = f'"{fmt_str}".format({", ".join(placeholders)})'
            else:
                result = f'"{content}"'
            line_no = code[: m.start()].count("\n")
            spans.append(TransformSpan(
                kind="convert_format_string",
                orig_start=line_no,
                orig_end=line_no,
                detail={"old": m.group(0), "new": result},
            ))
            return result

        result = fstring.sub(f_to_format, code)
        return result, spans

    def _convert_eafp_to_lbyl(self, code: str) -> tuple[str, list[TransformSpan]]:
        # try: x = d[key]; except KeyError: x = default -> x = d.get(key, default)
        pattern = re.compile(
            r"try:\s*\n"
            r"\s+(\w+)\s*=\s*(\w+)\[(\w+)\]\s*\n"
            r"except\s+(KeyError|IndexError):\s*\n"
            r"\s+(\w+)\s*=\s*(.+)",
        )

        def replacer(m):
            var = m.group(1)
            container = m.group(2)
            key = m.group(3)
            default_val = m.group(6).strip()
            if container == var:
                return (
                    f"{var} = {container}.get({key}, {default_val})"
                ), {"var": var, "container": container, "key": key, "default": default_val}
            return m.group(0), None

        return self._annotated_sub(pattern, replacer, code, "convert_eafp_to_lbyl", limit=2)

    def _convert_call_unbound(self, code: str) -> tuple[str, list[TransformSpan]]:
        pattern = re.compile(r"(\w+)\.(\w+)\(([^)]*)\)")

        def replacer(m):
            obj = m.group(1)
            method = m.group(2)
            args = m.group(3) if m.group(3) else ""
            # Don't touch common non-method calls
            if method in ("get", "keys", "values", "items", "append", "join", "split", "strip"):
                return m.group(0), None
            return (
                f"{obj}.{method}({args})"
            ), {
                "object": obj,
                "method": method,
                "args": args,
                "transformation": "call_unbound",
            }
            # Actually let's not transform, just annotate the pattern
            return m.group(0), None

        # For now, only annotate, don't transform
        return code, []


def generate_annotated_dataset(
    source_dir: str,
    output_jsonl: str,
    file_range: tuple[int, int] | None = None,
    max_files: int | None = None,
):
    import json

    source_path = Path(source_dir)
    files = sorted(source_path.glob("*.py"))

    if file_range:
        files = files[file_range[0] : file_range[1]]
    if max_files:
        files = files[:max_files]

    total = 0
    with open(output_jsonl, "w", encoding="utf-8") as f:
        for fpath in files:
            try:
                source = fpath.read_text(encoding="utf-8")
            except Exception:
                continue

            # Create a fresh generator for each source file to avoid state accumulation
            generator = AnnotatedCloneGenerator()

            for type_num in (1, 2, 3, 4):
                try:
                    if type_num == 1:
                        clones = generator.generate_type1(source, 1)
                    elif type_num == 2:
                        clones = generator.generate_type2(source, 1)
                    elif type_num == 3:
                        clones = generator.generate_type3(source, 1)
                    elif type_num == 4:
                        clones = generator.generate_type4(source, 1)
                except Exception:
                    continue

                for clone_code, spans in clones:
                    entry = {
                        "original_path": str(fpath),
                        "original": source,
                        "clone": clone_code,
                        "type": type_num,
                        "transformations": [s.to_dict() for s in spans],
                    }
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                    total += 1

            if total % 200 == 0:
                print(f"  Generated {total} entries...")

    print(f"Wrote {total} entries to {output_jsonl}")
    return total


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", default="dataset")
    parser.add_argument("--output", default="benchmarks/annotated_ground_truth.jsonl")
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--end", type=int)
    parser.add_argument("--max", type=int)
    args = parser.parse_args()

    file_range = (args.start, args.end) if args.end else None
    generate_annotated_dataset(
        source_dir=args.source,
        output_jsonl=args.output,
        file_range=file_range,
        max_files=args.max,
    )
