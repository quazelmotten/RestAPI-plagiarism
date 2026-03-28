import argparse
import random
import re
from pathlib import Path

import tree_sitter_python as tspython
from tree_sitter import Language, Parser

PY_LANGUAGE = Language(tspython.language())


class CloneGenerator:
    def __init__(self):
        self.parser = Parser()
        self.parser.language = PY_LANGUAGE
        self.rng = random.Random(42)

    def parse(self, code: str):
        return self.parser.parse(code.encode("utf-8"))

    def generate_type1(self, source_code: str, clone_num: int = 1) -> list[str]:
        clones = []
        for _ in range(clone_num):
            result = source_code

            # Only lexical-safe transformations
            result = self._normalize_whitespace(result)
            result = self._random_blank_lines(result)
            result = self._inject_comments(result)

            clones.append(result)

        return clones

    def _normalize_whitespace(self, code: str) -> str:
        lines = code.splitlines()
        cleaned = [line.rstrip() for line in lines]
        return "\n".join(cleaned) + "\n"

    def _random_blank_lines(self, code: str) -> str:
        lines = code.splitlines()
        result = []

        for line in lines:
            result.append(line)

            # Add blank line occasionally
            if line.strip() and random.random() < 0.15:
                result.append("")

        return "\n".join(result)

    def _inject_comments(self, code: str) -> str:
        lines = code.splitlines()
        result = []

        for line in lines:
            result.append(line)

            stripped = line.strip()

            # Only add comments after complete statements
            if stripped and not stripped.endswith(":"):
                if random.random() < 0.1:
                    indent = len(line) - len(line.lstrip())
                    comment = "# " + "".join(self.rng.choices("abcdefghijklmnopqrstuvwxyz", k=6))
                    result.append(" " * indent + comment)

        return "\n".join(result)

    def _node_hash(self, node):
        import hashlib

        m = hashlib.sha256()
        m.update(node.type.encode())

        for child in node.children:
            m.update(self._node_hash(child))

        return m.digest()

    def _ast_equal(self, code1: str, code2: str) -> bool:
        tree1 = self.parse(code1)
        tree2 = self.parse(code2)

        return self._node_hash(tree1.root_node) == self._node_hash(tree2.root_node)

    def _add_random_comments(self, code: str) -> str:
        lines = code.split("\n")
        result = []
        for line in lines:
            if line.strip() and self.rng.random() < 0.1:
                indent = len(line) - len(line.lstrip())
                comment = "# " + "".join(random.choices("abcdefghijklmnopqrstuvwxyz", k=5))
                result.append(" " * indent + comment)
            result.append(line)
        return "\n".join(result)

    def _reorder_imports(self, code: str) -> str:
        lines = code.split("\n")
        import_lines = []
        other_lines = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                import_lines.append(line)
            else:
                other_lines.append(line)

        self.rng.shuffle(import_lines)

        final_lines = import_lines + other_lines

        last_import_idx = 0
        for i, line in enumerate(final_lines):
            stripped = line.strip()
            if stripped.startswith("import ") or stripped.startswith("from "):
                last_import_idx = i

        for i in range(last_import_idx + 1):
            if not final_lines[i].strip():
                last_import_idx = i
                break

        return "\n".join(
            final_lines[: last_import_idx + 1] + [""] + final_lines[last_import_idx + 1 :]
        )

    def _change_indentation(self, code: str) -> str:
        lines = code.split("\n")
        indent_char = "    "
        if self.rng.random() < 0.5:
            indent_char = "\t"

        result = []
        for line in lines:
            if line.strip():
                current_indent = len(line) - len(line.lstrip())
                new_indent = current_indent + random.choice([-1, 0, 1, 2]) * len(indent_char)
                new_indent = max(0, new_indent)
                result.append(
                    indent_char * (new_indent // max(1, len(indent_char))) + line.lstrip()
                )
            else:
                result.append(line)
        return "\n".join(result)

    def _add_empty_lines(self, code: str) -> str:
        lines = code.split("\n")
        result = []
        for line in lines:
            result.append(line)
            if line.strip() and self.rng.random() < 0.15:
                result.append("")
        return "\n".join(result)

    def generate_type2(self, source_code: str, clone_num: int = 1) -> list[str]:
        clones = []
        tree = self.parse(source_code)

        identifiers = self._extract_identifiers(tree.root_node, source_code)
        if not identifiers:
            return [source_code] * clone_num

        for _ in range(clone_num):
            rename_map = self._create_rename_map(identifiers)
            clone = self._apply_rename(source_code, rename_map)
            clones.append(clone)

        return clones

    def _extract_identifiers(self, node, source_code: str) -> list[tuple[str, tuple[int, int]]]:
        identifiers = []

        def visit(n):
            if n.type == "identifier":
                text = source_code[n.start_byte : n.end_byte]
                if not text.startswith("__") and not text.endswith("__"):
                    identifiers.append((text, (n.start_byte, n.end_byte)))
            for child in n.children:
                visit(child)

        visit(node)
        return identifiers

    def _create_rename_map(self, identifiers: list[tuple[str, tuple[int, int]]]) -> dict[str, str]:
        unique_ids = list({id[0] for id in identifiers})
        self.rng.shuffle(unique_ids)

        new_names = []
        for name in unique_ids:
            if len(name) <= 2:
                new_name = "".join(self.rng.choices("abcdefghijklmnopqrstuvwxyz", k=3))
            else:
                prefix = self.rng.choice(
                    ["get_", "set_", "calc_", "data_", "val_", "temp_", "new_"]
                )
                suffix = "".join(
                    self.rng.choices("abcdefghijklmnopqrstuvwxyz", k=max(0, len(name) - 2))
                )
                new_name = prefix + suffix if self.rng.random() < 0.5 else name[:1] + suffix
            new_names.append(new_name)

        return dict(zip(unique_ids, new_names, strict=False))

    def _apply_rename(self, code: str, rename_map: dict[str, str]) -> str:
        result = code
        for old_name, new_name in rename_map.items():
            # Use a lambda to safely insert the literal string
            result = re.sub(r"\b" + re.escape(old_name) + r"\b", lambda m, s=new_name: s, result)
        return result

    def generate_type3(self, source_code: str, clone_num: int = 1) -> list[str]:
        clones = []

        for _ in range(clone_num):
            result = source_code

            transformations = [
                self._remove_dead_code,
                self._add_stub_functions,
                self._reorder_functions,
                self._inline_variables,
                self._add_prints,
            ]

            for trans in transformations:
                if self.rng.random() < 0.4:
                    result = trans(result)

            clones.append(result)

        return clones

    def _remove_dead_code(self, code: str) -> str:
        lines = code.split("\n")
        result = []
        skip_until = -1

        for i, line in enumerate(lines):
            if i < skip_until:
                continue

            stripped = line.strip()

            if stripped.startswith("if __name__") and i + 1 < len(lines):
                continue

            if stripped.startswith("return ") and self.rng.random() < 0.3:
                continue

            result.append(line)

        return "\n".join(result)

    def _add_stub_functions(self, code: str) -> str:
        stub = """
def _unused_stub():
    pass

"""
        lines = code.split("\n")

        if lines and lines[0].strip().startswith("#"):
            return stub + code

        return stub + code

    def _reorder_functions(self, code: str) -> str:
        tree = self.parse(code)

        functions = []
        current_func = []
        current_name = None

        lines = code.split("\n")

        func_pattern = re.compile(r"^def (\w+)\s*\(")

        func_lines = {}
        func_order = []
        current_func_name = None
        current_lines = []

        for line in lines:
            match = func_pattern.match(line)
            if match:
                if current_func_name:
                    func_lines[current_func_name] = "\n".join(current_lines)
                current_func_name = match.group(1)
                func_order.append(current_func_name)
                current_lines = [line]
            elif current_func_name:
                current_lines.append(line)

        if current_func_name:
            func_lines[current_func_name] = "\n".join(current_lines)

        if len(func_order) > 1:
            self.rng.shuffle(func_order)
            new_code = "\n\n".join(func_lines[name] for name in func_order if name in func_lines)
            return new_code

        return code

    def _inline_variables(self, code: str) -> str:
        lines = code.split("\n")
        result = []

        for line in lines:
            if "=" in line and "==" not in line and "!=" not in line:
                if self.rng.random() < 0.2:
                    continue
            result.append(line)

        return "\n".join(result)

    def _add_prints(self, code: str) -> str:
        lines = code.split("\n")
        result = []

        for line in lines:
            result.append(line)
            if line.strip() and not line.strip().startswith("#"):
                if self.rng.random() < 0.05:
                    indent = len(line) - len(line.lstrip())
                    result.append(" " * indent + 'print("debug")')

        return "\n".join(result)

    def generate_type4(self, source_code: str, clone_num: int = 1) -> list[str]:
        """
        Generate Type 4 clones: modified logic.
        Uses a pool of semantic-preserving transformations applied stochastically.
        """
        clones = []
        for _ in range(clone_num):
            code = source_code

            # All available transformations (pick a random subset each time)
            transformations = [
                (self._convert_for_to_while, 0.7),
                (self._convert_while_to_for, 0.4),
                (self._convert_list_comprehension, 0.6),
                (self._convert_listcomp_to_loop, 0.5),
                (self._use_map_filter, 0.4),
                (self._change_string_formatting, 0.6),
                (self._shuffle_commutative_ops, 0.5),
                (self._swap_if_else_negation, 0.4),
                (self._change_comparison_operators, 0.5),
                (self._convert_dict_comprehension, 0.5),
                (self._convert_lambda_to_def, 0.4),
                (self._split_compound_conditions, 0.4),
                (self._merge_conditions, 0.3),
                (self._change_augmented_assignment, 0.4),
            ]

            # Randomly select and apply a subset (3-6 transformations)
            selected = random.sample(
                transformations, min(len(transformations), random.randint(3, 6))
            )
            for transform, _ in selected:
                try:
                    code = transform(code)
                except Exception:
                    pass

            clones.append(code)
        return clones

    def _convert_for_to_while(self, code: str) -> str:
        """
        Convert simple for-loops into equivalent while-loops using iter().
        """
        pattern = re.compile(r"^([ \t]*)for\s+(\w+)\s+in\s+([^\n:]+):", re.MULTILINE)

        def replacer(match):
            indent, var, iterable = match.groups()
            indent_next = indent + "    "
            return (
                f"{indent}{var}_it = iter({iterable})\n"
                f"{indent}while True:\n"
                f"{indent_next}try:\n"
                f"{indent_next}    {var} = next({var}_it)\n"
                f"{indent_next}except StopIteration:\n"
                f"{indent_next}    break"
            )

        return pattern.sub(replacer, code)

    def _convert_list_comprehension(self, code: str) -> str:
        """
        Converts list comprehensions with optional if condition into list(map(...)) or list(filter(...)).
        """
        pattern = re.compile(
            r"\[([^\[\]]+?)\s+for\s+(\w+)\s+in\s+([^\[\]]+?)(?:\s+if\s+([^\[\]]+?))?\]"
        )

        def replacer(match):
            expr, var, iterable, cond = match.groups()
            if cond:
                return f"list({var} for {var} in {iterable} if {cond})"
            else:
                return f"list(map(lambda {var}: {expr}, {iterable}))"

        return pattern.sub(replacer, code)

    def _use_map_filter(self, code: str) -> str:
        """
        Converts simple for-loops that build lists into map() usage.
        Only handles very simple single-expression loops.
        """
        pattern = re.compile(r"\[\s*(\w+)\s+for\s+(\w+)\s+in\s+(\w+)\s*\]")

        def replacer(match):
            expr, var, iterable = match.groups()
            return f"list(map(lambda {var}: {expr}, {iterable}))"

        return pattern.sub(replacer, code)

    def _change_string_formatting(self, code: str) -> str:
        """
        Converts f-strings to str.format(), preserving content.
        """
        fstring = re.compile(r'f(["\'])(.*?)\1')

        def f_to_format(match):
            content = match.group(2)
            # Replace {var} inside content with {} for str.format()
            placeholders = re.findall(r"{(.*?)}", content)
            fmt_str = re.sub(r"{.*?}", "{}", content)
            if placeholders:
                return '"{}".format({})'.format(fmt_str, ", ".join(placeholders))
            else:
                return f'"{content}"'

        return fstring.sub(f_to_format, code)

    def _convert_while_to_for(self, code: str) -> str:
        # Matches simple while loops like:
        # i = 0
        # while i < N:
        #     ...
        #     i += 1
        pattern = re.compile(
            r"(\w+)\s*=\s*0\s*\nwhile\s+\1\s*<\s*(\d+)\s*:(.*?)(\n\s*\1\s*\+=\s*1)", re.DOTALL
        )

        def replacer(match):
            var = match.group(1)
            end = match.group(2)
            body = match.group(3)
            return f"for {var} in range({end}):{body}"

        return pattern.sub(replacer, code)

    def _convert_listcomp_to_loop(self, code: str) -> str:
        pattern = re.compile(r"\[(.*?)\s+for\s+(\w+)\s+in\s+(.*?)\]")

        def replacer(match):
            expr = match.group(1).strip()
            var = match.group(2)
            iterable = match.group(3).strip()
            loop_code = (
                f"{var}_list = []\nfor {var} in {iterable}:\n    {var}_list.append({expr})\n"
            )
            return f"{var}_list"

        return pattern.sub(replacer, code)

    def _shuffle_commutative_ops(self, code: str) -> str:
        pattern = re.compile(r"(\b\w+\b)\s*([\+\*])\s*(\b\w+\b)")

        def replacer(match):
            a, op, b = match.groups()
            if self.rng.random() < 0.5:
                return f"{b} {op} {a}"
            return match.group(0)

        return pattern.sub(replacer, code)

    def _swap_if_else_negation(self, code: str) -> str:
        """
        Swap if/else branches by negating the condition.
        e.g., `if x > 0: a()` → `if x <= 0: pass else: a()` (inverted)
        """
        # Simple pattern: if COND:\n    BODY\nelse:\n    ELSE_BODY
        pattern = re.compile(
            r"^([ \t]*)if\s+([^\n:]+):\s*\n"
            r"((?:\1[ \t]+[^\n]*\n)+)"
            r"\1else:\s*\n"
            r"((?:\1[ \t]+[^\n]*\n?)+)",
            re.MULTILINE,
        )

        def replacer(match):
            indent = match.group(1)
            cond = match.group(2).strip()
            if_body = match.group(3)
            else_body = match.group(4)

            # Negate the condition
            negated = self._negate_condition(cond)
            return f"{indent}if {negated}:\n{else_body}{indent}else:\n{if_body}"

        return pattern.sub(replacer, code)

    def _negate_condition(self, cond: str) -> str:
        """Negate a simple boolean condition."""
        # Handle common patterns
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
        return f"not ({cond})"

    def _change_comparison_operators(self, code: str) -> str:
        """
        Change comparison operators: == None → is None, != None → is not None.
        """
        code = re.sub(r"(\w+)\s*==\s*None", r"\1 is None", code)
        code = re.sub(r"(\w+)\s*!=\s*None", r"\1 is not None", code)
        code = re.sub(r"None\s*==\s*(\w+)", r"None is \1", code)
        code = re.sub(r"None\s*!=\s*(\w+)", r"None is not \1", code)
        return code

    def _convert_dict_comprehension(self, code: str) -> str:
        """
        Convert dict comprehensions to explicit loop.
        {k: v for k, v in iterable} → result = {}; for k, v in iterable: result[k] = v
        """
        pattern = re.compile(r"\{(\w+)\s*:\s*(\w+)\s+for\s+(\w+)\s*,\s*(\w+)\s+in\s+([^\{\}]+?)\}")

        def replacer(match):
            k, v, k_var, v_var, iterable = match.groups()
            tmp = f"_dict_{k_var}"
            return (
                f"(lambda: (lambda _d: "
                f"[_d.__setitem__({k_var}, {v_var}) "
                f"for {k_var}, {v_var} in {iterable}] and _d)({{}}))()"
            )

        return pattern.sub(replacer, code)

    def _convert_lambda_to_def(self, code: str) -> str:
        """
        Convert lambda expressions to named functions.
        lambda x: x + 1 → def _fn(x): return x + 1
        """
        lambda_pattern = re.compile(r"lambda\s+([\w\s,]+):\s*([^\n,\)]+)")
        counter = [0]

        def replacer(match):
            args = match.group(1).strip()
            body = match.group(2).strip()
            fn_name = f"_lambda_fn_{counter[0]}"
            counter[0] += 1
            # Return the function name (definition is prepended)
            return fn_name

        # This is complex to do safely with regex; use a simpler approach
        # Only transform lambdas in assignment context
        assign_pattern = re.compile(
            r"^([ \t]*)(\w+)\s*=\s*lambda\s+([\w\s,]+):\s*([^\n]+)", re.MULTILINE
        )

        def assign_replacer(match):
            indent = match.group(1)
            var_name = match.group(2)
            args = match.group(3).strip()
            body = match.group(4).strip()
            return f"{indent}def {var_name}({args}):\n{indent}    return {body}"

        return assign_pattern.sub(assign_replacer, code)

    def _split_compound_conditions(self, code: str) -> str:
        """
        Split compound conditions into nested ifs.
        if a and b: BODY → if a:\n    if b: BODY
        """
        pattern = re.compile(
            r"^([ \t]*)if\s+(\w+)\s+and\s+(\w+):\s*\n"
            r"((?:\1[ \t]+[^\n]*\n?)+)",
            re.MULTILINE,
        )

        def replacer(match):
            indent = match.group(1)
            a, b = match.group(2), match.group(3)
            body = match.group(4)
            inner_indent = indent + "    "
            indented_body = body.replace("\n" + inner_indent, "\n" + inner_indent + "    ")
            # Only apply 50% of the time
            if self.rng.random() < 0.5:
                return match.group(0)
            return f"{indent}if {a}:\n{inner_indent}if {b}:\n{inner_indent}    {body.lstrip()}"

        return pattern.sub(replacer, code)

    def _merge_conditions(self, code: str) -> str:
        """
        Merge nested if statements into compound conditions.
        if a:\n    if b: BODY → if a and b: BODY
        """
        pattern = re.compile(
            r"^([ \t]*)if\s+(\w+):\s*\n"
            r"\1[ \t]+if\s+(\w+):\s*\n"
            r"((?:\1[ \t]+[^\n]*\n?)+)",
            re.MULTILINE,
        )

        def replacer(match):
            indent = match.group(1)
            a, b = match.group(2), match.group(3)
            body = match.group(4)
            if self.rng.random() < 0.5:
                return match.group(0)
            return f"{indent}if {a} and {b}:\n{body}"

        return pattern.sub(replacer, code)

    def _change_augmented_assignment(self, code: str) -> str:
        """
        Change augmented assignment forms.
        x += 1 ↔ x = x + 1
        """
        ops = [("+", "+="), ("-", "-="), ("*", "*="), ("/", "/=")]
        for op, aug in ops:
            # x = x + y → x += y
            pattern = re.compile(
                rf"^([ \t]*)(\w+)\s*=\s*\2\s*{re.escape(op)}\s*(\w+)", re.MULTILINE
            )
            if self.rng.random() < 0.5:
                code = pattern.sub(rf"\1\2 {aug} \3", code)
        return code

    def generate_type5(self, source_code: str, clone_num: int = 1) -> list[str]:
        """
        Generate Type 5 clones: mixed transformations (T1+T2+T3+T4 combined).
        Applies a combination of all transformation types for maximum variety.
        """
        clones = []
        for _ in range(clone_num):
            code = source_code

            # T1: Lexical changes (always applied, mild)
            code = self._normalize_whitespace(code)
            if self.rng.random() < 0.6:
                code = self._inject_comments(code)
            if self.rng.random() < 0.5:
                code = self._random_blank_lines(code)

            # T2: Identifier renaming (70% chance)
            if self.rng.random() < 0.7:
                tree = self.parse(code)
                identifiers = self._extract_identifiers(tree.root_node, code)
                if identifiers:
                    rename_map = self._create_rename_map(identifiers)
                    code = self._apply_rename(code, rename_map)

            # T3: Structural changes (60% chance each)
            if self.rng.random() < 0.6:
                code = self._remove_dead_code(code)
            if self.rng.random() < 0.5:
                code = self._reorder_functions(code)
            if self.rng.random() < 0.4:
                code = self._inline_variables(code)
            if self.rng.random() < 0.3:
                code = self._add_stub_functions(code)

            # T4: Logic changes (pick 2-4 random transformations)
            t4_transforms = [
                self._convert_for_to_while,
                self._convert_while_to_for,
                self._convert_list_comprehension,
                self._convert_listcomp_to_loop,
                self._use_map_filter,
                self._change_string_formatting,
                self._shuffle_commutative_ops,
                self._swap_if_else_negation,
                self._change_comparison_operators,
                self._convert_lambda_to_def,
                self._change_augmented_assignment,
            ]
            selected = random.sample(t4_transforms, min(len(t4_transforms), random.randint(2, 4)))
            for transform in selected:
                try:
                    code = transform(code)
                except Exception:
                    pass

            clones.append(code)
        return clones


def generate_dataset(
    source_dir: str,
    output_dir: str,
    n: int = 1,
    file_range: tuple[int, int] = (0, 1000),
    types: list[int] = None,
):
    if types is None:
        types = [1, 2, 3, 4]
    generator = CloneGenerator()

    source_path = Path(source_dir)
    output_path = Path(output_dir)

    for type_num in types:
        type_dir = output_path / f"type{type_num}"
        type_dir.mkdir(parents=True, exist_ok=True)

    start, end = file_range
    files_generated = 0

    files = sorted(source_path.glob("*.py"))
    files = files[start:end]

    for file_path in files:
        with open(file_path, encoding="utf-8") as f:
            source_code = f.read()

        file_stem = file_path.stem  # Use the actual filename without extension

        for type_num in types:
            type_dir = output_path / f"type{type_num}"

            if type_num == 1:
                clones = generator.generate_type1(source_code, n)
            elif type_num == 2:
                clones = generator.generate_type2(source_code, n)
            elif type_num == 3:
                clones = generator.generate_type3(source_code, n)
            elif type_num == 4:
                clones = generator.generate_type4(source_code, n)
            elif type_num == 5:
                clones = generator.generate_type5(source_code, n)
            else:
                continue

            for j, clone in enumerate(clones):
                clone_name = f"{file_stem}_type{type_num}_{j + 1}.py"
                clone_path = type_dir / clone_name

                with open(clone_path, "w", encoding="utf-8") as f:
                    f.write(clone)

        files_generated += 1

        if files_generated % 50 == 0:
            print(f"Processed {files_generated} files...")

    print(f"Generated clones for {files_generated} files")
    print(f"Output directory: {output_dir}")
    for type_num in types:
        type_dir = output_path / f"type{type_num}"
        count = len(list(type_dir.glob("*.py")))
        print(f"  Type {type_num}: {count} clones")


def main():
    parser = argparse.ArgumentParser(
        description="Generate synthetic code clones for plagiarism testing"
    )
    parser.add_argument("--source", default=None, help="Source directory with original files")
    parser.add_argument("--output", default=None, help="Output directory for clones")
    parser.add_argument("--n", type=int, default=1, help="Number of clones per type per file")
    parser.add_argument("--start", type=int, default=0, help="Starting file index")
    parser.add_argument("--end", type=int, default=100, help="Ending file index")
    parser.add_argument(
        "--types",
        type=int,
        nargs="+",
        default=[1, 2, 3, 4, 5],
        help="Clone types to generate (1-5)",
    )

    args = parser.parse_args()

    script_dir = Path(__file__).parent
    project_root = script_dir.parent.parent

    source_dir = args.source if args.source else str(project_root / "dataset")
    output_dir = args.output if args.output else str(project_root / "tests" / "plagiarism")

    generate_dataset(
        source_dir=source_dir,
        output_dir=output_dir,
        n=args.n,
        file_range=(args.start, args.end),
        types=args.types,
    )


if __name__ == "__main__":
    main()
