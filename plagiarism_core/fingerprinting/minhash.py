"""MinHash/LSH for approximate similarity detection.

This module provides MinHash signatures for functions that can be used to quickly
detect partial similarities (e.g., when a function has been modified by adding
or removing a few lines) without requiring full structural matching.
"""

import hashlib
from typing import Iterable

import numpy as np


class MinHash:
    """
    MinHash implementation for estimating Jaccard similarity between sets.
    
    This implementation uses multiple hash functions to create a signature
    that can efficiently approximate set similarity. It's particularly useful for
    detecting partially similar code (e.g., when a few lines have been added/removed).
    """

    DEFAULT_NUM_HASHES = 128
    MAX_HASH = (1 << 32) - 1

    def __init__(self, num_hashes: int = DEFAULT_NUM_HASHES, seed: int = 42):
        self.num_hashes = num_hashes
        self.seed = seed
        self._hash_params = self._generate_hash_params(num_hashes, seed)

    def _generate_hash_params(self, num_hashes: int, seed: int) -> list[tuple[int, int]]:
        """Generate random hash function parameters (a, b) for each hash function."""
        rng = np.random.default_rng(seed)
        params = []
        for i in range(num_hashes):
            a = rng.integers(1, self.MAX_HASH, dtype=np.uint32)
            b = rng.integers(0, self.MAX_HASH, dtype=np.uint32)
            params.append((int(a), int(b)))
        return params

    def _hash(self, item: str, a: int, b: int) -> int:
        """Compute hash for an item using the given parameters."""
        data = item.encode("utf-8")
        h = int(hashlib.md5(data, usedforsecurity=False).hexdigest(), 16)
        return (a * (h ^ b)) % self.MAX_HASH

    def _compute_signature(self, items: Iterable[str]) -> np.ndarray:
        """Compute MinHash signature for a set of items."""
        signature = np.full(self.num_hashes, self.MAX_HASH, dtype=np.uint32)
        
        for item in items:
            for i, (a, b) in enumerate(self._hash_params):
                h = self._hash(item, a, b)
                if h < signature[i]:
                    signature[i] = h
        
        return signature

    def signature(self, items: Iterable[str]) -> bytes:
        """Compute and return MinHash signature as bytes."""
        sig = self._compute_signature(items)
        return sig.tobytes()

    def signature_array(self, items: Iterable[str]) -> np.ndarray:
        """Compute and return MinHash signature as numpy array."""
        return self._compute_signature(items)

    @staticmethod
    def jaccard(sig_a: bytes, sig_b: bytes) -> float:
        """Estimate Jaccard similarity from two MinHash signatures."""
        a = np.frombuffer(sig_a, dtype=np.uint32)
        b = np.frombuffer(sig_b, dtype=np.uint32)
        return np.mean(a == b)


def minhash_signature(items: Iterable[str], num_hashes: int = MinHash.DEFAULT_NUM_HASHES) -> bytes:
    """
    Compute MinHash signature for a set of items.
    
    Args:
        items: Iterable of string items (e.g., node types, k-grams)
        num_hashes: Number of hash functions to use
    
    Returns:
        MinHash signature as bytes
    """
    mh = MinHash(num_hashes=num_hashes)
    return mh.signature(items)


def extract_node_types(root) -> list[str]:
    """
    Extract bag-of node types from an AST.
    
    Returns a list of node types that can be used for MinHash.
    """
    node_types = []

    def visit(node):
        node_types.append(node.type)
        for child in node.children:
            visit(child)

    visit(root)
    return node_types


def extract_kgrams(root, k: int = 3) -> list[str]:
    """
    Extract k-grams of node types from an AST.
    
    This captures local structural patterns, which is useful for
    detecting partially modified code.
    """
    node_types = extract_node_types(root)
    if len(node_types) < k:
        return [",".join(node_types)] if node_types else []
    
    kgrams = []
    for i in range(len(node_types) - k + 1):
        kgram = ",".join(node_types[i:i+k])
        kgrams.append(kgram)
    return kgrams


def function_minhash(root, num_hashes: int = MinHash.DEFAULT_NUM_HASHES) -> bytes:
    """
    Compute MinHash signature for a function's AST.
    
    Uses both node types and k-grams as features.
    """
    node_types = extract_node_types(root)
    kgrams = extract_kgrams(root, k=3)
    
    features = node_types + kgrams
    return minhash_signature(features, num_hashes)