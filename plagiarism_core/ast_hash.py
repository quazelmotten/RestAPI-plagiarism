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


def hash_ast_subtrees_with_positions(root, min_depth: int = 3) -> List[Tuple[int, Tuple[int, int], Tuple[int, int]]]:
    """
    Hash AST subtrees with their source positions.

    Returns list of (hash_value, start_point, end_point) tuples
    for subtrees with depth >= min_depth.
    """
    results = []

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
            results.append((h, node.start_point, node.end_point))

        return depth, str(h)

    visit(root)
    return results


def find_ast_matches(
    file1_path: str,
    file2_path: str,
    lang_code: str,
    min_depth: int = 3,
) -> List[dict]:
    """
    Find matching AST subtrees between two files.

    Returns matches as dicts with file1/file2 line ranges.
    Uses structural hashing to find identical subtrees,
    then merges adjacent matches.
    """
    from .matcher import merge_adjacent_matches, Match

    language = get_language(lang_code)
    parser = Parser(language)

    with open(file1_path, 'r', encoding='utf-8', errors='ignore') as f:
        code1 = f.read()
    with open(file2_path, 'r', encoding='utf-8', errors='ignore') as f:
        code2 = f.read()

    tree1 = parser.parse(code1.encode('utf-8'))
    tree2 = parser.parse(code2.encode('utf-8'))

    subtrees1 = hash_ast_subtrees_with_positions(tree1.root_node, min_depth)
    subtrees2 = hash_ast_subtrees_with_positions(tree2.root_node, min_depth)

    # Find matching subtrees by hash
    hash_to_pos2 = {}
    for h, start, end in subtrees2:
        if h not in hash_to_pos2:
            hash_to_pos2[h] = []
        hash_to_pos2[h].append((start, end))

    matches = []
    used2 = set()
    for h, start1, end1 in subtrees1:
        if h in hash_to_pos2:
            for i, (start2, end2) in enumerate(hash_to_pos2[h]):
                key = (h, i)
                if key not in used2:
                    used2.add(key)
                    matches.append(Match(
                        file1={
                            'start_line': start1[0], 'start_col': start1[1],
                            'end_line': end1[0], 'end_col': end1[1],
                        },
                        file2={
                            'start_line': start2[0], 'start_col': start2[1],
                            'end_line': end2[0], 'end_col': end2[1],
                        },
                        kgram_count=1
                    ))
                    break

    # Merge adjacent/overlapping AST matches
    merged = merge_adjacent_matches(matches, gap=1)

    return [
        {
            'file1': m.file1,
            'file2': m.file2,
            'kgram_count': m.kgram_count,
        }
        for m in merged
    ]
