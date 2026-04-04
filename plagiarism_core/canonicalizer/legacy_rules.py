"""Legacy regex-based canonicalization rules for Type 4 detection."""

import logging
import re

from .ast_canonical import ast_canonicalize

logger = logging.getLogger(__name__)


def _convert_for_to_while(code: str) -> str:
    pattern = re.compile(r"^([ \t]*)for\s+(\w+)\s+in\s+([^\n:]+):", re.MULTILINE)

    def replacer(match):
        indent, var, iterable = match.groups()
        ni = indent + "    "
        return (
            f"{indent}{var}_it = iter({iterable})\n"
            f"{indent}while True:\n"
            f"{ni}try:\n"
            f"{ni}    {var} = next({var}_it)\n"
            f"{ni}except StopIteration:\n"
            f"{ni}    break"
        )

    return pattern.sub(replacer, code)


def _convert_while_to_for(code: str) -> str:
    pattern = re.compile(
        r"(\w+)\s*=\s*0\s*\nwhile\s+\1\s*<\s*(\d+)\s*:(.*?)(\n\s*\1\s*\+=\s*1)",
        re.DOTALL,
    )

    def replacer(match):
        var, end, body = match.group(1), match.group(2), match.group(3)
        return f"for {var} in range({end}):{body}"

    return pattern.sub(replacer, code)


def _normalize_list_comprehension(code: str) -> str:
    pattern = re.compile(
        r"\[([^\[\]]+?)\s+for\s+(\w+)\s+in\s+([^\[\]]+?)(?:\s+if\s+([^\[\]]+?))?\]"
    )

    def replacer(match):
        expr, var, iterable, cond = match.groups()
        if cond:
            return f"list({var} for {var} in {iterable} if {cond})"
        return f"list(map(lambda {var}: {expr}, {iterable}))"

    return pattern.sub(replacer, code)


def _normalize_string_formatting(code: str) -> str:
    fstring = re.compile(r'f(["\'])(.*?)\1')

    def f_to_format(match):
        content = match.group(2)
        placeholders = re.findall(r"{(.*?)}", content)
        fmt_str = re.sub(r"{.*?}", "{}", content)
        if placeholders:
            return '"{}".format({})'.format(fmt_str, ", ".join(placeholders))
        return f'"{content}"'

    return fstring.sub(f_to_format, code)


def _normalize_augmented_assignment(code: str) -> str:
    ops = [
        ("+", "+="),
        ("-", "-="),
        ("*", "*="),
        ("/", "/="),
        ("//", "//="),
        ("**", "**="),
        ("%", "%="),
        ("<<", "<<="),
        (">>", ">>="),
        ("&", "&="),
        ("|", "|="),
        ("^", "^="),
    ]
    for op, aug in ops:
        pattern = re.compile(
            rf"^([ \t]*)(\w+)\s*=\s*\2\s*{re.escape(op)}\s*(\w+)",
            re.MULTILINE,
        )
        code = pattern.sub(rf"\1\2 {aug} \3", code)
    return code


def _normalize_lambda_to_def(code: str) -> str:
    pattern = re.compile(
        r"^([ \t]*)(\w+)\s*=\s*lambda\s+([\w\s,]+):\s*([^\n]+)",
        re.MULTILINE,
    )

    def replacer(match):
        indent, name, args, body = match.groups()
        return f"{indent}def {name}({args.strip()}):\n{indent}    return {body.strip()}"

    return pattern.sub(replacer, code)


def _normalize_if_else_swap(code: str) -> str:
    pattern = re.compile(
        r"^([ \t]*)if\s+([^\n:]+):\s*\n"
        r"((?:\1[ \t]+[^\n]*\n)+)"
        r"\1else:\s*\n"
        r"((?:\1[ \t]+[^\n]*\n?)+)",
        re.MULTILINE,
    )

    def replacer(match):
        indent = match.group(1)
        if_body = match.group(3)
        else_body = match.group(4)
        if len(if_body) <= len(else_body):
            return match.group(0)
        return f"{indent}if not ({match.group(2).strip()}):\n{else_body}{indent}else:\n{if_body}"

    return pattern.sub(replacer, code)


def _normalize_comparison_operators(code: str) -> str:
    code = re.sub(r"(\w+)\s*==\s*None", r"\1 is None", code)
    code = re.sub(r"(\w+)\s*!=\s*None", r"\1 is not None", code)
    code = re.sub(r"None\s*==\s*(\w+)", r"None is \1", code)
    code = re.sub(r"None\s*!=\s*(\w+)", r"None is not \1", code)
    return code


def _normalize_compound_conditions(code: str) -> str:
    pattern = re.compile(
        r"^([ \t]*)if\s+(\w+)\s+and\s+(\w+):\s*\n"
        r"((?:\1[ \t]+[^\n]*\n?)+)",
        re.MULTILINE,
    )

    def replacer(match):
        indent, a, b, body = match.groups()
        inner = indent + "    "
        return f"{indent}if {a}:\n{inner}if {b}:\n{inner}    {body.lstrip()}"

    return pattern.sub(replacer, code)


def _normalize_dict_comprehension(code: str) -> str:
    pattern = re.compile(r"\{(\w+)\s*:\s*(\w+)\s+for\s+(\w+)\s*,\s*(\w+)\s+in\s+([^\{\}]+?)\}")

    def replacer(match):
        k_var, v_var, iterable = match.group(3), match.group(4), match.group(5)
        return (
            f"(lambda: (lambda _d: "
            f"[_d.__setitem__({k_var}, {v_var}) "
            f"for {k_var}, {v_var} in {iterable}] and _d)({{}}))()"
        )

    return pattern.sub(replacer, code)


_TYPE4_RULES = [
    _convert_for_to_while,
    _convert_while_to_for,
    _normalize_list_comprehension,
    _normalize_string_formatting,
    _normalize_augmented_assignment,
    _normalize_lambda_to_def,
    _normalize_comparison_operators,
    _normalize_compound_conditions,
    _normalize_dict_comprehension,
    _normalize_if_else_swap,
]


def _canonicalize_type4_light(code: str, lang_code: str) -> str:
    line = code.strip().lower()
    if not line:
        return ""
    if line.startswith("#") or line in ("{", "}", ";", ""):
        return ""
    line = re.sub(r"\s*(\+=|-=|\*=|/=|%=|<<=|>>=|&=|\|=|\^=)\s*", " = ", line)
    line = re.sub(r"\s*(==|!=|<=|>=)\s*", " COMP ", line)
    line = re.sub(r"\s(<|>)\s", " COMP ", line)
    line = re.sub(r"\s+(and|or|&&|\|\|)\s+", " BOOL ", line)
    line = re.sub(r"\s+(!)\s*", " NOT ", line)
    line = re.sub(r"^\s*for\s*\(", "LOOP(", line)
    line = re.sub(r"^\s*for\s+", "LOOP ", line)
    line = re.sub(r"^\s*while\s*\(", "LOOP(", line)
    line = re.sub(r"^\s*while\s+", "LOOP ", line)
    line = re.sub(r"^\s*do\s*\{", "DO{", line)
    line = re.sub(r"^\s*do\s+", "DO ", line)
    line = re.sub(r"^\s*if\s*\(", "COND(", line)
    line = re.sub(r"^\s*if\s+", "COND ", line)
    line = re.sub(r"^\s*else\s+if\s*\(", "COND(", line)
    line = re.sub(r"^\s*else\s+if\s+", "COND ", line)
    line = re.sub(r"^\s*switch\s*\(", "SWITCH(", line)
    line = re.sub(r"^\s*switch\s+", "SWITCH ", line)
    line = re.sub(r"^\s*case\s+", "CASE ", line)
    line = re.sub(r"^\s*return\s+", "RETURN ", line)
    line = re.sub(r"^\s*break\s*;", "BREAK", line)
    line = re.sub(r"^\s*continue\s*;", "CONTINUE", line)
    line = re.sub(r"\b\d+\.\d+\b", "FLOAT", line)
    line = re.sub(r"\b\d+\b", "NUM", line)
    line = re.sub(r'"[^"]*"', "STR", line)
    line = re.sub(r"'[^']*'", "STR", line)
    line = re.sub(r"<<", " OUT ", line)
    line = re.sub(r">>", " IN ", line)
    line = re.sub(r":=", " = ", line)
    line = re.sub(r"\blet\s+mut\b", "LET_MUT", line)
    line = re.sub(r"\blet\b", "LET", line)
    line = re.sub(r"\s+", " ", line).strip()
    return line


def canonicalize_type4(code: str, use_ast: bool = True, lang_code: str = "python") -> str:
    if use_ast and lang_code == "python":
        return ast_canonicalize(code, lang_code)
    elif use_ast and lang_code != "python":
        line_count = code.count("\n")
        if line_count >= 2:
            return ast_canonicalize(code, lang_code)
        else:
            return _canonicalize_type4_light(code, lang_code)
    elif lang_code == "python":
        for rule in _TYPE4_RULES:
            try:
                code = rule(code)
            except Exception:
                logger.warning("Canonicalization rule %s failed", rule.__name__, exc_info=True)
        return code
    else:
        return code
