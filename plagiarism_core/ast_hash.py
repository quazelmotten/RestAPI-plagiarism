"""
AST subtree hashing for structural similarity detection.
"""

import logging
from typing import List, Tuple, Optional

from tree_sitter import Parser

from .fingerprints import get_language, stable_hash

logger = logging.getLogger(__name__)


def hash_ast_subtrees(root, min_depth: int = 3) -> List[int]:
    """
    Hash AST subtrees with depth >= min_depth, ignoring comment nodes.
    Depth is measured as max distance to a leaf.

    Returns list of integer hash values.
    """
    hashes = []

    def visit(node):
        if node.type == 'comment':
            return 0, ""

        if not node.children:
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
            hashes.append(h)

        return depth, str(h)

    visit(root)
    return hashes


def extract_ast_hashes(
    file_path: str,
    lang_code: str,
    min_depth: int = 3,
    tree = None
) -> List[int]:
    """
    Extract AST subtree hashes from a file.
    """
    if tree is None:
        language = get_language(lang_code)
        parser = Parser(language)

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()

        tree = parser.parse(code.encode('utf-8'))

    return hash_ast_subtrees(tree.root_node, min_depth)


def ast_similarity(hashes_a: List[int], hashes_b: List[int]) -> float:
    """
    Compute Jaccard similarity between two sets of AST hashes.

    Returns:
        Similarity ratio between 0.0 and 1.0.
    """
    from collections import Counter

    ca, cb = Counter(hashes_a), Counter(hashes_b)
    intersection = sum((ca & cb).values())
    union = sum((ca | cb).values())
    return intersection / union if union else 0.0
