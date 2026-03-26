"""
Code canonicalization for plagiarism type detection.

Provides two main capabilities:
1. Identifier normalization (Type 2 detection) - replaces variable/function names with placeholders
2. Semantic canonicalization (Type 4 detection) - normalizes known equivalent code patterns

The semantic canonicalization uses AST-based transformation (via tree-sitter) rather than
regex, ensuring correct handling of nested structures and proper convergence of
semantically equivalent code to the same canonical form.
"""

import logging
import re
from typing import Dict, List, Set, Tuple, Optional, Any

from tree_sitter import Parser, Node

from .fingerprints import get_language, parse_file_once, stable_hash

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Semantic Node Type Map (Approach A)
# Maps AST node types to canonical semantic types for Type 4 matching
# ---------------------------------------------------------------------------

SEMANTIC_NODE_MAP: Dict[str, str] = {
    # Loops - all canonicalize to LOOP
    'for_statement': 'LOOP',
    'while_statement': 'LOOP',
    
    # Collection comprehensions - canonicalize to COLLECTION
    'list_comprehension': 'COLLECTION',
    'generator_expression': 'COLLECTION',
    'set_comprehension': 'COLLECTION',
    'dict_comprehension': 'DICT_COLLECTION',
    
    # String formatting - canonicalize to STRING_FORMAT
    'fstring': 'STRING_FORMAT',
    'string': 'STRING_FORMAT',  # tree-sitter uses 'string' for both f-string and regular
    
    # Lambda - canonicalize to FUNCTION_LITERAL
    'lambda': 'FUNCTION_LITERAL',
    
    # Augmented assignment - canonicalize to ASSIGN
    'augmented_assignment': 'ASSIGN',
    
    # Comparison operators - normalize to canonical comparison
    'comparison_operator': 'COMPARISON',
    
    # Boolean operations - normalize to canonical form
    'boolean_operator': 'BOOLEAN_OP',
}

# Node types that should be ignored entirely (comments, whitespace, etc.)
IGNORABLE_NODE_TYPES: Set[str] = {
    'comment', 'integer', 'float', 'true', 'false', 'none',
    'line_continue', 'indent', 'dedent', 'NEWLINE', 'END_MARKER',
}


def _semantic_node_type(node: Node) -> str:
    """Get the semantic type for a node, mapping equivalent constructs to the same type."""
    # First check our semantic map
    if node.type in SEMANTIC_NODE_MAP:
        return SEMANTIC_NODE_MAP[node.type]
    
    # Then check if it's ignorable
    if node.type in IGNORABLE_NODE_TYPES:
        return ''
    
    # Return the node type itself for unknown types
    return node.type


# ---------------------------------------------------------------------------
# AST-based Semantic Canonicalization (Approach B)
# Walks the AST and emits a canonical string representation
# ---------------------------------------------------------------------------

def _get_child_by_type(node: Node, child_type: str) -> Optional[Node]:
    """Get the first child of a specific type."""
    for child in node.children:
        if child.type == child_type:
            return child
    return None


def _get_source_text(node: Node, source_bytes: bytes) -> str:
    """Get the source text for a node."""
    return source_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')


def _emit_canonical(node: Node, source_bytes: bytes, depth: int = 0) -> str:
    """
    Emit a canonical string representation of an AST subtree.
    
    Two semantically equivalent code snippets should produce identical canonical strings.
    """
    if depth > 50:  # Prevent runaway recursion
        return '<RECURSION_LIMIT>'
    
    sem_type = _semantic_node_type(node)
    
    # If this node maps to a semantic type, emit that instead of the raw type
    if sem_type and sem_type not in (node.type,):
        return _emit_semantic_node(node, source_bytes, sem_type, depth)
    
    # Otherwise, recursively emit children joined
    parts = []
    for child in node.children:
        if child.type in IGNORABLE_NODE_TYPES:
            continue
        child_text = _emit_canonical(child, source_bytes, depth + 1)
        if child_text:
            parts.append(child_text)
    
    # For leaf nodes without semantic mapping, emit the type
    if not parts:
        return f'[{node.type}]'
    
    return ''.join(parts)


def _emit_semantic_node(node: Node, source_bytes: bytes, sem_type: str, depth: int) -> str:
    """Emit a canonical representation for a semantically-mapped node type."""
    
    if sem_type == 'LOOP':
        # Both for and while loops canonicalize to LOOP(ITERABLE)
        iterable = ''
        if node.type == 'for_statement':
            iter_node = _get_child_by_type(node, 'iterable')
            if iter_node:
                iterable = _emit_canonical(iter_node, source_bytes, depth + 1)
        elif node.type == 'while_statement':
            cond_node = _get_child_by_type(node, 'condition')
            if cond_node:
                iterable = _emit_canonical(cond_node, source_bytes, depth + 1)
        return f'LOOP({iterable})'
    
    elif sem_type == 'COLLECTION':
        # List comprehensions, generator expressions, list(map(...))
        element = ''
        iter_src = ''
        
        if node.type == 'list_comprehension':
            # Find element (the expression before 'for') - it's the first non-bracket child
            for child in node.children:
                if child.type in ('[', ']'):
                    continue
                if child.type == 'for_in_clause':
                    break
                # This is the element expression
                if not element:
                    element = _emit_canonical(child, source_bytes, depth + 1)
            # Find iterable from for_in_clause (the last identifier in the clause)
            for child in node.children:
                if child.type == 'for_in_clause':
                    for sub in child.children:
                        if sub.type == 'identifier':
                            iter_src = _emit_canonical(sub, source_bytes, depth + 1)
        elif node.type == 'generator_expression':
            for child in node.children:
                if child.type in ('(', ')'):
                    continue
                if child.type == 'for_in_clause':
                    break
                if not element:
                    element = _emit_canonical(child, source_bytes, depth + 1)
            for child in node.children:
                if child.type == 'for_in_clause':
                    for sub in child.children:
                        if sub.type == 'identifier':
                            iter_src = _emit_canonical(sub, source_bytes, depth + 1)
        elif node.type == 'call':
            # Handle list(map(...)) or list(... for ... in ...)
            func_node = _get_child_by_type(node, 'function')
            if func_node:
                # Check for 'list' call with single argument
                list_name = _get_source_text(func_node, source_bytes)
                if list_name == 'list':
                    args_node = _get_child_by_type(node, 'arguments')
                    if args_node:
                        first_arg = args_node.children[0] if args_node.children else None
                        if first_arg:
                            # Recursively get the semantic form of the argument
                            arg_sem = _semantic_node_type(first_arg)
                            if arg_sem == 'COLLECTION':
                                # Already a collection comprehension
                                return _emit_semantic_node(first_arg, source_bytes, 'COLLECTION', depth + 1)
                            elif first_arg.type == 'call':
                                # It's a call - check if it's map/filter
                                inner_func = _get_child_by_type(first_arg, 'function')
                                if inner_func:
                                    inner_name = _get_source_text(inner_func, source_bytes)
                                    if 'map' in inner_name or 'filter' in inner_name:
                                        # Extract from map/filter call
                                        inner_args = _get_child_by_type(first_arg, 'arguments')
                                        if inner_args and len(inner_args.children) >= 2:
                                            elem = _emit_canonical(inner_args.children[0], source_bytes, depth + 1)
                                            iterable = _emit_canonical(inner_args.children[1], source_bytes, depth + 1)
                                            return f'COLLECT({elem}, {iterable})'
        
        return f'COLLECT({element}, {iter_src})'
    
    elif sem_type == 'DICT_COLLECTION':
        key_expr = ''
        val_expr = ''
        iter_src = ''
        
        pair_node = _get_child_by_type(node, 'pair')
        if pair_node:
            key_node = _get_child_by_type(pair_node, 'key')
            val_node = _get_child_by_type(pair_node, 'value')
            if key_node:
                key_expr = _emit_canonical(key_node, source_bytes, depth + 1)
            if val_node:
                val_expr = _emit_canonical(val_node, source_bytes, depth + 1)
        
        iter_node = _get_child_by_type(node, 'iterable')
        if iter_node:
            iter_src = _emit_canonical(iter_node, source_bytes, depth + 1)
        
        return f'DICT_COLLECT({key_expr}, {val_expr}, {iter_src})'
    
    elif sem_type == 'STRING_FORMAT':
        parts = []
        
        if node.type in ('fstring', 'string'):
            for child in node.children:
                if child.type in ('string_content', 'string_start', 'string_end'):
                    text = _get_source_text(child, source_bytes)
                    if text:
                        parts.append(repr(text))
                elif child.type == 'interpolation':
                    # Extract expression inside {}
                    for sub in child.children:
                        if sub.type not in ('{', '}'):
                            parts.append(_emit_canonical(sub, source_bytes, depth + 1))
        
        return f'STRING_FORMAT({", ".join(parts)})'
    
    elif sem_type == 'FUNCTION_LITERAL':
        params = ''
        body = ''
        
        param_list = _get_child_by_type(node, 'parameters')
        if param_list:
            param_parts = []
            for child in param_list.children:
                if child.type == 'identifier':
                    param_parts.append('VAR')
            params = ', '.join(param_parts)
        
        body_node = _get_child_by_type(node, 'body')
        if body_node:
            body = _emit_canonical(body_node, source_bytes, depth + 1)
        
        return f'FUNC_LIT({params}, {body})'
    
    elif sem_type == 'ASSIGN':
        target = ''
        op = ''
        value = ''
        
        for child in node.children:
            if child.type == 'variable':
                target = _emit_canonical(child, source_bytes, depth + 1)
            elif child.type == 'operator':
                op = _get_source_text(child, source_bytes)
            elif child.type in ('integer', 'identifier', 'call'):
                value = _emit_canonical(child, source_bytes, depth + 1)
        
        return f'ASSIGN({target}, {op}, {value})'
    
    elif sem_type == 'COMPARISON':
        left = ''
        right = ''
        ops = []
        
        for child in node.children:
            text = _get_source_text(child, source_bytes)
            if text in ('==', '!=', '<', '>', '<=', '>=', 'in', 'not in', 'is', 'is not'):
                ops.append(text)
            elif not left:
                left = _emit_canonical(child, source_bytes, depth + 1)
            else:
                right = _emit_canonical(child, source_bytes, depth + 1)
        
        return f'COMPARE({left}, {", ".join(ops)}, {right})'
    
    elif sem_type == 'BOOLEAN_OP':
        ops = []
        operands = []
        for child in node.children:
            if child.type in ('and', 'or', 'not'):
                ops.append(child.type)
            else:
                operands.append(_emit_canonical(child, source_bytes, depth + 1))
        
        if 'not' in ops:
            return f'BOOL_OP(NOT, {operands[0]})'
        return f'BOOL_OP({", ".join(operands)})'
    
    # Fallback: emit semantic type with children
    parts = []
    for child in node.children:
        if child.type not in IGNORABLE_NODE_TYPES:
            child_text = _emit_canonical(child, source_bytes, depth + 1)
            if child_text:
                parts.append(child_text)
    
    return f'{sem_type}({", ".join(parts)})'


def ast_canonicalize(source: str, lang_code: str = 'python') -> str:
    """
    AST-based semantic canonicalization.
    
    Parses the source code with tree-sitter and emits a canonical string representation
    where semantically equivalent code produces identical output.
    
    This is the core of Approach B - replacing the old regex-based canonicalization.
    """
    try:
        tree, source_bytes = parse_file_once_from_string(source, lang_code)
    except Exception:
        logger.warning("Failed to parse source for AST canonicalization (lang=%s)", lang_code, exc_info=True)
        return source
    
    return _emit_canonical(tree.root_node, source_bytes)


def ast_canonicalize_with_identifiers(source: str, lang_code: str = 'python') -> str:
    """
    Full canonicalization: AST-based semantic normalization + identifier normalization.
    
    This produces the most aggressive normalization where two files with identical
    output differ only in naming and code style, not semantics.
    """
    # First apply AST-based semantic canonicalization
    semantic_result = ast_canonicalize(source, lang_code)
    
    # Then normalize identifiers
    normalized = normalize_identifiers(semantic_result, lang_code)
    
    return normalized


# ---------------------------------------------------------------------------
# Legacy regex-based canonicalization (kept for backward compatibility)
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Identifier normalization (Type 2)
# ---------------------------------------------------------------------------

def _collect_identifiers(root_node: Node, source_bytes: bytes) -> List[Tuple[int, int, str]]:
    """Collect identifier nodes from AST with (start_byte, end_byte, name)."""
    identifiers = []

    def visit(node: Node):
        if node.type == 'identifier' and not node.children:
            name = source_bytes[node.start_byte:node.end_byte].decode('utf-8', errors='ignore')
            if not (name.startswith('__') and name.endswith('__')):
                identifiers.append((node.start_byte, node.end_byte, name))
        for child in node.children:
            visit(child)

    visit(root_node)
    return identifiers


def _assign_placeholders(identifiers: List[Tuple[int, int, str]]) -> Dict[str, str]:
    """
    Map identifier names to placeholders, ordered by first occurrence in file.

    Each unique name gets VAR_0, VAR_1, etc. regardless of AST category.
    This keeps the hash stable even when the same name is used in different
    contexts (e.g., 'data' as both variable and parameter).
    """
    seen: Dict[str, int] = {}
    for _, _, name in identifiers:
        if name not in seen:
            seen[name] = len(seen)
    return {name: f'VAR_{idx}' for name, idx in seen.items()}


def _replace_identifiers(
    source_bytes: bytes,
    identifiers: List[Tuple[int, int, str]],
    placeholders: Dict[str, str],
) -> str:
    """
    Replace identifiers in source with their placeholders.

    Processes from end to start so earlier byte offsets stay valid.
    """
    if not identifiers:
        return source_bytes.decode('utf-8', errors='ignore')

    # Build (start, end, replacement) list
    replacements = []
    for start, end, name in identifiers:
        if name in placeholders:
            replacements.append((start, end, placeholders[name]))

    # Deduplicate: keep one replacement per unique position
    seen_positions = set()
    unique = []
    for start, end, repl in replacements:
        if start not in seen_positions:
            seen_positions.add(start)
            unique.append((start, end, repl))

    # Sort by start byte (descending) so we can replace without invalidating offsets
    unique.sort(key=lambda x: x[0], reverse=True)

    result = bytearray(source_bytes)
    for start, end, replacement in unique:
        result[start:end] = replacement.encode('utf-8')

    return result.decode('utf-8', errors='ignore')


def normalize_identifiers(source: str, lang_code: str = 'python') -> str:
    """
    Replace all user-defined identifiers with generic placeholders.

    Produces a 'shadow' version of the source where the only differences
    between two files are structural, not lexical.  Identical shadow output
    means the original files differ only in naming (Type 2 plagiarism).

    Example:
        def calculate_total(items):  →  def VAR_0(VAR_1):
            result = 0               →      VAR_2 = 0
            for item in items:       →      for VAR_3 in VAR_1:
                result += item       →          VAR_2 += VAR_3
            return result            →      return VAR_2
    """
    try:
        tree, source_bytes = parse_file_once_from_string(source, lang_code)
    except Exception:
        logger.warning("Failed to parse source for identifier normalization (lang=%s), returning original", lang_code, exc_info=True)
        return source

    return _normalize_identifiers_from_tree(tree, source_bytes, source)


def _normalize_identifiers_from_tree(tree, source_bytes: bytes, fallback: str) -> str:
    """Replace identifiers using a pre-parsed tree (avoids re-parsing)."""
    identifiers = _collect_identifiers(tree.root_node, source_bytes)
    if not identifiers:
        return fallback

    placeholders = _assign_placeholders(identifiers)
    return _replace_identifiers(source_bytes, identifiers, placeholders)


def get_identifier_renames(source_a: str, source_b: str, lang_code: str = 'python') -> List[Dict]:
    """
    Find specific identifier renames between two files.

    Returns list of {original, renamed, line} dicts for each rename found.
    """
    try:
        tree_a, bytes_a = parse_file_once_from_string(source_a, lang_code)
        tree_b, bytes_b = parse_file_once_from_string(source_b, lang_code)
    except Exception:
        logger.warning("Failed to parse sources for rename detection (lang=%s), returning empty", lang_code, exc_info=True)
        return []

    ids_a = _collect_identifiers(tree_a.root_node, bytes_a)
    ids_b = _collect_identifiers(tree_b.root_node, bytes_b)

    # Build occurrence-order list of unique names for each file
    order_a = []
    seen = set()
    for _, _, name in ids_a:
        if name not in seen:
            seen.add(name)
            order_a.append(name)

    order_b = []
    seen = set()
    for _, _, name in ids_b:
        if name not in seen:
            seen.add(name)
            order_b.append(name)

    # Map by position order (first in A ↔ first in B, etc.)
    renames = []
    source_lines_a = source_a.split('\n')
    for i in range(min(len(order_a), len(order_b))):
        if order_a[i] != order_b[i]:
            # Find the line where this identifier first appears
            line_num = _find_line_for_name(source_lines_a, order_a[i])
            renames.append({
                'original': order_a[i],
                'renamed': order_b[i],
                'line': line_num,
            })

    return renames


def _find_line_for_name(lines: List[str], name: str) -> int:
    """Find the first line (1-indexed) containing the given name as a word."""
    pattern = re.compile(r'\b' + re.escape(name) + r'\b')
    for i, line in enumerate(lines):
        if pattern.search(line):
            return i + 1
    return 1


# ---------------------------------------------------------------------------
# Type 4 semantic canonicalization rules
# ---------------------------------------------------------------------------

def _convert_for_to_while(code: str) -> str:
    """for x in iterable → while True with iter/next."""
    pattern = re.compile(
        r'^([ \t]*)for\s+(\w+)\s+in\s+([^\n:]+):', re.MULTILINE
    )

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
    """while i < N → for i in range(N)."""
    pattern = re.compile(
        r'(\w+)\s*=\s*0\s*\nwhile\s+\1\s*<\s*(\d+)\s*:(.*?)(\n\s*\1\s*\+=\s*1)',
        re.DOTALL,
    )

    def replacer(match):
        var, end, body = match.group(1), match.group(2), match.group(3)
        return f'for {var} in range({end}):{body}'

    return pattern.sub(replacer, code)


def _normalize_list_comprehension(code: str) -> str:
    """[expr for x in iter] → list(map(lambda x: expr, iter))."""
    pattern = re.compile(
        r'\[([^\[\]]+?)\s+for\s+(\w+)\s+in\s+([^\[\]]+?)(?:\s+if\s+([^\[\]]+?))?\]'
    )

    def replacer(match):
        expr, var, iterable, cond = match.groups()
        if cond:
            return f"list({var} for {var} in {iterable} if {cond})"
        return f"list(map(lambda {var}: {expr}, {iterable}))"

    return pattern.sub(replacer, code)


def _normalize_string_formatting(code: str) -> str:
    """f'...' → '{}'.format(...)."""
    fstring = re.compile(r'f(["\'])(.*?)\1')

    def f_to_format(match):
        content = match.group(2)
        placeholders = re.findall(r'{(.*?)}', content)
        fmt_str = re.sub(r'{.*?}', '{}', content)
        if placeholders:
            return '"{}".format({})'.format(fmt_str, ', '.join(placeholders))
        return '"{}"'.format(content)

    return fstring.sub(f_to_format, code)


def _normalize_augmented_assignment(code: str) -> str:
    """x += y → x = x + y (all augmented operators)."""
    ops = [('+', '+='), ('-', '-='), ('*', '*='), ('/', '/=')]
    for op, aug in ops:
        pattern = re.compile(
            rf'^([ \t]*)(\w+)\s*=\s*\2\s*{re.escape(op)}\s*(\w+)',
            re.MULTILINE,
        )
        code = pattern.sub(rf'\1\2 {aug} \3', code)
    return code


def _normalize_lambda_to_def(code: str) -> str:
    """name = lambda args: expr → def name(args): return expr."""
    pattern = re.compile(
        r'^([ \t]*)(\w+)\s*=\s*lambda\s+([\w\s,]+):\s*([^\n]+)',
        re.MULTILINE,
    )

    def replacer(match):
        indent, name, args, body = match.groups()
        return (
            f"{indent}def {name}({args.strip()}):\n"
            f"{indent}    return {body.strip()}"
        )

    return pattern.sub(replacer, code)


def _normalize_if_else_swap(code: str) -> str:
    """Canonicalize if/else by always putting the shorter branch second."""
    pattern = re.compile(
        r'^([ \t]*)if\s+([^\n:]+):\s*\n'
        r'((?:\1[ \t]+[^\n]*\n)+)'
        r'\1else:\s*\n'
        r'((?:\1[ \t]+[^\n]*\n?)+)',
        re.MULTILINE,
    )

    def replacer(match):
        indent = match.group(1)
        if_body = match.group(3)
        else_body = match.group(4)
        # Canonical: put shorter body in the if-branch
        if len(if_body) <= len(else_body):
            return match.group(0)
        return (
            f"{indent}if not ({match.group(2).strip()}):\n"
            f"{else_body}{indent}else:\n{if_body}"
        )

    return pattern.sub(replacer, code)


def _normalize_comparison_operators(code: str) -> str:
    """== None → is None, != None → is not None."""
    code = re.sub(r'(\w+)\s*==\s*None', r'\1 is None', code)
    code = re.sub(r'(\w+)\s*!=\s*None', r'\1 is not None', code)
    code = re.sub(r'None\s*==\s*(\w+)', r'None is \1', code)
    code = re.sub(r'None\s*!=\s*(\w+)', r'None is not \1', code)
    return code


def _normalize_compound_conditions(code: str) -> str:
    """if a and b → if a: if b:"""
    pattern = re.compile(
        r'^([ \t]*)if\s+(\w+)\s+and\s+(\w+):\s*\n'
        r'((?:\1[ \t]+[^\n]*\n?)+)',
        re.MULTILINE,
    )

    def replacer(match):
        indent, a, b, body = match.groups()
        inner = indent + "    "
        return f"{indent}if {a}:\n{inner}if {b}:\n{inner}    {body.lstrip()}"

    return pattern.sub(replacer, code)


def _normalize_dict_comprehension(code: str) -> str:
    """{k: v for k, v in iter} → lambda trick."""
    pattern = re.compile(
        r'\{(\w+)\s*:\s*(\w+)\s+for\s+(\w+)\s*,\s*(\w+)\s+in\s+([^\{\}]+?)\}'
    )

    def replacer(match):
        k_var, v_var, iterable = match.group(3), match.group(4), match.group(5)
        return (
            f"(lambda: (lambda _d: "
            f"[_d.__setitem__({k_var}, {v_var}) "
            f"for {k_var}, {v_var} in {iterable}] and _d)({{}}))()"
        )

    return pattern.sub(replacer, code)


# Ordered list of canonicalization transforms (applied sequentially).
# Each one converts a known Type-4 pattern to a standard form.
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


def canonicalize_type4(
    code: str,
    use_ast: bool = True,
    lang_code: str = 'python'
) -> str:
    """
    Apply Type 4 canonicalization to code.

    The goal is that two semantically equivalent code snippets produce the
    same (or very similar) output after canonicalization.  This is used as a
    fallback matching level — if two code regions match after
    canonicalization but not before, they are Type 4 plagiarism.

    Args:
        code: Source code to canonicalize
        use_ast: If True (default), use the new AST-based canonicalization which
                 properly handles nested structures and ensures convergence.
                 If False, uses the legacy regex-based approach.
        lang_code: Programming language (default 'python')

    Canonical forms (AST-based):
      - for/while loops → LOOP(ITERABLE)
      - list comprehensions → COLLECT(element, iterable)
      - f-strings → STRING_FORMAT(...)
      - lambdas → FUNC_LIT(args, body)
      - augmented assignment → ASSIGN(target, op, value)
      - comparisons → COMPARE(...)
      - boolean ops → BOOL_OP(...)
    """
    if use_ast and lang_code == 'python':
        # Use new AST-based canonicalization (Approach B)
        return ast_canonicalize(code, lang_code)
    elif lang_code == 'python':
        # Legacy regex-based approach (kept for backward compatibility)
        for rule in _TYPE4_RULES:
            try:
                code = rule(code)
            except Exception:
                logger.warning("Canonicalization rule %s failed", rule.__name__, exc_info=True)
        return code
    else:
        # For non-Python languages, return as-is
        return code


def canonicalize_full(source: str, lang_code: str = 'python', use_ast: bool = True) -> str:
    """
    Produce a fully canonicalized form: Type 4 rules + identifier normalization.

    This is the most aggressive normalization.  Two files whose full
    canonical forms are identical are semantically equivalent with
    possibly different names and code patterns.

    Args:
        source: Source code to canonicalize
        lang_code: Programming language (default 'python')
        use_ast: If True (default), use AST-based Type 4 canonicalization
    """
    result = source
    if lang_code == 'python':
        result = canonicalize_type4(result, use_ast=use_ast, lang_code=lang_code)
    result = normalize_identifiers(result, lang_code)
    return result


# ---------------------------------------------------------------------------
# Helper: parse a string (not file path) with tree-sitter
# ---------------------------------------------------------------------------

def parse_file_once_from_string(source: str, lang_code: str = 'python') -> Tuple:
    """
    Parse source code string with tree-sitter.

    Returns (tree, source_bytes).
    """
    language = get_language(lang_code)
    parser = Parser(language)
    source_bytes = source.encode('utf-8')
    tree = parser.parse(source_bytes)
    return tree, source_bytes
