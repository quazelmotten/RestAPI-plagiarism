"""Backward-compatibility shim — re-exports from fingerprinting.parser."""

from ..fingerprinting.parser import parse_string_once as parse_string
from ..fingerprinting.languages import (
    get_language_profile,
    get_supported_languages,
    register_language_profile,
    LanguageProfile,
    PythonProfile,
    CProfile,
    CppProfile,
    JavaProfile,
    JavaScriptProfile,
    TypeScriptProfile,
    TSXProfile,
    GoProfile,
    RustProfile,
)
from ..fingerprinting.languages import get_language, detect_language_from_extension

__all__ = [
    "parse_string",
    "get_language",
    "detect_language_from_extension",
    "get_language_profile",
    "get_supported_languages",
    "register_language_profile",
    "LanguageProfile",
    "PythonProfile",
    "CProfile",
    "CppProfile",
    "JavaProfile",
    "JavaScriptProfile",
    "TypeScriptProfile",
    "TSXProfile",
    "GoProfile",
    "RustProfile",
]
