"""
Tokenization and fingerprinting for plagiarism detection.
"""

import logging
from collections import deque
from functools import lru_cache
from typing import Any

import tree_sitter_cpp as tscpp
import tree_sitter_go as tsgo
import tree_sitter_java as tsjava
import tree_sitter_javascript as tsjs
import tree_sitter_python as tspython
import tree_sitter_rust as tsrust
import tree_sitter_typescript as tsts
import xxhash
from tree_sitter import Language, Parser

logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    "python": Language(tspython.language()),
    "cpp": Language(tscpp.language()),
    "c": Language(tscpp.language()),
    "java": Language(tsjava.language()),
    "javascript": Language(tsjs.language()),
    "typescript": Language(tsts.language_typescript()),
    "tsx": Language(tsts.language_tsx()),
    "go": Language(tsgo.language()),
    "rust": Language(tsrust.language()),
}


def get_language(lang_code: str) -> Language:
    if lang_code not in LANGUAGE_MAP:
        raise ValueError(f"Unsupported language: {lang_code}")
    return LANGUAGE_MAP[lang_code]


@lru_cache(maxsize=10000)
def stable_hash(s: str) -> int:
    """Deterministic hash for cross-run stability using xxhash."""
    import xxhash

    return xxhash.xxh64(s.encode()).intdigest()


def tokenize_with_tree_sitter(
    file_path: str, lang_code: str = "python", tree: Any = None
) -> list[tuple[str, tuple[int, int], tuple[int, int]]]:
    """
    Tokenize a file using tree-sitter.

    Returns list of (token_type, start_point, end_point).
    """
    if tree is None:
        tree, _ = parse_file_once(file_path, lang_code)

    tokens = []

    def visit(node):
        if not node.children:
            if node.type != "comment":
                tokens.append((node.type, node.start_point, node.end_point))
        else:
            for child in node.children:
                visit(child)

    visit(tree.root_node)
    return tokens


def tokenize_and_hash_ast(
    file_path: str,
    lang_code: str = "python",
    tree: Any = None,
    min_depth: int = 3,
) -> tuple[list[tuple[str, tuple[int, int], tuple[int, int]]], list[int]]:
    """
    Tokenize and extract AST subtree hashes in a single tree walk.

    Returns (tokens, ast_hashes) — avoids two separate traversals.
    """
    if tree is None:
        tree, _ = parse_file_once(file_path, lang_code)

    tokens = []
    ast_hashes = []

    def visit(node):
        if node.type == "comment":
            return 0, ""

        if not node.children:
            tokens.append((node.type, node.start_point, node.end_point))
            return 1, ""

        child_results = [visit(c) for c in node.children]
        child_depths = [d for d, _ in child_results if d > 0]
        child_hashes = [h for _, h in child_results if h]

        if not child_depths:
            return 1, ""

        depth = 1 + max(child_depths)
        rep = node.type + "(" + ",".join(child_hashes) + ")"

        h = stable_hash(rep)
        if depth >= min_depth:
            ast_hashes.append(h)

        return depth, str(h)

    visit(tree.root_node)
    return tokens, ast_hashes


def compute_fingerprints(
    tokens: list[tuple[str, tuple[int, int], tuple[int, int]]],
    k: int = 3,
    base: int = 257,
    mod: int = 10**9 + 7,
) -> list[dict[str, Any]]:
    """
    Compute k-gram fingerprints using Winnowing algorithm.
    """
    if len(tokens) < k:
        return []

    hashes = []
    power = pow(base, k - 1, mod)
    h = 0

    for i in range(k):
        h = (h * base + stable_hash(tokens[i][0])) % mod

    hashes.append({"hash": h, "start": tokens[0][1], "end": tokens[k - 1][2], "kgram_idx": 0})

    for i in range(k, len(tokens)):
        h = (h - stable_hash(tokens[i - k][0]) * power) % mod
        h = (h * base + stable_hash(tokens[i][0])) % mod
        hashes.append(
            {"hash": h, "start": tokens[i - k + 1][1], "end": tokens[i][2], "kgram_idx": i - k + 1}
        )

    return hashes


def winnow_fingerprints(
    fingerprints: list[dict[str, Any]], window_size: int = 3
) -> list[dict[str, Any]]:
    """
    Apply winnowing algorithm: select minimum hash in each sliding window.
    """
    winnowed: list[dict[str, Any]] = []
    for i in range(len(fingerprints) - window_size + 1):
        window = fingerprints[i : i + window_size]
        min_fp = min(window, key=lambda x: x["hash"])
        if not winnowed or min_fp["hash"] != winnowed[-1]["hash"]:
            winnowed.append(min_fp.copy())
    return winnowed


def compute_and_winnow(
    tokens: list[tuple[str, tuple[int, int], tuple[int, int]]],
    k: int = 3,
    base: int = 257,
    mod: int = 10**9 + 7,
    window_size: int = 3,
) -> list[dict[str, Any]]:
    """
    Compute k-gram fingerprints and apply winnowing in a single pass.

    Optimizations over separate compute_fingerprints + winnow_fingerprints:
    - Pre-hashes all token types up front (avoids repeated xxhash calls)
    - Uses deque-based monotonic queue for O(n) winnowing (vs O(nw) min scan)
    - Tuples internally, only creates dicts for final winnowed output
    - No intermediate list of all k-gram fingerprints
    """
    n = len(tokens)
    if n < k:
        return []

    # B) Pre-hash all token types at once
    token_hashes = [xxhash.xxh64(t[0].encode()).intdigest() for t in tokens]

    power = pow(base, k - 1, mod)

    # Compute first k-gram hash
    h = 0
    for i in range(k):
        h = (h * base + token_hashes[i]) % mod

    # C) Deque-based monotonic queue for winnowing
    # Each entry: (hash_value, kgram_idx, start_point, end_point)
    dq: deque = deque()
    winnowed: list[dict[str, Any]] = []

    def _process_kgram(kg_hash, kgram_idx):
        """Process one k-gram through the winnowing deque."""
        start = tokens[kgram_idx][1]
        end = tokens[kgram_idx + k - 1][2]

        # Remove entries outside the window
        while dq and dq[0][1] <= kgram_idx - window_size:
            dq.popleft()

        # Remove entries with larger or equal hash (monotonic)
        while dq and dq[-1][0] >= kg_hash:
            dq.pop()

        dq.append((kg_hash, kgram_idx, start, end))

        # Output minimum if we have a full window
        if kgram_idx >= window_size - 1:
            min_hash, min_idx, min_start, min_end = dq[0]
            if not winnowed or min_hash != winnowed[-1]["hash"]:
                winnowed.append(
                    {
                        "hash": min_hash,
                        "start": min_start,
                        "end": min_end,
                        "kgram_idx": min_idx,
                    }
                )

    # First k-gram
    _process_kgram(h, 0)

    # Remaining k-grams via rolling hash
    for i in range(k, n):
        h = (h - token_hashes[i - k] * power) % mod
        h = (h * base + token_hashes[i]) % mod
        _process_kgram(h, i - k + 1)

    return winnowed


def parse_file_once(file_path: str, lang_code: str = "python") -> tuple[Any, bytes]:
    """
    Parse a file once with tree-sitter, returning the tree and source bytes.

    Use this to avoid re-parsing the same file for tokenization and AST hashing.
    Pass the returned tree to tokenize_with_tree_sitter() and extract_ast_hashes().
    """
    language = get_language(lang_code)
    parser = Parser(language)

    with open(file_path, encoding="utf-8", errors="ignore") as f:
        code = f.read()

    source_bytes = code.encode("utf-8")
    tree = parser.parse(source_bytes)
    return tree, source_bytes


def parse_string_once(source: str, lang_code: str = "python") -> tuple[Any, bytes]:
    """Parse a source code string with tree-sitter. Returns (tree, source_bytes)."""
    language = get_language(lang_code)
    parser = Parser(language)
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    return tree, source_bytes


def index_fingerprints(fingerprints: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    """
    Create hash -> list of fingerprint positions index.
    """
    from collections import defaultdict

    index = defaultdict(list)
    for fp in fingerprints:
        index[fp["hash"]].append(fp)
    return index


# ---------------------------------------------------------------------------
# Per-function identifier normalization (Step 1)
# ---------------------------------------------------------------------------

# Builtins that should never be replaced with VAR_N (Step 2)
# Only true builtins, keywords, and common function/class names.
# Do NOT include instance methods like items, append, read, etc.
# since they commonly appear as student variable names.
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

    # Use _find_function_scopes inline to avoid circular import issues
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

    # Find all top-level function scopes (not inside classes)
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
        # No functions — fall back to global normalization (but with builtins)
        return _normalize_in_scope(source, lang_code)

    # Sort scopes by start_byte (descending) for byte-offset-safe replacement
    all_scopes.sort(key=lambda x: x[0], reverse=True)

    # Normalize each function scope independently
    result_bytes = bytearray(source_bytes)
    for sb, eb in all_scopes:
        fn_source = source_bytes[sb:eb].decode("utf-8", errors="ignore")
        fn_normalized = _normalize_in_scope(fn_source, lang_code)
        result_bytes[sb:eb] = fn_normalized.encode("utf-8")

    # Also normalize module-level code (outside any function)
    # Reconstruct the full file: for each gap between functions, normalize that
    all_scopes_asc = sorted(all_scopes, key=lambda x: x[0])
    module_parts = []
    cursor = 0
    for sb, eb in all_scopes_asc:
        if sb > cursor:
            module_source = source_bytes[cursor:sb].decode("utf-8", errors="ignore")
            module_norm = _normalize_in_scope(module_source, lang_code)
            module_parts.append((cursor, sb, module_norm))
        cursor = eb

    # Apply module-level normalization
    for sb, eb, norm in reversed(module_parts):
        result_bytes[sb:eb] = norm.encode("utf-8")

    return result_bytes.decode("utf-8", errors="ignore")


def _make_shadow_lines_scope(source: str, lang_code: str = "python") -> list[str]:
    """Produce per-function shadow lines (Step 1 + 4)."""
    normalized = _normalize_identifiers_in_scope(source, lang_code)
    return normalized.split("\n")


# ---------------------------------------------------------------------------
# Scope-local shadow helpers (Step 4)
# ---------------------------------------------------------------------------


def _scope_shadow_hashes(source: str, lang_code: str = "python") -> set[int]:
    """Compute shadow hashes for a scope (used in semantic line matching)."""
    lines = _make_shadow_lines_scope(source, lang_code)
    hashes = set()
    for line in lines:
        h = stable_hash(line.strip()) if line.strip() else 0
        if h:
            hashes.add(h)
    return hashes
