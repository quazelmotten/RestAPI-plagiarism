"""
Winnowing algorithm for fingerprint selection.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Fingerprint:
    """A selected fingerprint from winnowing."""

    hash_value: int
    position: int
    token_count: int = 1


class Winnower:
    """Implements the winnowing algorithm for fingerprint selection."""

    def __init__(self, window_size: int = 4):
        self.window_size = window_size

    def winnow(self, hashes: list[int]) -> list[Fingerprint]:
        """
        Apply winnowing: select minimum hash in each sliding window.

        Args:
            hashes: List of k-gram hashes

        Returns:
            List of Fingerprint objects
        """
        if len(hashes) < self.window_size:
            return []

        fingerprints = []
        last_selected = -1

        for i in range(len(hashes) - self.window_size + 1):
            window = hashes[i : i + self.window_size]
            min_val = min(window)
            min_idx = i + window.index(min_val)

            if min_idx > last_selected:
                fingerprints.append(Fingerprint(hash_value=min_val, position=min_idx))
                last_selected = min_idx

        return fingerprints


def compute_kgram_hashes(tokens: list, k: int = 3) -> list[int]:
    """
    Compute k-gram hashes from a token stream.

    Args:
        tokens: List of Token objects or similar
        k: K-gram size

    Returns:
        List of k-gram hash values
    """
    if len(tokens) < k:
        return []

    from .hashing import stable_hash

    # Hash each token
    token_hashes = []
    for token in tokens:
        if hasattr(token, "type") and hasattr(token, "value"):
            h = stable_hash(f"{token.type}:{token.value}")
        else:
            h = stable_hash(str(token))
        token_hashes.append(h)

    # Compute rolling k-gram hashes
    base = 257
    mod = 10**9 + 7
    power = pow(base, k - 1, mod)

    h = 0
    for i in range(k):
        h = (h * base + token_hashes[i]) % mod

    kgram_hashes = [h]
    for i in range(k, len(token_hashes)):
        h = (h - token_hashes[i - k] * power) % mod
        h = (h * base + token_hashes[i]) % mod
        kgram_hashes.append(h)

    return kgram_hashes
