"""
Winnowing algorithm for selecting representative fingerprints.

Implements the classic winnowing algorithm with a sliding window to select
a minimal set of k-gram hashes that guarantees matching of any k-gram
with similarity above threshold.
"""

from dataclasses import dataclass

from .tokenizer import Token


@dataclass(frozen=True)
class Fingerprint:
    """A selected fingerprint from the winnowing process."""

    hash_value: int
    position: int  # line number or k-gram index
    token_count: int = 0  # number of tokens in the k-gram


class Winnower:
    """Window-based winnowing fingerprint selector."""

    def __init__(self, window_size: int = 4):
        """
        Initialize winnower.

        Args:
            window_size: Size of the sliding window (default 4).
                         Larger windows produce fewer fingerprints but may miss some matches.
        """
        self.window_size = window_size

    def winnow(self, hashes: list[int], positions: list[int] | None = None) -> list[Fingerprint]:
        """
        Apply winnowing algorithm to select fingerprints.

        Args:
            hashes: List of k-gram hashes (in order)
            positions: Optional list of positions (e.g., line numbers) for each hash.
                      If None, uses index positions.

        Returns:
            List of selected Fingerprint objects
        """
        if not hashes:
            return []

        if positions is None:
            positions = list(range(len(hashes)))

        assert len(hashes) == len(positions), "hashes and positions must have same length"

        fingerprints = []
        n = len(hashes)

        # For the first window, select minimum hash and its position
        min_hash = min(hashes[: self.window_size])
        min_idx = hashes[: self.window_size].index(min_hash)
        fingerprints.append(Fingerprint(hash_value=min_hash, position=positions[min_idx]))

        # Slide window through remaining hashes
        for i in range(1, n - self.window_size + 1):
            window = hashes[i : i + self.window_size]

            # If previous min hash is still in window, we might not need to select a new one
            # Actually, the classic algorithm: at each window, select the minimum hash.
            # But if the minimum is the same as the previous window's minimum and it's still
            # within the window (i.e., its index >= i), we skip adding it again.

            window_min = min(window)
            window_min_idx = i + window.index(window_min)

            # Check if this is the same fingerprint as last selected
            if window_min == min_hash and window_min_idx == min_idx:
                # Same minimum, carry forward (already in list)
                pass
            else:
                # New minimum selected
                fingerprints.append(
                    Fingerprint(
                        hash_value=window_min,
                        position=positions[window_min_idx],
                        token_count=0,  # can be set later if needed
                    )
                )
                min_hash = window_min
                min_idx = window_min_idx

        return fingerprints

    def winnow_with_tokens(
        self,
        kgrams: list[list[int]],  # list of token hash lists (each k-gram)
        positions: list[int] | None = None,
    ) -> list[Fingerprint]:
        """
        Winnow based on precomputed k-gram token hashes.

        Args:
            kgrams: List of k-grams, where each k-gram is a list of token hashes
            positions: Optional positions for each k-gram

        Returns:
            List of Fingerprints with combined hash values
        """
        # Compute combined hash for each k-gram
        combined_hashes = [self._combine_hashes(kg) for kg in kgrams]
        return self.winnow(combined_hashes, positions)

    @staticmethod
    def _combine_hashes(token_hashes: list[int], base: int = 257, mod: int = 10**9 + 7) -> int:
        """
        Combine token hashes into a single k-gram hash using polynomial rolling hash.

        Args:
            token_hashes: List of token hash values
            base: Base for rolling hash
            mod: Modulus

        Returns:
            Combined hash value
        """
        h = 0
        for token_hash in token_hashes:
            h = (h * base + token_hash) % mod
        return h


def compute_kgram_hashes(tokens: list[Token], k: int) -> list[list[int]]:
    """
    Compute k-grams from token stream.

    Args:
        tokens: List of Token objects
        k: k-gram size

    Returns:
        List of k-grams, where each k-gram is a list of token hashes
    """
    if len(tokens) < k:
        return []

    # Compute individual token hashes (simple hash of type+value)
    token_hashes = [hash((t.type, t.value)) & 0xFFFFFFFF for t in tokens]

    # Extract k-grams
    kgrams = []
    for i in range(len(token_hashes) - k + 1):
        kgram = token_hashes[i : i + k]
        kgrams.append(kgram)

    return kgrams
