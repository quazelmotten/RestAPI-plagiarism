"""
Tokenization and fingerprinting for plagiarism detection.
"""

import logging
from functools import lru_cache
from typing import List, Dict, Any, Tuple

from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_cpp as tscpp

logger = logging.getLogger(__name__)

LANGUAGE_MAP = {
    'python': Language(tspython.language()),
    'cpp': Language(tscpp.language()),
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
    file_path: str,
    lang_code: str = 'python',
    tree: Any = None
) -> List[Tuple[str, Tuple[int, int], Tuple[int, int]]]:
    """
    Tokenize a file using tree-sitter.

    Returns list of (token_type, start_point, end_point).
    """
    if tree is None:
        language = get_language(lang_code)
        parser = Parser(language)

        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            code = f.read()

        tree = parser.parse(code.encode('utf-8'))

    tokens = []

    def visit(node):
        if not node.children:
            if node.type != 'comment':
                tokens.append((node.type, node.start_point, node.end_point))
        else:
            for child in node.children:
                visit(child)

    visit(tree.root_node)
    return tokens


def compute_fingerprints(
    tokens: List[Tuple[str, Tuple[int, int], Tuple[int, int]]],
    k: int = 6,
    base: int = 257,
    mod: int = 10**9 + 7
) -> List[Dict[str, Any]]:
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

    hashes.append({
        'hash': h,
        'start': tokens[0][1],
        'end': tokens[k - 1][2],
        'kgram_idx': 0
    })

    for i in range(k, len(tokens)):
        h = (h - stable_hash(tokens[i - k][0]) * power) % mod
        h = (h * base + stable_hash(tokens[i][0])) % mod
        hashes.append({
            'hash': h,
            'start': tokens[i - k + 1][1],
            'end': tokens[i][2],
            'kgram_idx': i - k + 1
        })

    return hashes


def winnow_fingerprints(
    fingerprints: List[Dict[str, Any]],
    window_size: int = 5
) -> List[Dict[str, Any]]:
    """
    Apply winnowing algorithm: select minimum hash in each sliding window.
    """
    winnowed = []
    for i in range(len(fingerprints) - window_size + 1):
        window = fingerprints[i:i + window_size]
        min_fp = min(window, key=lambda x: x['hash'])
        if not winnowed or min_fp['hash'] != winnowed[-1]['hash']:
            winnowed.append(min_fp.copy())
    return winnowed


def index_fingerprints(
    fingerprints: List[Dict[str, Any]]
) -> Dict[int, List[Dict[str, Any]]]:
    """
    Create hash -> list of fingerprint positions index.
    """
    from collections import defaultdict
    index = defaultdict(list)
    for fp in fingerprints:
        index[fp['hash']].append(fp)
    return index
