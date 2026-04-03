"""
Multi-level plagiarism detector.

Runs a cascade of matching strategies, each progressively more abstract:
  Level 1 – Exact line matching           → Type 1 (exact copy)
  Level 2 – Identifier-normalized lines   → Type 2 (renamed)
  Level 3 – Function structural matching  → Type 3 (reordered) / Type 2
  Level 4 – Semantic canonicalization     → Type 4 (semantic equivalent)

Each match carries a plagiarism_type, similarity score, and optional details
(renames detected, transformations applied, etc.).
"""

import logging

from tree_sitter import Node

from .canonicalizer import (
    _get_child_by_type,
    _normalize_identifiers_from_tree,
    _semantic_node_type,
    ast_canonicalize,
    canonicalize_type4,
    normalize_identifiers,
    parse_file_once_from_string,
)
from .fingerprints import _normalize_in_scope, stable_hash
from .models import Match, PlagiarismType

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Normalized-line helpers
# ---------------------------------------------------------------------------


def _strip_comments(line: str, lang_code: str = "python") -> str:
    """Remove single-line comments, respecting string literals.

    Supports:
      - Python/Ruby/Bash: #
      - C/C++/Java/JS/TS/Go/Rust: //
      - SQL/Lua: --
    Block comments (/* */) are not handled per-line — they are
    uncommon in student submissions and would require cross-line state.
    """
    # Choose the line-comment marker for this language
    if lang_code in ("python", "ruby", "perl", "bash", "shell"):
        comment_prefix = "#"
    elif lang_code in ("sql", "lua"):
        comment_prefix = "--"
    else:
        # C, cpp, java, javascript, typescript, go, rust, etc.
        comment_prefix = "//"

    in_string = False
    string_char = None
    result = []
    i = 0
    while i < len(line):
        ch = line[i]
        if not in_string:
            if ch in ('"', "'"):
                in_string = True
                string_char = ch
                result.append(ch)
            elif line[i : i + len(comment_prefix)] == comment_prefix and (
                i == 0 or line[i - 1] != "\\"
            ):
                break
            else:
                result.append(ch)
        else:
            result.append(ch)
            if ch == string_char and (i == 0 or line[i - 1] != "\\"):
                in_string = False
        i += 1
    return "".join(result).strip()


def _make_shadow_lines(
    source: str, lang_code: str = "python", tree=None, source_bytes: bytes = None
) -> list[str]:
    """Produce identifier-normalized lines (shadow version).

    Uses global normalization so that rename detection at the line level
    works correctly (different function names produce different VAR_N).
    Per-function normalization is used separately for scope-local shadow
    exclusion in _semantic_line_matches.
    """
    if tree is not None and source_bytes is not None:
        normalized = _normalize_identifiers_from_tree(tree, source_bytes, source)
    else:
        normalized = normalize_identifiers(source, lang_code)
    return normalized.split("\n")


def _make_exact_lines(source: str, lang_code: str = "python") -> list[str]:
    """Produce whitespace-and-comment-normalized lines."""
    import re

    lines = []
    for line in source.split("\n"):
        stripped = _strip_comments(line, lang_code)
        if not stripped:
            lines.append("")
        else:
            lines.append(re.sub(r"\s+", " ", stripped))
    return lines


def _line_hash(line: str) -> int:
    """Fast int hash for a normalized line using xxhash for consistency."""
    if not line:
        return 0
    return stable_hash(line)


# ---------------------------------------------------------------------------
# Level 1 + 2: Line-level matching
# ---------------------------------------------------------------------------


def _line_level_matches(
    lines_a: list[str],
    lines_b: list[str],
    shadow_a: list[str],
    shadow_b: list[str],
    min_match_lines: int = 2,
) -> list[Match]:
    """
    Match lines at two levels simultaneously.

    For each matching shadow-line region:
      - If the original lines also match → Type 1
      - If only the shadows match       → Type 2 (with rename info)
    """
    # Build hash → line-indices index for shadow B
    shadow_b_index: dict[int, list[int]] = {}
    for j, s in enumerate(shadow_b):
        if s:
            shadow_b_index.setdefault(_line_hash(s), []).append(j)

    # Build hash of exact lines for A
    exact_a_hashes = [_line_hash(ln) for ln in lines_a]
    exact_b_hashes = [_line_hash(ln) for ln in lines_b]

    # Find all A→B shadow-matching line pairs
    pair_map: dict[int, list[int]] = {}
    for i, s in enumerate(shadow_a):
        if not s:
            continue
        h = _line_hash(s)
        if h in shadow_b_index:
            pair_map[i] = shadow_b_index[h]

    # Extend matches to contiguous regions.
    # When a line in A matches multiple lines in B, prefer the B candidate
    # that produces the longest contiguous match (avoids greedy short-match
    # selection that blocks longer downstream matches).
    raw: list[tuple[int, int, int]] = []  # (start_a, start_b, length)
    visited: set[int] = set()

    for start_a in sorted(pair_map.keys()):
        if start_a in visited:
            continue
        candidates = pair_map[start_a]
        # Try all candidates, keep the one with the longest extension
        best_b, best_len = candidates[0], 0
        for start_b in candidates:
            length = 0
            ia, ib = start_a, start_b
            while (
                ia < len(shadow_a)
                and ib < len(shadow_b)
                and shadow_a[ia]
                and shadow_b[ib]
                and _line_hash(shadow_a[ia]) == _line_hash(shadow_b[ib])
            ):
                length += 1
                ia += 1
                ib += 1
            if length > best_len:
                best_b, best_len = start_b, length

        # Record the best match and mark visited
        if best_len >= min_match_lines:
            for offset in range(best_len):
                visited.add(start_a + offset)
            raw.append((start_a, best_b, best_len))

    # Greedy longest-first, non-overlapping selection
    raw.sort(key=lambda x: -x[2])
    used_a: set[int] = set()
    used_b: set[int] = set()
    matches: list[Match] = []

    for sa, sb, length in raw:
        ra = set(range(sa, sa + length))
        rb = set(range(sb, sb + length))
        if ra & used_a or rb & used_b:
            # Trim overlapping edges
            while (sa in used_a or sb in used_b) and length > 0:
                sa += 1
                sb += 1
                length -= 1
            while ((sa + length - 1) in used_a or (sb + length - 1) in used_b) and length > 0:
                length -= 1
            if length < min_match_lines:
                continue

        # Classify each line in the region
        line_details = []
        all_exact = True
        for offset in range(length):
            ia, ib = sa + offset, sb + offset
            if ia < len(exact_a_hashes) and ib < len(exact_b_hashes):
                is_exact = exact_a_hashes[ia] != 0 and exact_a_hashes[ia] == exact_b_hashes[ib]
            else:
                is_exact = False
            if not is_exact:
                all_exact = False
            line_details.append(
                {
                    "line_a": ia + 1,  # 1-indexed
                    "line_b": ib + 1,
                    "is_exact": is_exact,
                }
            )

        if all_exact:
            ptype = PlagiarismType.EXACT
            desc = None
            renames = None
        else:
            ptype = PlagiarismType.RENAMED
            renames = _extract_line_renames(lines_a, lines_b, shadow_a, shadow_b, sa, sb, length)
            desc = (
                ", ".join(f"{r['original']} → {r['renamed']}" for r in renames) if renames else None
            )

        matches.append(
            Match(
                file1={"start_line": sa, "start_col": 0, "end_line": sa + length - 1, "end_col": 0},
                file2={"start_line": sb, "start_col": 0, "end_line": sb + length - 1, "end_col": 0},
                kgram_count=length,
                plagiarism_type=ptype,
                similarity=1.0,
                details={"renames": renames} if renames else None,
                description=desc,
            )
        )
        used_a.update(range(sa, sa + length))
        used_b.update(range(sb, sb + length))

    matches.sort(key=lambda m: m.file1["start_line"])
    return matches


def _extract_line_renames(
    lines_a: list[str],
    lines_b: list[str],
    shadow_a: list[str],
    shadow_b: list[str],
    start_a: int,
    start_b: int,
    length: int,
) -> list[dict]:
    """
    For a matched shadow region, figure out which specific identifiers differ.

    Builds local VAR_N mappings per match region (first-occurrence order)
    and pairs identifiers that map to the same VAR_N across files.
    This correctly handles cases where identifiers appear in different orders.
    """
    import re

    vars_set = {f"VAR_{i}" for i in range(50)}

    def build_local_map(original_lines, shadow_lines):
        """Map VAR_N -> original name using first occurrence in the region."""
        mapping = {}
        for orig, shad in zip(original_lines, shadow_lines, strict=False):
            orig_names = [n for n in re.findall(r"\b[a-zA-Z_]\w*\b", orig) if n not in vars_set]
            shad_names = [n for n in re.findall(r"\b[a-zA-Z_]\w*\b", shad) if n in vars_set]
            for on, sn in zip(orig_names, shad_names, strict=False):
                if sn not in mapping:
                    mapping[sn] = on
        return mapping

    orig_a_lines = lines_a[start_a : start_a + length]
    shad_a_lines = shadow_a[start_a : start_a + length]
    orig_b_lines = lines_b[start_b : start_b + length]
    shad_b_lines = shadow_b[start_b : start_b + length]

    map_a = build_local_map(orig_a_lines, shad_a_lines)  # VAR_N -> name in A
    map_b = build_local_map(orig_b_lines, shad_b_lines)  # VAR_N -> name in B

    renames = []
    seen_renames: set[tuple[str, str]] = set()
    for var_n, name_a in map_a.items():
        name_b = map_b.get(var_n)
        if name_b and name_a != name_b and (name_a, name_b) not in seen_renames:
            renames.append({"original": name_a, "renamed": name_b, "line": start_a + 1})
            seen_renames.add((name_a, name_b))

    return renames


# ---------------------------------------------------------------------------
# AST structural hashing (identifier-independent, with semantic normalization)
# ---------------------------------------------------------------------------


class _FilteredNode:
    """Lightweight wrapper around a tree-sitter Node that overrides children.

    Used to present a filtered view of an AST node (e.g., parameters node
    with self/this removed) without modifying the original tree.
    """

    __slots__ = (
        "type",
        "start_point",
        "end_point",
        "start_byte",
        "end_byte",
        "children",
        "child_count",
        "is_named",
    )

    def __init__(self, node: Node, filtered_children: list):
        self.type = node.type
        self.start_point = node.start_point
        self.end_point = node.end_point
        self.start_byte = node.start_byte
        self.end_byte = node.end_byte
        self.children = filtered_children
        self.child_count = len(filtered_children)
        self.is_named = node.is_named


def _strip_self_from_params(node: Node, source_bytes: bytes, lang_code: str = "python") -> Node:
    """Return a view of a function node with self/this removed from parameters.

    For Python: removes the first 'self' identifier and its trailing comma.
    For Java/JS/TS: removes the first 'this' identifier (if present).
    Other languages: returns node unchanged.
    """
    if lang_code != "python":
        return node

    # Find the function_definition node (skip decorated_definition wrapper)
    fn_node = node
    while fn_node.type == "decorated_definition":
        found = False
        for child in fn_node.children:
            if child.type == "function_definition":
                fn_node = child
                found = True
                break
        if not found:
            return node

    # Find the parameters node
    params_node = None
    for child in fn_node.children:
        if child.type == "parameters":
            params_node = child
            break

    if params_node is None:
        return node

    children = list(params_node.children)
    if len(children) < 5:
        return node  # need at least ( self , x )

    # Check if first non-paren child is 'self' or 'this'
    first = children[1]
    if first.type != "identifier" or first.children:
        return node

    name = source_bytes[first.start_byte : first.end_byte].decode("utf-8", errors="ignore")
    if name not in ("self", "this"):
        return node

    # Verify there's a comma after it (multi-param method)
    if children[2].type != ",":
        return node  # only param, don't strip

    # Remove self and its trailing comma: [0]= (, [1]=self, [2]=,, [3]=x, [4]=)
    new_children = [children[0]] + children[3:]
    filtered_params = _FilteredNode(params_node, new_children)

    # Rebuild the function node's children with filtered params
    new_fn_children = []
    for child in fn_node.children:
        if child is params_node:
            new_fn_children.append(filtered_params)
        else:
            new_fn_children.append(child)

    if fn_node is node:
        return _FilteredNode(fn_node, new_fn_children)

    filtered_fn = _FilteredNode(fn_node, new_fn_children)
    # Rebuild decorated_definition children
    new_dec_children = []
    for child in node.children:
        if child is fn_node:
            new_dec_children.append(filtered_fn)
        else:
            new_dec_children.append(child)
    return _FilteredNode(node, new_dec_children)

    # Find the function_definition node (skip decorated_definition wrapper)
    fn_node = node
    while fn_node.type == "decorated_definition":
        found = False
        for child in fn_node.children:
            if child.type == "function_definition":
                fn_node = child
                found = True
                break
        if not found:
            return node

    # Find the parameters node
    params_node = None
    for child in fn_node.children:
        if child.type == "parameters":
            params_node = child
            break

    if params_node is None:
        return node

    children = list(params_node.children)
    if len(children) < 3:
        return node

    # Check if first non-paren child is 'self'
    if (
        children[1].type == "identifier" and children[1].children == []  # leaf node
    ):
        name = node.type  # placeholder — we check below
        # We need source_bytes to read the identifier name
        # Instead, check by position: if there's a comma after it,
        # it's a multi-param method with self as first param
        if len(children) >= 5 and children[2].type == ",":
            # self is children[1], comma is children[2]
            new_children = [children[0]] + children[3:]
            filtered_params = _FilteredNode(params_node, new_children)

            # Rebuild the function node's children with filtered params
            new_fn_children = []
            for child in fn_node.children:
                if child is params_node:
                    new_fn_children.append(filtered_params)
                else:
                    new_fn_children.append(child)

            if fn_node is node:
                return _FilteredNode(fn_node, new_fn_children)
            else:
                filtered_fn = _FilteredNode(fn_node, new_fn_children)
                # Rebuild decorated_definition children
                new_dec_children = []
                for child in node.children:
                    if child is fn_node:
                        new_dec_children.append(filtered_fn)
                    else:
                        new_dec_children.append(child)
                return _FilteredNode(node, new_dec_children)

    return node


def _hash_ast_subtree(node: Node, use_semantic: bool = False) -> int:
    """
    Hash a subtree's structure, optionally using semantic normalization.

    If use_semantic=True, semantically equivalent constructs (for/while loops,
    list comprehensions/map calls, etc.) produce the same hash, enabling better
    Type 4 detection at the AST level.

    With use_semantic=False (default), the function ignores identifier names,
    so two functions with different variable names produce identical hashes
    (for Type 2 detection).

    Operator and keyword leaf values are included in the hash so that
    functions with different operators (e.g., a+b vs a-b) produce different
    hashes, preventing incorrect function pairing.
    """
    if node.type == "comment":
        return 0

    # Get the effective node type for hashing
    if use_semantic:
        hash_type = _semantic_node_type(node) or node.type
    else:
        hash_type = node.type

    if not node.children:
        if hash_type == "identifier":
            return 0  # ignore names entirely
        # Include operator and keyword leaf values in the hash
        # so that +, -, *, /, ==, etc. produce different hashes
        leaf_value = hash_type
        if node.type in (
            "+",
            "-",
            "*",
            "/",
            "%",
            "//",
            "**",
            "==",
            "!=",
            "<",
            ">",
            "<=",
            ">=",
            "and",
            "or",
            "not",
            "is",
            "in",
        ):
            leaf_value = f"{hash_type}:{node.type}"
        return stable_hash(leaf_value)

    child_hashes = []
    for child in node.children:
        ch = _hash_ast_subtree(child, use_semantic)
        if ch:
            child_hashes.append(ch)

    if not child_hashes:
        return 0

    rep = hash_type + "(" + ",".join(str(h) for h in child_hashes) + ")"
    return stable_hash(rep)


def _hash_ast_subtree_semantic(node: Node) -> int:
    """
    Hash a subtree using semantic normalization (Approach A).

    Semantically equivalent code constructs produce identical hashes:
      - for loops and while loops → same hash (LOOP)
      - list comprehensions and map() calls → same hash (COLLECTION)
      - f-strings and .format() → same hash (STRING_FORMAT)
    """
    return _hash_ast_subtree(node, use_semantic=True)


# Node types for functions/methods across languages
_FUNCTION_NODE_TYPES = {
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

# Node types for classes/structs across languages
_CLASS_NODE_TYPES = {
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


def _extract_name(node: Node, source_bytes: bytes) -> str | None:
    """Extract the name identifier from a function/class node."""
    for sub in node.children:
        if sub.type == "identifier":
            return source_bytes[sub.start_byte : sub.end_byte].decode("utf-8", errors="ignore")
        # For decorated definitions (Python), descend into the actual function
        if sub.type == "function_definition":
            return _extract_name(sub, source_bytes)
        # For C/C++: name is inside function_declarator
        if sub.type == "function_declarator":
            return _extract_name(sub, source_bytes)
        # For Java: method_declaration has identifier directly
        if sub.type == "formal_parameters":
            # Already past the name, look at siblings
            pass
    return None


def _extract_functions(
    root_node: Node, source_bytes: bytes, lang_code: str = "python"
) -> list[dict]:
    """Extract function and class definitions with structural and semantic hashes.

    Also extracts methods from inside class bodies to detect method reordering.
    Recursively traverses all nodes to find function/class definitions at any depth.
    """
    func_types = _FUNCTION_NODE_TYPES.get(lang_code, _FUNCTION_NODE_TYPES["python"])
    class_types = _CLASS_NODE_TYPES.get(lang_code, _CLASS_NODE_TYPES["python"])
    all_types = set(func_types) | set(class_types)

    def _collect(node: Node, parent_name: str = "") -> list[dict]:
        results = []
        for child in node.children:
            # Detect top-level lambda assignments as functions (for scenarios like 8b)
            if parent_name == "" and child.type == "expression_statement":
                assign = _get_child_by_type(child, "assignment")
                if assign:
                    after_eq = False
                    value_node = None
                    for c in assign.children:
                        if c.type == "=":
                            after_eq = True
                        elif after_eq and c.type not in ("comment",):
                            value_node = c
                            break
                    if value_node and value_node.type == "lambda":
                        # Extract the target identifier name
                        target_node = None
                        for c in assign.children:
                            if c.type == "identifier":
                                target_node = c
                                break
                        if target_node:
                            name = (
                                source_bytes[target_node.start_byte : target_node.end_byte]
                                .decode("utf-8", errors="ignore")
                                .strip()
                            )
                            # Compute hashes on the lambda node
                            struct_hash = _hash_ast_subtree(value_node)
                            semantic_hash = _hash_ast_subtree_semantic(value_node)
                            results.append(
                                {
                                    "name": name,
                                    "start_line": child.start_point[0],
                                    "end_line": child.end_point[0],
                                    "struct_hash": struct_hash,
                                    "semantic_hash": semantic_hash,
                                    "node": value_node,
                                }
                            )
                            # Skip further processing of this child
                            continue
            if child.type in all_types:
                name = _extract_name(child, source_bytes)
                if parent_name:
                    qualified = f"{parent_name}.{name}" if name else f"{parent_name}.<anonymous>"
                else:
                    qualified = name or "<anonymous>"

                # Strip self/this from parameters for structural hash
                # so standalone functions and methods with same body match
                if child.type in func_types:
                    hash_node = _strip_self_from_params(child, source_bytes, lang_code)
                else:
                    hash_node = child
                struct_hash = _hash_ast_subtree(hash_node)
                semantic_hash = _hash_ast_subtree_semantic(hash_node)
                results.append(
                    {
                        "name": qualified,
                        "start_line": child.start_point[0],
                        "end_line": child.end_point[0],
                        "struct_hash": struct_hash,
                        "semantic_hash": semantic_hash,
                        "node": child,
                    }
                )

                # Recurse into child to find nested functions/methods
                results.extend(
                    _collect(child, qualified if child.type in class_types else parent_name)
                )
            else:
                # Traverse intermediate nodes (block, declaration_list, etc.)
                # to find nested function/class definitions
                results.extend(_collect(child, parent_name))

        return results

    return _collect(root_node)


def _is_main_block(node: Node, source_bytes: bytes, lang_code: str = "python") -> bool:
    """Check if a node is an entry-point block.

    Python: if __name__ == "__main__":
    C/C++/Java/Go/Rust: int main() / func main() / fn main()
    """
    if lang_code == "python" and node.type == "if_statement":
        for child in node.children:
            if child.type == "comparison_operator":
                text = source_bytes[child.start_byte : child.end_byte].decode(
                    "utf-8", errors="ignore"
                )
                if "__name__" in text and "__main__" in text:
                    return True

    elif lang_code in ("cpp", "c") and node.type == "function_definition":
        for child in node.children:
            if child.type == "function_declarator":
                for sub in child.children:
                    if sub.type == "identifier":
                        name = source_bytes[sub.start_byte : sub.end_byte].decode(
                            "utf-8", errors="ignore"
                        )
                        if name == "main":
                            return True

    elif lang_code == "java" and node.type == "method_declaration":
        for child in node.children:
            if child.type == "identifier":
                name = source_bytes[child.start_byte : child.end_byte].decode(
                    "utf-8", errors="ignore"
                )
                if name == "main":
                    return True

    elif lang_code == "go" and node.type == "function_declaration":
        for child in node.children:
            if child.type == "identifier":
                name = source_bytes[child.start_byte : child.end_byte].decode(
                    "utf-8", errors="ignore"
                )
                if name == "main":
                    return True

    elif lang_code == "rust" and node.type == "function_item":
        for child in node.children:
            if child.type == "identifier":
                name = source_bytes[child.start_byte : child.end_byte].decode(
                    "utf-8", errors="ignore"
                )
                if name == "main":
                    return True

    return False


def _extract_main_block(
    root_node: Node, source_bytes: bytes, lang_code: str = "python"
) -> dict | None:
    """Extract the entry-point block as a pseudo-function.

    Python: if __name__ == "__main__": body
    C/C++/Java/Go/Rust: main() function body

    Returns a dict with start_line, end_line, body, and hashes.
    """
    for child in root_node.children:
        if _is_main_block(child, source_bytes, lang_code):
            body_node = None
            if lang_code == "python":
                for sub in child.children:
                    if sub.type == "block":
                        body_node = sub
                        break
            elif lang_code in ("cpp", "c"):
                body_node = _get_child_by_type(child, "compound_statement")
            elif lang_code == "java":
                body_node = _get_child_by_type(child, "block")
            elif lang_code == "go":
                body_node = _get_child_by_type(child, "block")
            elif lang_code == "rust":
                body_node = _get_child_by_type(child, "block")

            if body_node is None:
                continue

            struct_hash = _hash_ast_subtree(body_node)
            semantic_hash = _hash_ast_subtree_semantic(body_node)

            return {
                "name": "__main__",
                "start_line": body_node.start_point[0],
                "end_line": body_node.end_point[0],
                "if_start_line": child.start_point[0],
                "struct_hash": struct_hash,
                "semantic_hash": semantic_hash,
                "node": body_node,
            }
    return None


# ---------------------------------------------------------------------------
# Level 3: Function-level matching (reordering / renaming)
# ---------------------------------------------------------------------------


def _function_level_matches(
    source_a: str,
    source_b: str,
    used_lines_a: set[int],
    used_lines_b: set[int],
    lang_code: str = "python",
    tree_a=None,
    bytes_a: bytes = None,
    tree_b=None,
    bytes_b: bytes = None,
) -> list[Match]:
    """
    Match functions between files by structural hash (identifiers ignored).

    Produces:
      - Type 3 if the function moved to a different position
      - Type 2 if it stayed in the same position but has different names
    """
    if tree_a is None or bytes_a is None or tree_b is None or bytes_b is None:
        try:
            tree_a, bytes_a = parse_file_once_from_string(source_a, lang_code)
            tree_b, bytes_b = parse_file_once_from_string(source_b, lang_code)
        except Exception:
            logger.warning(
                "Failed to parse sources for function-level matching (lang=%s), skipping",
                lang_code,
                exc_info=True,
            )
            return []

    funcs_a = _extract_functions(tree_a.root_node, bytes_a, lang_code)
    funcs_b = _extract_functions(tree_b.root_node, bytes_b, lang_code)

    # Index B functions by struct hash
    hash_index: dict[int, list[int]] = {}
    for j, f in enumerate(funcs_b):
        if f["struct_hash"]:
            hash_index.setdefault(f["struct_hash"], []).append(j)

    used_b_idx: set[int] = set()
    matches: list[Match] = []

    for _i, fa in enumerate(funcs_a):
        # Skip if already covered by line-level matching
        func_lines_a = set(range(fa["start_line"], fa["end_line"] + 1))
        if func_lines_a & used_lines_a:
            continue
        if not fa["struct_hash"]:
            continue

        candidates = hash_index.get(fa["struct_hash"], [])
        for j in candidates:
            if j in used_b_idx:
                continue
            fb = funcs_b[j]
            func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
            if func_lines_b & used_lines_b:
                continue

            # Classify
            is_reordered = abs(fa["start_line"] - fb["start_line"]) > 2
            is_renamed = fa["name"] != fb["name"]

            if is_renamed:
                ptype = PlagiarismType.RENAMED
                desc = f"Function renamed: {fa['name']} → {fb['name']}"
            elif is_reordered:
                ptype = PlagiarismType.REORDERED
                desc = f"Function reordered: {fa['name']}"
            else:
                ptype = PlagiarismType.EXACT
                desc = None

            matches.append(
                Match(
                    file1={
                        "start_line": fa["start_line"],
                        "start_col": 0,
                        "end_line": fa["end_line"],
                        "end_col": 0,
                    },
                    file2={
                        "start_line": fb["start_line"],
                        "start_col": 0,
                        "end_line": fb["end_line"],
                        "end_col": 0,
                    },
                    kgram_count=fa["end_line"] - fa["start_line"] + 1,
                    plagiarism_type=ptype,
                    similarity=1.0,
                    details={"original_name": fa["name"], "renamed_name": fb["name"]}
                    if is_renamed
                    else None,
                    description=desc,
                )
            )
            used_b_idx.add(j)
            break

    return matches


# ---------------------------------------------------------------------------
# Level 4: Line-level semantic canonicalization
# ---------------------------------------------------------------------------


def _semantic_line_matches(
    source_a: str,
    source_b: str,
    used_lines_a: set[int],
    used_lines_b: set[int],
    lines_a: list[str],
    lines_b: list[str],
    shadow_a: list[str],
    shadow_b: list[str],
    min_match_lines: int = 2,
    lang_code: str = "python",
    func_matches: list[Match] | None = None,
) -> list[Match]:
    """
    For unmatched lines, apply Type 4 canonicalization and re-match.

    Only classifies lines as SEMANTIC if they:
      1. Don't match in original form (not EXACT)
      2. Don't match in shadow form (not RENAMED)
      3. Do match after Type 4 canonicalization (SEMANTIC)

    Step 4: Shadow exclusion is scoped to function pairs when function
    matches are available, preventing a line in one function from being
    excluded because its shadow appears in a completely different function.
    """
    # Step 4: Build scope-local shadow exclusion sets
    # For lines inside matched functions, only exclude shadows within
    # the matched function's partner (not globally).
    # For lines outside matched functions, fall back to global exclusion.
    global_shadow_b_hashes: set[int] = set()
    global_shadow_a_hashes: set[int] = set()
    for s in shadow_b:
        h = _line_hash(s.strip()) if s else 0
        if h:
            global_shadow_b_hashes.add(h)
    for s in shadow_a:
        h = _line_hash(s.strip()) if s else 0
        if h:
            global_shadow_a_hashes.add(h)

    # Build per-function shadow hash maps: line_index -> partner shadow hashes
    line_a_scoped_b: dict[int, set[int]] = {}
    line_b_scoped_a: dict[int, set[int]] = {}
    if func_matches:
        for fm in func_matches:
            a_start, a_end = fm.file1["start_line"], fm.file1["end_line"]
            b_start, b_end = fm.file2["start_line"], fm.file2["end_line"]
            # Partner B hashes for each line in A's function
            b_hashes = set()
            for j in range(b_start, min(b_end + 1, len(shadow_b))):
                h = _line_hash(shadow_b[j].strip()) if j < len(shadow_b) and shadow_b[j] else 0
                if h:
                    b_hashes.add(h)
            for i in range(a_start, min(a_end + 1, len(shadow_a))):
                line_a_scoped_b[i] = b_hashes
            # Partner A hashes for each line in B's function
            a_hashes = set()
            for i in range(a_start, min(a_end + 1, len(shadow_a))):
                h = _line_hash(shadow_a[i].strip()) if i < len(shadow_a) and shadow_a[i] else 0
                if h:
                    a_hashes.add(h)
            for j in range(b_start, min(b_end + 1, len(shadow_b))):
                line_b_scoped_a[j] = a_hashes

    def _get_exclusion_b(line_idx: int) -> set[int]:
        """Get shadow exclusion set for a line in file A."""
        if line_idx in line_a_scoped_b:
            return line_a_scoped_b[line_idx]
        return global_shadow_b_hashes

    def _get_exclusion_a(line_idx: int) -> set[int]:
        """Get shadow exclusion set for a line in file B."""
        if line_idx in line_b_scoped_a:
            return line_b_scoped_a[line_idx]
        return global_shadow_a_hashes

    # Canonicalize all unmatched lines.
    # Skip lines that match in shadow form (scope-local) — those are RENAMED, not SEMANTIC
    canon_a_lines = []
    canon_b_lines = []
    for i, line in enumerate(lines_a):
        if i in used_lines_a or not line.strip():
            canon_a_lines.append("")
        else:
            clean_line = _strip_comments(line, lang_code)
            if not clean_line:
                canon_a_lines.append("")
                continue
            # Step 4: Use scope-local shadow exclusion
            if i < len(shadow_a):
                shadow_h = _line_hash(shadow_a[i].strip())
                if shadow_h and shadow_h in _get_exclusion_b(i):
                    canon_a_lines.append("")
                    continue
            canon = canonicalize_type4(clean_line, lang_code=lang_code)
            canon_a_lines.append(canon.strip())
    for j, line in enumerate(lines_b):
        if j in used_lines_b or not line.strip():
            canon_b_lines.append("")
        else:
            clean_line = _strip_comments(line, lang_code)
            if not clean_line:
                canon_b_lines.append("")
                continue
            # Step 4: Use scope-local shadow exclusion
            if j < len(shadow_b):
                shadow_h = _line_hash(shadow_b[j].strip())
                if shadow_h and shadow_h in _get_exclusion_a(j):
                    canon_b_lines.append("")
                    continue
            canon = canonicalize_type4(clean_line, lang_code=lang_code)
            canon_b_lines.append(canon.strip())

    # Build hash index for B's canonicalized lines
    canon_b_index: dict[int, list[int]] = {}
    for j, c in enumerate(canon_b_lines):
        if c:
            canon_b_index.setdefault(_line_hash(c), []).append(j)

    # Find matching canonicalized line pairs
    pair_map: dict[int, list[int]] = {}
    for i, c in enumerate(canon_a_lines):
        if not c:
            continue
        h = _line_hash(c)
        if h in canon_b_index:
            pair_map[i] = canon_b_index[h]

    # Extend to contiguous regions of lines that match ONLY after canonicalization.
    # Match by canonical form even when shadows differ (e.g., += vs =...+).
    raw: list[tuple[int, int, int]] = []
    visited: set[int] = set()

    # Common boilerplate canonical patterns that should be rejected
    # These appear in nearly every C/C++/Java/JS competitive programming file
    _common_boilerplate_hashes: set[int] = set()
    _boilerplate_patterns = [
        "int n;",
        "int t;",
        "int m;",
        "int i;",
        "int j;",
        "int k;",
        "return 0;",
        "return 0",
        "using namespace std;",
        # Canonicalized forms (after _canonicalize_type4_light)
        "cin in n;",
        "cin in t;",
        "cin in m;",
        "cin in n",
        "cin in t",
        "cin in m",
        "cin IN n;",
        "cin IN t;",
        "cin IN m;",
        "cin IN n",
        "cin IN t",
        "cin IN m",
        "cin >> n;",
        "cin >> t;",
        "cin >> m;",
        "loop(",
        "loop (",
        "for (int i = 0; i < n; i++)",
        "for (int i=0; i<n; i++)",
        "loop (int i = 0; i < n; i++)",
    ]
    for bp in _boilerplate_patterns:
        _common_boilerplate_hashes.add(_line_hash(bp))
        _common_boilerplate_hashes.add(_line_hash(bp.lower()))
        _common_boilerplate_hashes.add(_line_hash(bp.upper()))

    for start_a in sorted(pair_map.keys()):
        if start_a in visited:
            continue
        for start_b in pair_map[start_a]:
            length = 0
            ia, ib = start_a, start_b
            while (
                ia < len(canon_a_lines)
                and ib < len(canon_b_lines)
                and canon_a_lines[ia]
                and canon_b_lines[ib]
                and _line_hash(canon_a_lines[ia]) == _line_hash(canon_b_lines[ib])
            ):
                length += 1
                visited.add(ia)
                ia += 1
                ib += 1
            if length >= min_match_lines:
                # Reject if all matched lines are common boilerplate
                all_boilerplate = True
                for offset in range(length):
                    h = _line_hash(canon_a_lines[start_a + offset])
                    if h not in _common_boilerplate_hashes:
                        all_boilerplate = False
                        break
                if all_boilerplate:
                    continue
                raw.append((start_a, start_b, length))

    # Greedy longest-first selection
    raw.sort(key=lambda x: -x[2])
    used_a: set[int] = set()
    used_b: set[int] = set()
    matches: list[Match] = []

    for sa, sb, length in raw:
        ra = set(range(sa, sa + length))
        rb = set(range(sb, sb + length))
        if ra & used_a or rb & used_b:
            while (sa in used_a or sb in used_b) and length > 0:
                sa += 1
                sb += 1
                length -= 1
            while ((sa + length - 1) in used_a or (sb + length - 1) in used_b) and length > 0:
                length -= 1
            if length < min_match_lines:
                continue

        # Build transformation description
        transforms = []
        for offset in range(length):
            ia, ib = sa + offset, sb + offset
            if ia < len(lines_a) and ib < len(lines_b):
                if lines_a[ia].strip() != lines_b[ib].strip():
                    transforms.append(
                        {
                            "line_a": ia + 1,
                            "line_b": ib + 1,
                            "original": lines_a[ia].strip()[:80],
                            "canonical": lines_b[ib].strip()[:80],
                        }
                    )

        desc = None
        if transforms:
            # Summarize the transformation types
            descs = []
            for t in transforms:
                if "for " in t["original"] and "map(" in t["canonical"]:
                    descs.append("list comprehension → map")
                elif "+=" in t["original"] or "+=" in t["canonical"]:
                    descs.append("augmented assignment")
                elif "lambda" in t["original"] or "lambda" in t["canonical"]:
                    descs.append("lambda ↔ def")
                else:
                    descs.append("semantic rewrite")
            desc = ", ".join(set(descs))

        matches.append(
            Match(
                file1={"start_line": sa, "start_col": 0, "end_line": sa + length - 1, "end_col": 0},
                file2={"start_line": sb, "start_col": 0, "end_line": sb + length - 1, "end_col": 0},
                kgram_count=length,
                plagiarism_type=PlagiarismType.SEMANTIC,
                similarity=1.0,
                details={"transformations": transforms} if transforms else None,
                description=desc,
            )
        )
        used_a.update(range(sa, sa + length))
        used_b.update(range(sb, sb + length))

    matches.sort(key=lambda m: m.file1["start_line"])
    return matches


# ---------------------------------------------------------------------------
# Level 4b: Function-level semantic canonicalization (existing)
# ---------------------------------------------------------------------------


def _semantic_function_matches(
    source_a: str,
    source_b: str,
    used_lines_a: set[int],
    used_lines_b: set[int],
    lang_code: str = "python",
    tree_a=None,
    bytes_a: bytes = None,
    tree_b=None,
    bytes_b: bytes = None,
) -> list[Match]:
    """
    Apply Type 4 semantic matching at the function level.

    Uses AST-level semantic normalization (Approach A): semantically equivalent
    constructs (for/while loops, comprehensions, f-strings, etc.) produce identical
    semantic hashes, enabling detection even when the structural hashes differ.

    For each unmatched function in A, tries to find a function in B that:
      1. Didn't match at any earlier level
      2. Has the same SEMANTIC hash (different from structural hash)
    """
    if tree_a is None or bytes_a is None or tree_b is None or bytes_b is None:
        try:
            tree_a, bytes_a = parse_file_once_from_string(source_a, lang_code)
            tree_b, bytes_b = parse_file_once_from_string(source_b, lang_code)
        except Exception:
            logger.warning(
                "Failed to parse sources for semantic function matching (lang=%s), skipping",
                lang_code,
                exc_info=True,
            )
            return []

    funcs_a = _extract_functions(tree_a.root_node, bytes_a, lang_code)
    funcs_b = _extract_functions(tree_b.root_node, bytes_b, lang_code)

    # Index B functions by semantic hash (not structural hash)
    # This catches semantically equivalent code that structurally differs
    sem_b_hashes: dict[int, list[int]] = {}
    for j, fb in enumerate(funcs_b):
        if fb["semantic_hash"]:
            sem_b_hashes.setdefault(fb["semantic_hash"], []).append(j)

    used_b_idx: set[int] = set()
    matches: list[Match] = []

    for _i, fa in enumerate(funcs_a):
        func_lines_a = set(range(fa["start_line"], fa["end_line"] + 1))
        if func_lines_a & used_lines_a:
            continue
        if not fa["semantic_hash"]:
            continue

        candidates = sem_b_hashes.get(fa["semantic_hash"], [])
        for j in candidates:
            if j in used_b_idx:
                continue
            fb = funcs_b[j]
            func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
            if func_lines_b & used_lines_b:
                continue

            # Allow semantic matching when struct hashes differ
            # (e.g., augmented assignment vs explicit assignment)
            # Skip if struct hashes are the same AND semantic hashes are the same
            # (those would be caught by function-level matching)
            if fa["struct_hash"] == fb["struct_hash"]:
                continue

            matches.append(
                Match(
                    file1={
                        "start_line": fa["start_line"],
                        "start_col": 0,
                        "end_line": fa["end_line"],
                        "end_col": 0,
                    },
                    file2={
                        "start_line": fb["start_line"],
                        "start_col": 0,
                        "end_line": fb["end_line"],
                        "end_col": 0,
                    },
                    kgram_count=fa["end_line"] - fa["start_line"] + 1,
                    plagiarism_type=PlagiarismType.SEMANTIC,
                    similarity=1.0,
                    details={
                        "original_function": fa["name"],
                        "matched_function": fb["name"],
                    },
                    description=f"Semantic equivalent: {fa['name']} ↔ {fb['name']}",
                )
            )
            used_b_idx.add(j)
            break

    return matches


# ---------------------------------------------------------------------------
# Match merging
# ---------------------------------------------------------------------------


def _merge_matches(matches: list[Match], gap: int = 0) -> list[Match]:
    """
    Merge adjacent matches that are of the SAME plagiarism type.

    Only merges matches with identical plagiarism_type to avoid
    swallowing Type 4 (semantic) lines into surrounding Type 1 (exact) regions.
    """
    if not matches:
        return []

    matches = sorted(matches, key=lambda m: (m.file1["start_line"], m.file2["start_line"]))
    merged = [
        Match(
            file1=dict(matches[0].file1),
            file2=dict(matches[0].file2),
            kgram_count=matches[0].kgram_count,
            plagiarism_type=matches[0].plagiarism_type,
            similarity=matches[0].similarity,
            details=matches[0].details,
            description=matches[0].description,
        )
    ]

    for m in matches[1:]:
        prev = merged[-1]
        f1_adj = m.file1["start_line"] <= prev.file1["end_line"] + gap + 1
        f2_adj = m.file2["start_line"] <= prev.file2["end_line"] + gap + 1
        same_type = m.plagiarism_type == prev.plagiarism_type

        if f1_adj and f2_adj and same_type:
            prev.file1["end_line"] = max(prev.file1["end_line"], m.file1["end_line"])
            prev.file2["end_line"] = max(prev.file2["end_line"], m.file2["end_line"])
            prev.kgram_count += m.kgram_count
            # Merge details
            if m.details:
                if prev.details:
                    for k, v in m.details.items():
                        if (
                            k in prev.details
                            and isinstance(prev.details[k], list)
                            and isinstance(v, list)
                        ):
                            prev.details[k].extend(v)
                        else:
                            prev.details[k] = v
                else:
                    prev.details = m.details
        else:
            merged.append(
                Match(
                    file1=dict(m.file1),
                    file2=dict(m.file2),
                    kgram_count=m.kgram_count,
                    plagiarism_type=m.plagiarism_type,
                    similarity=m.similarity,
                    details=m.details,
                    description=m.description,
                )
            )

    return merged


# ---------------------------------------------------------------------------
# Line coverage helper
# ---------------------------------------------------------------------------


def _covered_lines(matches: list[Match], is_file1: bool) -> set[int]:
    """Get the set of covered line indices (0-indexed) from matches."""
    covered: set[int] = set()
    for m in matches:
        region = m.file1 if is_file1 else m.file2
        for line in range(region["start_line"], region["end_line"] + 1):
            covered.add(line)
    return covered


def _extract_comprehension_pattern(source: str, lang_code: str = "python") -> dict | None:
    """Extract abstract pattern from a list comprehension or loop-with-append body.

    Returns {iterable, variable, element} if the source matches either pattern,
    or None otherwise. Both patterns canonicalize to the same abstract form,
    enabling detection of comprehension ↔ explicit loop equivalence.
    """
    if lang_code != "python":
        return None

    try:
        tree, source_bytes = parse_file_once_from_string(source, lang_code)
    except Exception:
        return None

    root = tree.root_node

    # If the source includes a function definition, extract its body
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

    # Pattern A: single return with list_comprehension
    if len(stmts) == 1 and stmts[0].type == "return_statement":
        ret = stmts[0]
        for child in ret.children:
            if child.type == "list_comprehension":
                return _extract_comprehension_parts(child, source_bytes)

    # Pattern B: var = [] + for var2 in iter: var.append(expr) + return var
    if len(stmts) >= 3:
        # Check: first statement is var = []
        first = stmts[0]
        if first.type == "expression_statement":
            first = _get_child_by_type(first, "assignment")
        if first and first.type == "assignment":
            children = [c for c in first.children if c.type not in ("comment", "NEWLINE")]
            if len(children) >= 3 and children[2].type == "list":
                list_node = children[2]
                list_children = [c for c in list_node.children if c.type not in ("comment",)]
                # [] has exactly [ and ]
                if len(list_children) == 2:
                    target_name = source_bytes[
                        children[0].start_byte : children[0].end_byte
                    ].decode("utf-8", errors="ignore")

                    # Check middle statements: for loop with append
                    for_stmt = None
                    for s in stmts[1:-1]:
                        if s.type == "for_statement":
                            for_stmt = s
                            break
                    if for_stmt is None:
                        # Check inside expression_statement wrapper
                        for s in stmts[1:-1]:
                            inner = _get_child_by_type(s, "for_statement")
                            if inner:
                                for_stmt = inner
                                break

                    if for_stmt:
                        result = _extract_loop_append_pattern(for_stmt, target_name, source_bytes)
                        if result:
                            # Check last statement is return target
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
    """Extract iterable, variable, element, and optional filter from a list_comprehension node."""
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
            # Extract filter condition
            for sub in child.children:
                if sub.type not in ("if",):
                    filter_text = (
                        source_bytes[sub.start_byte : sub.end_byte]
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )

    # Get element expression (first non-bracket, non-for, non-if child)
    for child in comp_node.children:
        if child.type not in (
            "[",
            "]",
            "(",
            ")",
            "for_in_clause",
            "for",
            "if_clause",
        ):
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
    """Extract iterable, variable, element from a for loop with .append()."""
    # for_statement: for variable in iterable: body
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

    # Find .append(expr) in the body, optionally guarded by an if statement
    body = _get_child_by_type(for_stmt, "block")
    filter_text = None
    if body:
        # Look for either direct append or if-wrapped append
        append_call = None
        guard_if_stmt = None
        for stmt in body.children:
            if stmt.type == "if_statement":
                # Check if the if's block contains the append
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
            # Extract element from the append call
            args = _get_child_by_type(append_call, "argument_list")
            if args:
                for arg in args.children:
                    if arg.type not in ("(", ")", ","):
                        element_text = source_bytes[arg.start_byte : arg.end_byte].decode(
                            "utf-8", errors="ignore"
                        )
                        break
            # If there was a guard if statement, extract its condition as filter
            if guard_if_stmt:
                # Find condition node (skip 'if', ':', 'block', 'else_clause')
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


def _extract_return_value(block_node, source_bytes) -> str | None:
    """Extract the return value text from a block containing a single return."""
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


def _extract_map_lambda_parts(map_call_node, source_bytes) -> dict | None:
    """Extract iterable, variable, element from a list(map(lambda ...)) pattern.
    The map_call_node is the call node for map(). Expects: map(lambda var: body, iterable)
    Returns dict with keys: iterable, variable, element.
    """
    # Check that the first argument is a lambda
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

    # Extract variable name from lambda parameters
    params_node = None
    for sub in lambda_node.children:
        if sub.type == "parameters":
            params_node = sub
            break
    var_name = ""
    if params_node:
        # Find first identifier inside parameters
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

    # Extract lambda body expression (omit the lambda keyword, parameters, colon)
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


def _extract_conditional_assign_signature(stmts, source_bytes) -> str | None:
    """Detect if/else assignment → return pattern and normalize.

    Handles:
      if cond: x = val1  else: x = val2  return x
    and:
      x = val1 if cond else val2  return x
    Both normalize to: COND_ASSIGN(cond, val1, val2, target)
    """
    if_node = stmts[0]
    if if_node.type != "if_statement":
        return None

    # Get condition
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

    # Get if-body assignment
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

    # Get else-clause assignment
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

    # Check last statement is return target
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
    """Detect nested if patterns and normalize to SAFE_OP form.

    Handles:
      if cond1:
        if cond2:
          return True
      return False
    And compound conditions:
      if cond1 and cond2:
        return True
      return False
    Both normalize to: BOOL_CHECK(cond, True, False)
    """
    if_node = stmts[0]
    if if_node.type != "if_statement":
        return None

    # Get condition text
    cond_text = None
    # Check for compound condition (and/or)
    bool_op = _get_child_by_type(if_node, "boolean_operator")
    if bool_op:
        cond_text = (
            source_bytes[bool_op.start_byte : bool_op.end_byte]
            .decode("utf-8", errors="ignore")
            .strip()
        )
    else:
        # Check for nested if (if cond1: if cond2:)
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
                # Combine outer and inner conditions
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

                    # Get return value from inner if
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
                                        # Get fallback from last statement
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
                # If inner_if found but conditions not sufficient, return None
                return None
            else:
                # No nested if; this is a simple if-else-return pattern handled by LBYL
                return None

        if not cond_text:
            # Get simple condition
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

    # Get if-body return value
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

    # Get fallback return value
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


def _extract_tuple_return_signature(stmts, source_bytes) -> str | None:
    """Detect pattern: multiple assignments followed by return tuple.
    Normalizes both to a single signature: RETURNS_TUPLE(expr1, expr2, ...).
    """
    # Case 1: single return with tuple
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
        # If no tuple, fall through to other cases

    # Case 2: multiple assignments then return tuple
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
                    # Iterate all statements except the last (return)
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


def _extract_return_chain_signature(node, source_bytes) -> str | None:
    """For complete if/elif/else chains where all branches return, extract sorted return values."""
    ret_vals = []

    # Python uses 'block', C/C++/Java/JS use 'compound_statement' or 'statement_block'
    body = _get_child_by_type(node, "block")
    if body is None:
        body = _get_child_by_type(node, "compound_statement")
    if body is None:
        body = _get_child_by_type(node, "statement_block")
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


def _extract_body_signature(source: str, lang_code: str = "python") -> str | None:
    """Extract an abstract semantic signature from a function body.

    Tries multiple strategies to find a normalized representation that
    two semantically equivalent but structurally different bodies share.
    Returns a string signature or None if no pattern matches.

    Handles:
      - Complete if/elif/else return chains → RETURNS(val1, val2, ...)
      - Comprehension ↔ loop+append → COLLECT(iter, var, elem)
      - Ternary assignment ↔ if/else assignment → ASSIGN_IF(cond, true, false)
      - Lambda ↔ def → FUNC_BODY(return_expr)
      - Dict comprehension ↔ loop → DICT_COLLECT(key, val, iter)
      - Filtered comprehension → COLLECT_FILTERED(iter, var, elem, filter)
      - Try/except ↔ pre-check → SAFE_OP(op, fallback)
      - Single return expression → RETURN(expr)
    """
    try:
        tree, source_bytes = parse_file_once_from_string(source, lang_code)
    except Exception:
        return None

    root = tree.root_node

    # Language-specific function body extraction
    if lang_code == "python":
        for child in root.children:
            fn_node = None
            if child.type == "function_definition":
                fn_node = child
            elif child.type == "decorated_definition":
                fn_node = _get_child_by_type(child, "function_definition")
            if fn_node:
                body_node = _get_child_by_type(fn_node, "block")
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
    elif lang_code in ("cpp", "c"):
        for child in root.children:
            if child.type == "function_definition":
                body_node = _get_child_by_type(child, "compound_statement")
                if body_node:
                    source = source_bytes[body_node.start_byte : body_node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    try:
                        tree, source_bytes = parse_file_once_from_string(source, lang_code)
                        root = tree.root_node
                        # Re-parsed compound_statement wraps the body — unwrap it
                        if root.children and root.children[0].type == "compound_statement":
                            root = root.children[0]
                    except Exception:
                        return None
                break
    elif lang_code == "java":
        for child in root.children:
            if child.type in ("method_declaration", "constructor_declaration"):
                body_node = _get_child_by_type(child, "block")
                if body_node:
                    source = source_bytes[body_node.start_byte : body_node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    try:
                        tree, source_bytes = parse_file_once_from_string(source, lang_code)
                        root = tree.root_node
                        if root.children and root.children[0].type == "block":
                            root = root.children[0]
                    except Exception:
                        return None
                break
    elif lang_code in ("javascript", "typescript", "tsx"):
        for child in root.children:
            if child.type in (
                "function_declaration",
                "method_definition",
                "arrow_function",
                "function",
            ):
                body_node = _get_child_by_type(child, "statement_block")
                if not body_node:
                    body_node = _get_child_by_type(child, "expression")
                if body_node:
                    source = source_bytes[body_node.start_byte : body_node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    try:
                        tree, source_bytes = parse_file_once_from_string(source, lang_code)
                        root = tree.root_node
                        if root.children and root.children[0].type == "statement_block":
                            root = root.children[0]
                    except Exception:
                        return None
                break
    elif lang_code == "go":
        for child in root.children:
            if child.type == "function_declaration":
                body_node = _get_child_by_type(child, "block")
                if body_node:
                    source = source_bytes[body_node.start_byte : body_node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    try:
                        tree, source_bytes = parse_file_once_from_string(source, lang_code)
                        root = tree.root_node
                        if root.children and root.children[0].type == "block":
                            root = root.children[0]
                    except Exception:
                        return None
                break
    elif lang_code == "rust":
        for child in root.children:
            if child.type == "function_item":
                body_node = _get_child_by_type(child, "block")
                if body_node:
                    source = source_bytes[body_node.start_byte : body_node.end_byte].decode(
                        "utf-8", errors="ignore"
                    )
                    try:
                        tree, source_bytes = parse_file_once_from_string(source, lang_code)
                        root = tree.root_node
                        if root.children and root.children[0].type == "block":
                            root = root.children[0]
                    except Exception:
                        return None
                break

    stmts = [
        c
        for c in root.children
        if c.type not in ("comment", "NEWLINE", "", "whitespace", ";", "{", "}")
    ]
    if not stmts:
        return None

    # Strategy 1: Complete if/elif/else return chain (works for Python, C++, Java, JS)
    if stmts[0].type == "if_statement":
        sig = _extract_return_chain_signature(stmts[0], source_bytes)
        if sig:
            return sig

    # Strategy 1b: If/else assignment pattern
    if stmts[0].type == "if_statement" and len(stmts) >= 2:
        sig = _extract_conditional_assign_signature(stmts, source_bytes)
        if sig:
            return sig

    # Strategy 1d: Nested if short-circuit / boolean check
    if stmts[0].type == "if_statement":
        sig = _extract_nested_if_signature(stmts, source_bytes)
        if sig:
            return sig

    # Strategy 1c: LBYL pattern
    if stmts[0].type == "if_statement" and len(stmts) >= 2:
        sig = _extract_lbyl_signature(stmts, source_bytes)
        if sig:
            return sig

    # Strategy 2: Single expression statement (ternary return, etc.)
    if len(stmts) <= 2:
        for stmt in stmts:
            # Return statement (Python, C++, Java, Go)
            if stmt.type == "return_statement":
                for child in stmt.children:
                    if child.type in ("conditional_expression", "ternary_expression"):
                        sig = _extract_ternary_signature(child, source_bytes)
                        if sig:
                            return sig
                    elif child.type not in ("return", ";", "comment"):
                        expr = (
                            source_bytes[child.start_byte : child.end_byte]
                            .decode("utf-8", errors="ignore")
                            .strip()
                        )
                        if expr and expr != ";":
                            # Only produce RETURNS for expressions with meaningful structure
                            # A bare identifier like "return a;" is too generic for matching
                            if child.type in (
                                "binary_expression",
                                "call",
                                "conditional_expression",
                                "ternary_expression",
                                "parenthesized_expression",
                            ):
                                return f"RETURNS({expr})"
            # Expression statement with assignment
            if stmt.type == "expression_statement":
                assign = _get_child_by_type(stmt, "assignment")
                if assign:
                    val_node = None
                    target_node = None
                    for sub in assign.children:
                        if sub.type == "identifier" and target_node is None:
                            target_node = sub
                        elif sub.type not in ("=",):
                            val_node = sub
                    if val_node and val_node.type in (
                        "conditional_expression",
                        "ternary_expression",
                    ):
                        sig = _extract_ternary_signature(val_node, source_bytes)
                        if sig:
                            return sig

    # Strategy 7: Single return (any expression)
    if len(stmts) == 1 and stmts[0].type == "return_statement":
        for child in stmts[0].children:
            if child.type not in ("return", ";", "comment"):
                expr = (
                    source_bytes[child.start_byte : child.end_byte]
                    .decode("utf-8", errors="ignore")
                    .strip()
                )
                if expr and expr != ";":
                    # Only produce RETURNS for expressions with meaningful structure
                    if child.type in (
                        "binary_expression",
                        "call",
                        "conditional_expression",
                        "ternary_expression",
                        "parenthesized_expression",
                        "unary_expression",
                    ):
                        return f"RETURNS({expr})"

    return None


def _extract_ternary_signature(node, source_bytes) -> str | None:
    """Extract (condition, true_value, false_value) from a conditional_expression node."""
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


def _extract_dict_pattern(stmts, source_bytes) -> str | None:
    """Detect dict comprehension ↔ loop with dict[key] = value."""
    # Check for dict comprehension in return
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

    # Check for loop with dict assignment
    if len(stmts) >= 3:
        # First: result = {}
        first = stmts[0]
        if first.type == "expression_statement":
            first = _get_child_by_type(first, "assignment")
        if first and first.type == "assignment":
            children = [c for c in first.children if c.type not in ("comment",)]
            if len(children) >= 3 and children[2].type == "dictionary":
                dict_children = [c for c in children[2].children if c.type not in ("comment",)]
                if len(dict_children) == 2:  # { }
                    target = (
                        source_bytes[children[0].start_byte : children[0].end_byte]
                        .decode("utf-8", errors="ignore")
                        .strip()
                    )

                    # Find for loop
                    for s in stmts[1:-1]:
                        for_node = _get_child_by_type(s, "for_statement")
                        if for_node:
                            # Check body has target[key] = value
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


def _extract_try_signature(try_node, source_bytes) -> str | None:
    """Extract abstract signature from try/except pattern."""
    # Get the try body operation
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

    # Get the except fallback
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


def _extract_lbyl_signature(stmts, source_bytes) -> str | None:
    """Extract abstract signature from if-check-then-return pattern (LBYL)."""
    # Pattern: if condition: return fallback ... return operation
    if_node = stmts[0]
    cond = _get_child_by_type(if_node, "comparison_operator")
    if not cond:
        cond = _get_child_by_type(if_node, "boolean_operator")
    if not cond:
        # Try first non-keyword child as condition
        for child in if_node.children:
            if child.type not in ("if", ":", "block", "comment"):
                cond = child
                break
    if not cond:
        return None

    # Get the if-body (fallback return)
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

    # Get the main operation (last return)
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


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def detect_plagiarism(
    source_a: str,
    source_b: str,
    lang_code: str = "python",
    min_match_lines: int = 2,
) -> list[Match]:
    """
    Run the full multi-level plagiarism detection pipeline.

    Returns a list of Match objects, each annotated with:
      - plagiarism_type (1-4)
      - similarity (0.0-1.0)
      - details (renames, transformations)
      - description (human-readable)

    Inverted pipeline (Step 6):
      1. Function-level matching first (structural hash → Type 2/3, then semantic hash → Type 4)
      2. Line-level matching WITHIN matched function pairs (Type 1/2)
      3. Semantic line matching for unmatched code (Type 4)
      4. Line-level matching for module-level code (outside functions)
    """
    lines_a = source_a.split("\n")
    lines_b = source_b.split("\n")

    # Parse once, reuse across all match phases
    try:
        tree_a, bytes_a = parse_file_once_from_string(source_a, lang_code)
        tree_b, bytes_b = parse_file_once_from_string(source_b, lang_code)
    except Exception:
        logger.warning(
            "Failed to parse sources (lang=%s), falling back to unoptimized path",
            lang_code,
            exc_info=True,
        )
        tree_a, bytes_a, tree_b, bytes_b = None, None, None, None

    # Generate shadow (identifier-normalized) lines using pre-parsed trees
    shadow_a = _make_shadow_lines(source_a, lang_code, tree_a, bytes_a)
    shadow_b = _make_shadow_lines(source_b, lang_code, tree_b, bytes_b)

    all_matches: list[Match] = []
    covered_a: set[int] = set()
    covered_b: set[int] = set()

    # ─── Preprocessing: Scope-local shadows for __main__ blocks ──────────
    # Global normalization assigns VAR_N based on file-wide first-occurrence
    # order. Inside __main__ blocks the same variable (e.g. "length") gets
    # different VAR_N in different files because preceding code differs.
    # This prevents Phase 3 from finding any shadow matches for __main__ code.
    #
    # Fix: replace the shadow lines for the __main__ block region with
    # scope-local normalization so that Phase 3 can match them naturally.
    if tree_a and tree_b:
        main_a = _extract_main_block(tree_a.root_node, bytes_a, lang_code)
        main_b = _extract_main_block(tree_b.root_node, bytes_b, lang_code)
        if main_a and main_b:
            a_start = main_a["if_start_line"]
            a_end = main_a["end_line"]
            b_start = main_b["if_start_line"]
            b_end = main_b["end_line"]

            body_text_a = "\n".join(lines_a[a_start : a_end + 1])
            body_text_b = "\n".join(lines_b[b_start : b_end + 1])
            norm_a = _normalize_in_scope(body_text_a, lang_code).split("\n")
            norm_b = _normalize_in_scope(body_text_b, lang_code).split("\n")

            for k, line in enumerate(norm_a):
                idx = a_start + k
                if idx < len(shadow_a):
                    shadow_a[idx] = line
            for k, line in enumerate(norm_b):
                idx = b_start + k
                if idx < len(shadow_b):
                    shadow_b[idx] = line

    # ─── Phase 1: Function-level matching (inverted hierarchy) ───────────
    if tree_a and tree_b:
        # Extract functions from both files
        funcs_a = _extract_functions(tree_a.root_node, bytes_a, lang_code)
        funcs_b = _extract_functions(tree_b.root_node, bytes_b, lang_code)

        # 1a: Match by structural hash (Type 2 renamed / Type 3 reordered)
        func_matches = _function_level_matches(
            source_a,
            source_b,
            covered_a,
            covered_b,
            lang_code,
            tree_a=tree_a,
            bytes_a=bytes_a,
            tree_b=tree_b,
            bytes_b=bytes_b,
        )
        for fm in func_matches:
            for line in range(fm.file1["start_line"], fm.file1["end_line"] + 1):
                covered_a.add(line)
            for line in range(fm.file2["start_line"], fm.file2["end_line"] + 1):
                covered_b.add(line)
        all_matches.extend(func_matches)

        # 1b: Match by semantic hash for remaining functions (Type 4)
        sem_func_matches = _semantic_function_matches(
            source_a,
            source_b,
            covered_a,
            covered_b,
            lang_code,
            tree_a=tree_a,
            bytes_a=bytes_a,
            tree_b=tree_b,
            bytes_b=bytes_b,
        )
        for fm in sem_func_matches:
            for line in range(fm.file1["start_line"], fm.file1["end_line"] + 1):
                covered_a.add(line)
            for line in range(fm.file2["start_line"], fm.file2["end_line"] + 1):
                covered_b.add(line)
        all_matches.extend(sem_func_matches)

        # 1c: Match remaining functions by name (for cases where struct/semantic hashes differ
        # but the function has the same name, e.g., for↔while loop conversion)
        name_b_index: dict[str, list[int]] = {}
        for j, fb in enumerate(funcs_b):
            func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
            if func_lines_b & covered_b:
                continue
            name_b_index.setdefault(fb["name"], []).append(j)

        for fa in funcs_a:
            func_lines_a = set(range(fa["start_line"], fa["end_line"] + 1))
            if func_lines_a & covered_a:
                continue
            candidates = name_b_index.get(fa["name"], [])
            for j in candidates:
                fb = funcs_b[j]
                func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
                if func_lines_b & covered_b:
                    continue
                # Require body similarity to avoid false positives
                # (e.g., bubble sort vs merge sort with same function name)
                fn_lines_a = lines_a[fa["start_line"] : fa["end_line"] + 1]
                fn_lines_b = lines_b[fb["start_line"] : fb["end_line"] + 1]
                fn_shadow_a = shadow_a[fa["start_line"] : fa["end_line"] + 1]
                fn_shadow_b = shadow_b[fb["start_line"] : fb["end_line"] + 1]

                # Check for meaningful body overlap using shadow lines
                # Require at least 3 matching lines or 20% of the smaller function
                body_line_match = _line_level_matches(
                    fn_lines_a, fn_lines_b, fn_shadow_a, fn_shadow_b, 3
                )
                body_sem_match = _semantic_line_matches(
                    "\n".join(fn_lines_a),
                    "\n".join(fn_lines_b),
                    set(),
                    set(),
                    fn_lines_a,
                    fn_lines_b,
                    fn_shadow_a,
                    fn_shadow_b,
                    min_match_lines=3,
                    lang_code=lang_code,
                )

                # For large functions (like main() in competitive programming),
                # require that matched lines represent a meaningful fraction
                # of the function body, not just scattered boilerplate
                if body_line_match or body_sem_match:
                    total_matched_lines = 0
                    for m in body_line_match:
                        total_matched_lines += m.file1["end_line"] - m.file1["start_line"] + 1
                    for m in body_sem_match:
                        total_matched_lines += m.file1["end_line"] - m.file1["start_line"] + 1
                    min_func_lines = min(len(fn_lines_a), len(fn_lines_b))
                    if min_func_lines > 50:
                        # For large functions, require at least 40% overlap
                        overlap_ratio = total_matched_lines / min_func_lines
                        if overlap_ratio < 0.4:
                            body_line_match = []
                            body_sem_match = []

                if not body_line_match and not body_sem_match:
                    # Fallback: compare body-level signatures.
                    # Per-line canonicalization can't bridge multi-line constructs
                    # (e.g., complete if/elif/else chains, comprehensions, ternaries).
                    # Body signature extraction processes the entire AST subtree and
                    # normalizes known patterns to comparable abstract forms.
                    body_src_a = "\n".join(fn_lines_a)
                    body_src_b = "\n".join(fn_lines_b)
                    try:
                        sig_a = _extract_body_signature(body_src_a, lang_code)
                        sig_b = _extract_body_signature(body_src_b, lang_code)
                        if not (sig_a and sig_b and sig_a == sig_b):
                            # Final fallback: raw canonical comparison — but only
                            # accept if the canonical forms are sufficiently detailed.
                            # Reject short canonical forms that are too coarse.
                            body_canon_a = ast_canonicalize(body_src_a, lang_code)
                            body_canon_b = ast_canonicalize(body_src_b, lang_code)
                            if body_canon_a != body_canon_b:
                                continue  # no similarity
                            # Even if canonical forms match, require minimum complexity
                            # to avoid false positives on trivial functions
                            if len(body_canon_a) < 50:
                                continue  # too short to be meaningful
                    except Exception:
                        continue  # parse error, skip

                # Find common prefix and suffix by shadow OR exact comparison
                # (shadow comparison may differ for def lines due to VAR_N assignment)
                min_body = min(len(fn_lines_a), len(fn_lines_b))
                prefix_len = 0
                while prefix_len < min_body:
                    sa = (fn_shadow_a[prefix_len] or "").strip()
                    sb = (fn_shadow_b[prefix_len] or "").strip()
                    exact_a = (fn_lines_a[prefix_len] or "").strip()
                    exact_b = (fn_lines_b[prefix_len] or "").strip()
                    shadow_match = sa and sb and _line_hash(sa) == _line_hash(sb)
                    exact_match = exact_a == exact_b and bool(exact_a)
                    if shadow_match or exact_match:
                        prefix_len += 1
                    else:
                        break

                suffix_len = 0
                while suffix_len < min_body - prefix_len:
                    ia = len(fn_lines_a) - 1 - suffix_len
                    ib = len(fn_lines_b) - 1 - suffix_len
                    sa = (fn_shadow_a[ia] or "").strip()
                    sb = (fn_shadow_b[ib] or "").strip()
                    exact_a = (fn_lines_a[ia] or "").strip()
                    exact_b = (fn_lines_b[ib] or "").strip()
                    shadow_match = sa and sb and _line_hash(sa) == _line_hash(sb)
                    exact_match = exact_a == exact_b and bool(exact_a)
                    if shadow_match or exact_match:
                        suffix_len += 1
                    else:
                        break

                # Compute the trimmed range (only differing middle)
                trim_a_start = fa["start_line"] + prefix_len
                trim_a_end = fa["end_line"] - suffix_len
                trim_b_start = fb["start_line"] + prefix_len
                trim_b_end = fb["end_line"] - suffix_len

                if trim_a_start > trim_a_end or trim_b_start > trim_b_end:
                    # Entire body is identical — skip name-based match,
                    # let Phase 3 find EXACT matches
                    continue

                # Check if the trimmed middle has meaningful differences.
                # If most lines are identical, don't create a T4 match —
                # let Phase 2 find exact sub-matches and Phase 4 handle
                # the truly differing lines.
                differing_lines = 0
                for k in range(prefix_len, min_body - suffix_len):
                    exact_a = (fn_lines_a[k] or "").strip()
                    exact_b = (fn_lines_b[k] or "").strip()
                    sa = (fn_shadow_a[k] or "").strip()
                    sb = (fn_shadow_b[k] or "").strip()
                    if exact_a != exact_b and not (sa and sb and _line_hash(sa) == _line_hash(sb)):
                        differing_lines += 1

                total_trimmed = min_body - prefix_len - suffix_len
                if total_trimmed > 0 and differing_lines / total_trimmed < 0.1:
                    # Less than 10% of trimmed lines actually differ —
                    # Create a RENAMED function-level match so Phase 2 can
                    # find exact sub-matches within it. Phase 2 will then
                    # remove this function-level match if sub-matches cover
                    # the function body well enough.
                    name_match = Match(
                        file1={
                            "start_line": fa["start_line"],
                            "start_col": 0,
                            "end_line": fa["end_line"],
                            "end_col": 0,
                        },
                        file2={
                            "start_line": fb["start_line"],
                            "start_col": 0,
                            "end_line": fb["end_line"],
                            "end_col": 0,
                        },
                        kgram_count=fa["end_line"] - fa["start_line"] + 1,
                        plagiarism_type=PlagiarismType.RENAMED,
                        similarity=1.0 - (differing_lines / total_trimmed),
                        details={
                            "original_function": fa["name"],
                            "matched_function": fb["name"],
                            "_mostly_identical": True,
                        },
                        description=f"Renamed function: {fa['name']} ↔ {fb['name']} (mostly identical)",
                    )
                    all_matches.append(name_match)
                    name_b_index[fa["name"]].remove(j)
                    break

                # Trimmed SEMANTIC match for only the differing portion
                name_match = Match(
                    file1={
                        "start_line": trim_a_start,
                        "start_col": 0,
                        "end_line": trim_a_end,
                        "end_col": 0,
                    },
                    file2={
                        "start_line": trim_b_start,
                        "start_col": 0,
                        "end_line": trim_b_end,
                        "end_col": 0,
                    },
                    kgram_count=trim_a_end - trim_a_start + 1,
                    plagiarism_type=PlagiarismType.SEMANTIC,
                    similarity=1.0,
                    details={"original_function": fa["name"], "matched_function": fb["name"]},
                    description=f"Semantic equivalent: {fa['name']} ↔ {fb['name']} (name-based)",
                )
                all_matches.append(name_match)
                for line in range(trim_a_start, trim_a_end + 1):
                    covered_a.add(line)
                for line in range(trim_b_start, trim_b_end + 1):
                    covered_b.add(line)
                name_b_index[fa["name"]].remove(j)
                break

        # 1d: Match remaining functions by body signature regardless of name (for scenarios like 8s)
        for fa in funcs_a:
            func_lines_a = set(range(fa["start_line"], fa["end_line"] + 1))
            if func_lines_a & covered_a:
                continue
            # Try all remaining (uncovered) functions in B
            for _j, fb in enumerate(funcs_b):
                func_lines_b = set(range(fb["start_line"], fb["end_line"] + 1))
                if func_lines_b & covered_b:
                    continue
                # Require minimum structural similarity before comparing body signatures
                # Functions with very different sizes or structures shouldn't match
                size_a = fa["end_line"] - fa["start_line"] + 1
                size_b = fb["end_line"] - fb["start_line"] + 1
                if size_a < 3 or size_b < 3:
                    continue  # Too small for meaningful comparison
                size_ratio = min(size_a, size_b) / max(size_a, size_b)
                if size_ratio < 0.5:
                    continue  # Size difference too large
                # Compare body signatures
                fn_lines_a = lines_a[fa["start_line"] : fa["end_line"] + 1]
                fn_lines_b = lines_b[fb["start_line"] : fb["end_line"] + 1]
                fn_shadow_a = shadow_a[fa["start_line"] : fa["end_line"] + 1]
                fn_shadow_b = shadow_b[fb["start_line"] : fb["end_line"] + 1]
                body_src_a = "\n".join(fn_lines_a)
                body_src_b = "\n".join(fn_lines_b)
                try:
                    sig_a = _extract_body_signature(body_src_a, lang_code)
                    sig_b = _extract_body_signature(body_src_b, lang_code)
                    if not (sig_a and sig_b and sig_a == sig_b):
                        continue
                except Exception:
                    continue
                # Find common prefix and suffix to trim non-matching parts
                min_body = min(len(fn_lines_a), len(fn_lines_b))
                prefix_len = 0
                while prefix_len < min_body:
                    sa = (fn_shadow_a[prefix_len] or "").strip()
                    sb = (fn_shadow_b[prefix_len] or "").strip()
                    exact_a = (fn_lines_a[prefix_len] or "").strip()
                    exact_b = (fn_lines_b[prefix_len] or "").strip()
                    shadow_match = sa and sb and _line_hash(sa) == _line_hash(sb)
                    exact_match = exact_a == exact_b and bool(exact_a)
                    if shadow_match or exact_match:
                        prefix_len += 1
                    else:
                        break
                suffix_len = 0
                while suffix_len < min_body - prefix_len:
                    ia = len(fn_lines_a) - 1 - suffix_len
                    ib = len(fn_lines_b) - 1 - suffix_len
                    sa = (fn_shadow_a[ia] or "").strip()
                    sb = (fn_shadow_b[ib] or "").strip()
                    exact_a = (fn_lines_a[ia] or "").strip()
                    exact_b = (fn_lines_b[ib] or "").strip()
                    shadow_match = sa and sb and _line_hash(sa) == _line_hash(sb)
                    exact_match = exact_a == exact_b and bool(exact_a)
                    if shadow_match or exact_match:
                        suffix_len += 1
                    else:
                        break
                trim_a_start = fa["start_line"] + prefix_len
                trim_a_end = fa["end_line"] - suffix_len
                trim_b_start = fb["start_line"] + prefix_len
                trim_b_end = fb["end_line"] - suffix_len
                if trim_a_start > trim_a_end or trim_b_start > trim_b_end:
                    continue
                cross_match = Match(
                    file1={
                        "start_line": trim_a_start,
                        "start_col": 0,
                        "end_line": trim_a_end,
                        "end_col": 0,
                    },
                    file2={
                        "start_line": trim_b_start,
                        "start_col": 0,
                        "end_line": trim_b_end,
                        "end_col": 0,
                    },
                    kgram_count=trim_a_end - trim_a_start + 1,
                    plagiarism_type=PlagiarismType.SEMANTIC,
                    similarity=1.0,
                    details={"original_function": fa["name"], "matched_function": fb["name"]},
                    description=f"Semantic equivalent (cross-name): {fa['name']} ↔ {fb['name']}",
                )
                all_matches.append(cross_match)
                for line in range(trim_a_start, trim_a_end + 1):
                    covered_a.add(line)
                for line in range(trim_b_start, trim_b_end + 1):
                    covered_b.add(line)
                break  # break inner loop, move to next fa

        # ─── Phase 2: Line matching WITHIN matched function pairs ────────
        # Run on all function-level matches (Type 1/2/3 and Type 4).
        # For Type 4 matches, this refines the match: exact sub-ranges become
        # Type 1, and the T4 match gets trimmed to only truly differing lines.
        # If a T4 match gets fully covered by Type 1 sub-matches, it's removed.
        for fm in all_matches[:]:  # copy to avoid modification during iteration
            a_start, a_end = fm.file1["start_line"], fm.file1["end_line"]
            b_start, b_end = fm.file2["start_line"], fm.file2["end_line"]

            # Extract lines within this function pair
            fn_lines_a = lines_a[a_start : a_end + 1]
            fn_lines_b = lines_b[b_start : b_end + 1]
            fn_shadow_a = shadow_a[a_start : a_end + 1]
            fn_shadow_b = shadow_b[b_start : b_end + 1]

            # Build local used_lines (relative to function start)
            local_used_a: set[int] = set()
            local_used_b: set[int] = set()

            # Line matching within function pair
            fn_line_matches = _line_level_matches(
                fn_lines_a,
                fn_lines_b,
                fn_shadow_a,
                fn_shadow_b,
                min_match_lines,
            )

            # Adjust line numbers to global coordinates and collect
            for m in fn_line_matches:
                m.file1["start_line"] += a_start
                m.file1["end_line"] += a_start
                m.file2["start_line"] += b_start
                m.file2["end_line"] += b_start
                # Mark these lines as covered
                for line in range(m.file1["start_line"], m.file1["end_line"] + 1):
                    covered_a.add(line)
                for line in range(m.file2["start_line"], m.file2["end_line"] + 1):
                    covered_b.add(line)

            # Semantic matching within function pair for unmatched lines
            local_used_a = set(range(len(fn_lines_a)))  # start with all used
            local_used_b = set(range(len(fn_lines_b)))
            for m in fn_line_matches:
                for line in range(
                    m.file1["start_line"] - a_start, m.file1["end_line"] - a_start + 1
                ):
                    local_used_a.discard(line)
                for line in range(
                    m.file2["start_line"] - b_start, m.file2["end_line"] - b_start + 1
                ):
                    local_used_b.discard(line)

            fn_sem_matches = _semantic_line_matches(
                "\n".join(fn_lines_a),
                "\n".join(fn_lines_b),
                local_used_a,
                local_used_b,
                fn_lines_a,
                fn_lines_b,
                fn_shadow_a,
                fn_shadow_b,
                min_match_lines=1,  # Allow single-line matches within function pairs
                lang_code=lang_code,
            )

            for m in fn_sem_matches:
                m.file1["start_line"] += a_start
                m.file1["end_line"] += a_start
                m.file2["start_line"] += b_start
                m.file2["end_line"] += b_start
                for line in range(m.file1["start_line"], m.file1["end_line"] + 1):
                    covered_a.add(line)
                for line in range(m.file2["start_line"], m.file2["end_line"] + 1):
                    covered_b.add(line)

            all_matches.extend(fn_line_matches)
            all_matches.extend(fn_sem_matches)

            # If the function-level match (fm) is mostly covered by line-level
            # sub-matches, remove it. The line-level matches provide more
            # accurate type classification (Type 1 for exact, etc.).
            # For "_mostly_identical" matches, remove if sub-matches cover
            # at least 90% of the function body.
            fm_a_range = set(range(a_start, a_end + 1))
            fm_b_range = set(range(b_start, b_end + 1))
            covered_by_sub_a = set()
            covered_by_sub_b = set()
            for m in fn_line_matches:
                for line in range(m.file1["start_line"], m.file1["end_line"] + 1):
                    covered_by_sub_a.add(line)
                for line in range(m.file2["start_line"], m.file2["end_line"] + 1):
                    covered_by_sub_b.add(line)
            for m in fn_sem_matches:
                for line in range(m.file1["start_line"], m.file1["end_line"] + 1):
                    covered_by_sub_a.add(line)
                for line in range(m.file2["start_line"], m.file2["end_line"] + 1):
                    covered_by_sub_b.add(line)

            is_mostly_identical = (
                fm.details.get("_mostly_identical", False) if fm.details else False
            )
            if is_mostly_identical:
                coverage_a = len(covered_by_sub_a) / len(fm_a_range) if fm_a_range else 0
                coverage_b = len(covered_by_sub_b) / len(fm_b_range) if fm_b_range else 0
                if coverage_a >= 0.9 and coverage_b >= 0.9:
                    all_matches.remove(fm)
            elif covered_by_sub_a == fm_a_range and covered_by_sub_b == fm_b_range:
                all_matches.remove(fm)

    # ─── Phase 3: Line matching for module-level code (outside functions) ──
    module_line_matches = _line_level_matches(lines_a, lines_b, shadow_a, shadow_b, min_match_lines)
    for m in module_line_matches:
        # Only keep if lines are not already covered
        a_range = set(range(m.file1["start_line"], m.file1["end_line"] + 1))
        b_range = set(range(m.file2["start_line"], m.file2["end_line"] + 1))
        if not (a_range & covered_a) and not (b_range & covered_b):
            all_matches.append(m)
            covered_a.update(a_range)
            covered_b.update(b_range)

    # ─── Phase 4: Semantic matching for remaining unmatched code ────────
    # Use min_match_lines=2 to avoid spurious single-line matches
    # (single-line matches within function pairs are handled in Phase 2)
    sem_line_matches = _semantic_line_matches(
        source_a,
        source_b,
        covered_a,
        covered_b,
        lines_a,
        lines_b,
        shadow_a,
        shadow_b,
        min_match_lines=2,
        lang_code=lang_code,
        func_matches=all_matches,
    )
    all_matches.extend(sem_line_matches)

    # Merge only truly adjacent (gap=0) same-type matches.
    all_matches = _merge_matches(all_matches, gap=0)

    # Sort by file A line
    all_matches.sort(key=lambda m: m.file1["start_line"])

    return all_matches


def detect_plagiarism_from_files(
    file_a: str,
    file_b: str,
    lang_code: str = "python",
    min_match_lines: int = 2,
) -> list[Match]:
    """Convenience wrapper that reads files from disk."""
    with open(file_a, encoding="utf-8", errors="ignore") as f:
        source_a = f.read()
    with open(file_b, encoding="utf-8", errors="ignore") as f:
        source_b = f.read()
    return detect_plagiarism(source_a, source_b, lang_code, min_match_lines)
