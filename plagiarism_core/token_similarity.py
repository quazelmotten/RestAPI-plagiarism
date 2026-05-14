"""
Token-level similarity using k-grams + MinHash.

Provides a Dolos-like similarity metric that operates on token sequences
rather than AST structure. This is more resilient to:
- Semantic transforms (for → while, list comp → loop, etc.) — Type 4
- Structural reordering (function reorder, statement reorder) — Type 3
- Renaming (after identifier normalization) — Type 2

The pipeline:
  1. Walk the parse tree once, collecting identifiers and producing tokens
  2. Normalize identifier values to VAR_N (builtins preserved)
  3. Normalize literal values to LIT
  4. Extract overlapping k-grams of (type:value) pairs
  5. Compute MinHash Jaccard of k-gram sets

To avoid redundant parsing, this module works on already-parsed tree-sitter
trees rather than re-parsing source strings.
"""

import logging

from .fingerprinting.minhash import MinHash, minhash_signature
from .fingerprinting.tokenizer import Token

logger = logging.getLogger(__name__)

DEFAULT_K = 5
MINHASH_NUM_HASHES = 64

# Node types to skip during tokenization
_SKIP_TYPES = frozenset({
    "comment", "line_continue", "indent", "dedent",
    "NEWLINE", "whitespace", "END_MARKER",
})


def _tokenize_from_tree(tree, source_bytes: bytes) -> list[Token]:
    """Produce type-only tokens from an already-parsed tree.

    Returns Tokens where the `value` field is the source text and `type`
    is the semantic category (IDENT, LITERAL, KW, OP, DELIM, or the
    tree-sitter node type upper-cased). Literal values are replaced
    with ``LIT``.
    """
    tokens = []

    def visit(node):
        if node.type in _SKIP_TYPES:
            return

        line = node.start_point[0]
        col = node.start_point[1]
        value = source_bytes[node.start_byte:node.end_byte].decode("utf-8", errors="ignore").strip()

        if node.type in ("identifier", "field_identifier", "type_identifier",
                         "namespace_identifier", "property_identifier",
                         "shorthand_property_identifier"):
            tokens.append(Token(type="IDENT", value=value, line=line, col=col))
        elif node.type in ("string", "integer", "float", "char", "true", "false",
                           "nil", "null", "number_literal", "int_literal",
                           "float_literal", "char_literal", "string_literal",
                           "boolean_literal", "decimal_integer_literal",
                           "decimal_floating_point_literal"):
            tokens.append(Token(type="LITERAL", value="LIT", line=line, col=col))
        elif node.type == "comment":
            return
        elif node.children:
            for child in node.children:
                visit(child)
        else:
            token_type = _TOKEN_TYPE_MAP.get(node.type, node.type.upper())
            tokens.append(Token(type=token_type, value=value, line=line, col=col))

    visit(tree.root_node)
    return tokens


def extract_kgram_strings(tokens, k: int = DEFAULT_K) -> list[str]:
    """Extract type-only k-gram strings from a token list.

    Uses only token types (IDENT, LITERAL, KW, OP, DELIM), ignoring values.
    This makes k-grams resilient to identifier renaming and literal changes.
    """
    if len(tokens) < k:
        return []

    features = []
    for i in range(len(tokens) - k + 1):
        kgram = "|".join(t.type for t in tokens[i:i + k])
        features.append(kgram)
    return features


def token_similarity(
    source1: str,
    source2: str,
    language: str = "python",
    k: int = DEFAULT_K,
    tree1=None,
    tree2=None,
    bytes1=None,
    bytes2=None,
) -> float:
    """Compute k-gram MinHash similarity between two source strings.

    If pre-parsed trees and source bytes are provided, avoids re-parsing.

    Returns a float in ``[0.0, 1.0]``, or ``0.0`` on failure.
    """
    if tree1 is not None and bytes1 is not None:
        tokens1 = _tokenize_from_tree(tree1, bytes1)
    else:
        enc1 = _parse_and_tokenize(source1, language)
        if enc1 is None:
            return 0.0
        tokens1 = enc1

    if tree2 is not None and bytes2 is not None:
        tokens2 = _tokenize_from_tree(tree2, bytes2)
    else:
        enc2 = _parse_and_tokenize(source2, language)
        if enc2 is None:
            return 0.0
        tokens2 = enc2

    if not tokens1 or not tokens2:
        return 0.0

    kgrams1 = extract_kgram_strings(tokens1, k)
    kgrams2 = extract_kgram_strings(tokens2, k)

    if not kgrams1 or not kgrams2:
        return 0.0

    try:
        sig1 = minhash_signature(kgrams1, MINHASH_NUM_HASHES)
        sig2 = minhash_signature(kgrams2, MINHASH_NUM_HASHES)
        return float(MinHash.jaccard(sig1, sig2))
    except Exception:
        logger.warning("MinHash failed for token similarity", exc_info=True)
        return 0.0


def _parse_and_tokenize(source: str, language: str):
    """Fallback: parse and tokenize a source string."""
    from .fingerprinting.parser import parse_string_once
    try:
        tree, source_bytes = parse_string_once(source, language)
        return _tokenize_from_tree(tree, source_bytes)
    except Exception:
        logger.warning("Failed to parse for token similarity", exc_info=True)
        return None


_TOKEN_TYPE_MAP = {
    "binary_operator": "OP",
    "unary_operator": "OP",
    "comparison_operator": "OP",
    "boolean_operator": "OP",
    "assignment_operator": "OP",
    "update_expression": "OP",
    "ternary_operator": "OP",
    "if": "KW", "else": "KW", "for": "KW", "while": "KW",
    "return": "KW", "def": "KW", "class": "KW",
    "try": "KW", "except": "KW", "finally": "KW",
    "with": "KW", "as": "KW", "import": "KW", "from": "KW",
    "lambda": "KW", "yield": "KW", "async": "KW", "await": "KW",
    "do": "KW", "switch": "KW", "case": "KW", "default": "KW",
    "break": "KW", "continue": "KW", "goto": "KW",
    "throw": "KW", "catch": "KW",
    "new": "KW", "delete": "KW", "this": "KW", "super": "KW",
    "extends": "KW", "implements": "KW", "interface": "KW", "enum": "KW",
    "typedef": "KW", "struct": "KW", "union": "KW",
    "namespace": "KW", "template": "KW", "typename": "KW",
    "virtual": "KW", "override": "KW", "final": "KW",
    "constexpr": "KW", "noexcept": "KW", "friend": "KW",
    "mutable": "KW", "explicit": "KW",
    "using": "KW", "func": "KW", "defer": "KW",
    "go": "KW", "select": "KW", "chan": "KW",
    "map": "KW", "range": "KW", "package": "KW",
    "fn": "KW", "let": "KW", "mut": "KW",
    "match": "KW", "impl": "KW", "trait": "KW",
    "mod": "KW", "pub": "KW", "use": "KW",
    "crate": "KW", "self": "KW", "ref": "KW", "move": "KW",
    "void": "KW", "const": "KW", "static": "KW",
    "extern": "KW", "volatile": "KW", "register": "KW",
    "inline": "KW", "auto": "KW",
    "public": "KW", "private": "KW", "protected": "KW",
    "abstract": "KW", "synchronized": "KW", "transient": "KW",
    "native": "KW",
    "var": "KW", "function": "KW", "type": "KW",
    "declare": "KW", "readonly": "KW",
    "(": "DELIM", ")": "DELIM", "[": "DELIM", "]": "DELIM",
    "{": "DELIM", "}": "DELIM", ",": "DELIM", ".": "DELIM",
    ";": "DELIM", ":": "DELIM",
    "+": "OP", "-": "OP", "*": "OP", "/": "OP", "%": "OP",
    "=": "OP", "==": "OP", "!=": "OP", "<": "OP", ">": "OP",
    "<=": "OP", ">=": "OP",
    "and": "OP", "or": "OP", "not": "OP", "is": "OP", "in": "OP",
    "&&": "OP", "||": "OP", "!": "OP", "++": "OP", "--": "OP",
    "+=": "OP", "-=": "OP", "*=": "OP", "/=": "OP", "%=": "OP",
    "->": "OP", "::": "OP", "=>": "OP", "?": "OP",
    "<<": "OP", ">>": "OP", "&": "OP", "|": "OP", "^": "OP", "~": "OP",
}
