"""Normalization utilities: identifier replacement and semantic canonicalization."""

from .canonicalizer import SemanticCanonicalizer
from .identifiers import normalize_identifiers

__all__ = ["normalize_identifiers", "SemanticCanonicalizer"]
