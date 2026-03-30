"""
Language registry and factory functions.
"""

from .base import (
    get_language_profile,
    get_supported_languages,
    register_language_profile,
)

__all__ = ["get_language_profile", "get_supported_languages", "register_language_profile"]
