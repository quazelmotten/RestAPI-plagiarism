"""Identifier normalization and scope handling."""

import logging

from .hashing import stable_hash
from .parser import parse_string_once

logger = logging.getLogger(__name__)

BUILTIN_NAMES = {
    # I/O and conversion builtins
    "print",
    "input",
    "open",
    # Type constructors
    "int",
    "float",
    "str",
    "bool",
    "list",
    "dict",
    "set",
    "tuple",
    "bytes",
    "bytearray",
    "complex",
    # Iteration / collection builtins
    "len",
    "range",
    "enumerate",
    "zip",
    "map",
    "filter",
    "sorted",
    "reversed",
    "iter",
    "next",
    # Aggregation builtins
    "sum",
    "min",
    "max",
    "abs",
    "round",
    "any",
    "all",
    # Exception classes
    "Exception",
    "ValueError",
    "TypeError",
    "KeyError",
    "IndexError",
    "AttributeError",
    "RuntimeError",
    # Python keywords that may appear as identifiers in tree-sitter
    "if",
    "else",
    "elif",
    "for",
    "while",
    "return",
    "def",
    "class",
    "in",
    "not",
    "and",
    "or",
    "is",
    "None",
    "True",
    "False",
    "pass",
    "break",
    "continue",
    "import",
    "from",
    "with",
    "as",
    "try",
    "except",
    "finally",
    "raise",
    "yield",
    "lambda",
    "assert",
    "del",
    "global",
    "nonlocal",
    "async",
    "await",
    # Other languages (Java, C++, Go, Rust, JS/TS)
    "void",
    "null",
    "var",
    "let",
    "const",
    "function",
    "public",
    "private",
    "protected",
    "static",
    "final",
    "struct",
    "enum",
    "interface",
    "type",
    "impl",
    "trait",
    "self",
    "this",
    "super",
    # Common builtins / keywords in other langs
    "new",
    "delete",
    "sizeof",
    "typeof",
    "instanceof",
    "println",
    "fmt",
    "log",
    "console",
}


def _find_function_scopes(source: str, lang_code: str = "python") -> list[dict]:
    """Extract function scopes (top-level and nested, NOT inside classes)."""
    try:
        tree, source_bytes = parse_string_once(source, lang_code)
    except Exception:
        return []

    fn_types = {
        "python": ("function_definition", "decorated_definition"),
        "c": ("function_definition",),
        "cpp": ("function_definition",),
        "java": ("method_declaration", "constructor_declaration"),
        "javascript": ("function_declaration", "arrow_function", "method_definition"),
        "typescript": ("function_declaration", "arrow_function", "method_definition"),
        "tsx": ("function_declaration", "arrow_function", "method_definition"),
        "go": ("function_declaration", "method_declaration"),
        "rust": ("function_item",),
    }
    class_types = {
        "python": ("class_definition",),
        "c": ("struct_specifier",),
        "cpp": ("class_specifier", "struct_specifier"),
        "java": ("class_declaration", "interface_declaration"),
        "javascript": ("class_declaration",),
        "typescript": ("class_declaration", "interface_declaration"),
        "tsx": ("class_declaration", "interface_declaration"),
        "go": ("type_declaration",),
        "rust": ("struct_item", "enum_item", "trait_item", "impl_item"),
    }

    fn_type_set = fn_types.get(lang_code, fn_types["python"])
    cls_type_set = class_types.get(lang_code, class_types["python"])
    skip_types = set(cls_type_set)

    def _extract_from(parent, depth=0):
        results = []
        for child in parent.children:
            if child.type in skip_types:
                continue
            if child.type in fn_type_set:
                results.append(
                    {
                        "start_byte": child.start_byte,
                        "end_byte": child.end_byte,
                        "start_line": child.start_point[0],
                        "end_line": child.end_point[0],
                    }
                )
                results.extend(_extract_from(child, depth + 1))
        return results

    return _extract_from(tree.root_node)


def _normalize_in_scope(code: str, lang_code: str = "python") -> str:
    """Normalize identifiers in a single scope (function or module block).

    Each unique non-builtin identifier gets VAR_0, VAR_1, etc. assigned
    by first-occurrence order within THIS scope only.
    """
    if not code.strip():
        return code

    try:
        tree, source_bytes = parse_string_once(code, lang_code)
    except Exception:
        return code

    identifiers = []
    for node in _walk(tree.root_node):
        if node.type == "identifier" and not node.children:
            name = source_bytes[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")
            if not (name.startswith("__") and name.endswith("__")) and name not in BUILTIN_NAMES:
                identifiers.append((node.start_byte, node.end_byte, name))

    if not identifiers:
        return code

    seen: dict[str, int] = {}
    for _, _, name in identifiers:
        if name not in seen:
            seen[name] = len(seen)
    placeholders = {name: f"VAR_{idx}" for name, idx in seen.items()}

    replacements = []
    for start, end, name in identifiers:
        if name in placeholders:
            replacements.append((start, end, placeholders[name]))

    seen_positions: set[int] = set()
    unique = []
    for start, end, repl in replacements:
        if start not in seen_positions:
            seen_positions.add(start)
            unique.append((start, end, repl))

    unique.sort(key=lambda x: x[0], reverse=True)
    result = bytearray(source_bytes)
    for start, end, replacement in unique:
        result[start:end] = replacement.encode("utf-8")

    return result.decode("utf-8", errors="ignore")


def _walk(node):
    """Yield all nodes in an AST (depth-first)."""
    yield node
    for child in node.children:
        yield from _walk(child)


def _normalize_identifiers_in_scope(source: str, lang_code: str = "python") -> str:
    """
    Per-function identifier normalization (Step 1).

    Each function gets its own VAR_N numbering starting from VAR_0.
    Builtins (len, range, print, etc.) are preserved as-is (Step 2).
    Module-level code (outside any function) also gets its own scope.
    """
    try:
        tree, source_bytes = parse_string_once(source, lang_code)
    except Exception:
        logger.warning(
            "Failed to parse for per-function normalization, falling back", exc_info=True
        )
        return _normalize_in_scope(source, lang_code)

    fn_type_set = {
        "python": ("function_definition", "decorated_definition"),
        "c": ("function_definition",),
        "cpp": ("function_definition",),
        "java": ("method_declaration", "constructor_declaration"),
        "javascript": ("function_declaration", "arrow_function", "method_definition"),
        "typescript": ("function_declaration", "arrow_function", "method_definition"),
        "tsx": ("function_declaration", "arrow_function", "method_definition"),
        "go": ("function_declaration", "method_declaration"),
        "rust": ("function_item",),
    }
    cls_type_set = {
        "python": ("class_definition",),
        "c": ("struct_specifier",),
        "cpp": ("class_specifier", "struct_specifier"),
        "java": ("class_declaration", "interface_declaration"),
        "javascript": ("class_declaration",),
        "typescript": ("class_declaration", "interface_declaration"),
        "tsx": ("class_declaration", "interface_declaration"),
        "go": ("type_declaration",),
        "rust": ("struct_item", "enum_item", "trait_item", "impl_item"),
    }

    fn_types = fn_type_set.get(lang_code, fn_type_set["python"])
    cls_types = cls_type_set.get(lang_code, cls_type_set["python"])
    skip_cls = set(cls_types)

    all_scopes = []

    def _collect_fns(parent, depth=0):
        for child in parent.children:
            if child.type in skip_cls:
                continue
            if child.type in fn_types:
                all_scopes.append((child.start_byte, child.end_byte))
                _collect_fns(child, depth + 1)

    _collect_fns(tree.root_node)

    if not all_scopes:
        return _normalize_in_scope(source, lang_code)

    all_scopes.sort(key=lambda x: x[0], reverse=True)

    result_bytes = bytearray(source_bytes)
    for sb, eb in all_scopes:
        fn_source = source_bytes[sb:eb].decode("utf-8", errors="ignore")
        fn_normalized = _normalize_in_scope(fn_source, lang_code)
        result_bytes[sb:eb] = fn_normalized.encode("utf-8")

    all_scopes_asc = sorted(all_scopes, key=lambda x: x[0])
    module_parts = []
    cursor = 0
    for sb, eb in all_scopes_asc:
        if sb > cursor:
            module_source = source_bytes[cursor:sb].decode("utf-8", errors="ignore")
            module_norm = _normalize_in_scope(module_source, lang_code)
            module_parts.append((cursor, sb, module_norm))
        cursor = eb

    for sb, eb, norm in reversed(module_parts):
        result_bytes[sb:eb] = norm.encode("utf-8")

    return result_bytes.decode("utf-8", errors="ignore")


def _make_shadow_lines_scope(source: str, lang_code: str = "python") -> list[str]:
    """Produce per-function shadow lines (Step 1 + 4)."""
    normalized = _normalize_identifiers_in_scope(source, lang_code)
    return normalized.split("\n")


def _scope_shadow_hashes(source: str, lang_code: str = "python") -> set[int]:
    """Compute shadow hashes for a scope (used in semantic line matching)."""
    lines = _make_shadow_lines_scope(source, lang_code)
    hashes = set()
    for line in lines:
        h = stable_hash(line.strip()) if line.strip() else 0
        if h:
            hashes.add(h)
    return hashes
