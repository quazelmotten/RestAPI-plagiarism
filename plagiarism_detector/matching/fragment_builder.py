"""
Fragment builder for constructing match regions from token-level matches.
"""

from typing import List

from ..models import Match, PlagiarismType, Region, Point
from ..fingerprinting import Fingerprint


class FragmentBuilder:
    """Builds match regions from k-gram fingerprint matches."""

    @staticmethod
    def build_from_fingerprints(
        fingerprints_a: List[Fingerprint],
        fingerprints_b: List[Fingerprint],
        min_fingerprints: int = 3,
    ) -> List[Match]:
        """
        Construct matches by aligning fingerprint sequences.

        This is a more advanced algorithm for cases where we have hash collisions
        across the files. Could be used for an alternative matcher.
        """
        # Placeholder implementation
        return []
