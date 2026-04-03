"""
Fragment builder for constructing match regions from token-level matches.
"""


from ..fingerprinting import Fingerprint
from ..models import Match


class FragmentBuilder:
    """Builds match regions from k-gram fingerprint matches."""

    @staticmethod
    def build_from_fingerprints(
        fingerprints_a: list[Fingerprint],
        fingerprints_b: list[Fingerprint],
        min_fingerprints: int = 3,
    ) -> list[Match]:
        """
        Construct matches by aligning fingerprint sequences.

        This is a more advanced algorithm for cases where we have hash collisions
        across the files. Could be used for an alternative matcher.
        """
        # Placeholder implementation
        return []
