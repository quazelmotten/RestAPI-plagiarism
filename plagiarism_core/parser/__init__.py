"""Parser module: unified interface for tree-sitter parsing and language support."""

from .parser import CodeParser, parse_file, parse_string, get_language, detect_language
from .languages import (
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

__all__ = [
    "CodeParser",
    "parse_file",
    "parse_string",
    "get_language",
    "detect_language",
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
