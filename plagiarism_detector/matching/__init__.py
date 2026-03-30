"""Matching utilities: fragment building and merge strategies."""

from .merge_strategies import merge_adjacent_matches, resolve_overlaps

__all__ = ["merge_adjacent_matches", "resolve_overlaps"]
