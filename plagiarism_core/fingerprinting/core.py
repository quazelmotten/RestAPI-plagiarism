"""Core fingerprinting: tokenization, hashing, winnowing, and indexing."""

import logging
from collections import defaultdict, deque
from typing import Any

import xxhash

from .hashing import stable_hash
from .parser import parse_file_once

logger = logging.getLogger(__name__)


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

    token_hashes = [xxhash.xxh64(t[0].encode()).intdigest() for t in tokens]

    power = pow(base, k - 1, mod)

    h = 0
    for i in range(k):
        h = (h * base + token_hashes[i]) % mod

    dq: deque = deque()
    winnowed: list[dict[str, Any]] = []

    def _process_kgram(kg_hash, kgram_idx):
        """Process one k-gram through the winnowing deque."""
        start = tokens[kgram_idx][1]
        end = tokens[kgram_idx + k - 1][2]

        while dq and dq[0][1] <= kgram_idx - window_size:
            dq.popleft()

        while dq and dq[-1][0] >= kg_hash:
            dq.pop()

        dq.append((kg_hash, kgram_idx, start, end))

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

    _process_kgram(h, 0)

    for i in range(k, n):
        h = (h - token_hashes[i - k] * power) % mod
        h = (h * base + token_hashes[i]) % mod
        _process_kgram(h, i - k + 1)

    return winnowed


def index_fingerprints(fingerprints: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    """
    Create hash -> list of fingerprint positions index.
    """
    index = defaultdict(list)
    for fp in fingerprints:
        index[fp["hash"]].append(fp)
    return index
