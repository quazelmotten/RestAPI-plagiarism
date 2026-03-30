"""Normalization utilities: identifier replacement and semantic canonicalization."""

from .identifiers import normalize_identifiers
from .canonicalizer import SemanticCanonicalizer

__all__ = ["normalize_identifiers", "SemanticCanonicalizer"]
