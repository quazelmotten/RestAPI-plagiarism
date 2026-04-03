"""
Language profile definitions for plagiarism detection.

Each profile defines language-specific node types, builtins, comment markers,
and normalization rules. Profiles are auto-registered in the global registry.
"""

from abc import ABC
from typing import ClassVar


class LanguageProfile(ABC):
    """Abstract base class for language-specific configuration."""

    # Language code used in tree-sitter and throughout the system
    language_code: ClassVar[str]

    # Tree-sitter node types for functions/methods
    function_node_types: ClassVar[tuple[str, ...]]

    # Tree-sitter node types for classes/structs/enums/interfaces
    class_node_types: ClassVar[tuple[str, ...]]

    # Built-in identifiers that should never be normalized to VAR_N
    builtin_names: ClassVar[set[str]]

    # Single-line comment markers (first character is sufficient)
    comment_markers: ClassVar[set[str]]

    @classmethod
    def get_builtin_names(cls) -> set[str]:
        """Get builtin names for this language."""
        return cls.builtin_names

    @classmethod
    def get_function_node_types(cls) -> tuple[str, ...]:
        """Get function node types for this language."""
        return cls.function_node_types

    @classmethod
    def get_class_node_types(cls) -> tuple[str, ...]:
        """Get class/struct node types for this language."""
        return cls.class_node_types

    @classmethod
    def get_comment_markers(cls) -> set[str]:
        """Get comment markers for this language."""
        return cls.comment_markers


class PythonProfile(LanguageProfile):
    """Python language profile."""

    language_code = "python"
    function_node_types = ("function_definition", "decorated_definition")
    class_node_types = ("class_definition",)
    builtin_names = {
        # I/O and conversion
        "print",
        "input",
        "open",
        # Type constructors
        "int",
        "float",
        "str",
        "bool",
        "list",
        "dict",
        "set",
        "tuple",
        "bytes",
        "bytearray",
        "complex",
        # Iteration / collection
        "len",
        "range",
        "enumerate",
        "zip",
        "map",
        "filter",
        "sorted",
        "reversed",
        "iter",
        "next",
        # Aggregation
        "sum",
        "min",
        "max",
        "abs",
        "round",
        "any",
        "all",
        # Exception classes
        "Exception",
        "ValueError",
        "TypeError",
        "KeyError",
        "IndexError",
        "AttributeError",
        "RuntimeError",
        # Keywords that may appear as identifiers in tree-sitter
        "if",
        "else",
        "elif",
        "for",
        "while",
        "return",
        "def",
        "class",
        "in",
        "not",
        "and",
        "or",
        "is",
        "None",
        "True",
        "False",
        "pass",
        "break",
        "continue",
        "import",
        "from",
        "with",
        "as",
        "try",
        "except",
        "finally",
        "raise",
        "yield",
        "lambda",
        "assert",
        "del",
        "global",
        "nonlocal",
        "async",
        "await",
    }
    comment_markers = {"#"}


class CProfile(LanguageProfile):
    """C language profile."""

    language_code = "c"
    function_node_types = ("function_definition",)
    class_node_types = ("struct_specifier",)
    builtin_names = {
        "void",
        "NULL",
        "size_t",
        "int",
        "char",
        "float",
        "double",
        "long",
        "short",
        "signed",
        "unsigned",
        "struct",
        "union",
        "enum",
        "typedef",
        "static",
        "extern",
        "const",
        "volatile",
        "register",
        "if",
        "else",
        "for",
        "while",
        "do",
        "switch",
        "case",
        "default",
        "break",
        "continue",
        "return",
        "goto",
        "sizeof",
        "include",
        "define",
        "undef",
        "ifdef",
        "ifndef",
        "endif",
        "pragma",
    }
    comment_markers = {"/"}  # // comments


class CppProfile(LanguageProfile):
    """C++ language profile (superset of C)."""

    language_code = "cpp"
    function_node_types = ("function_definition",)
    class_node_types = ("class_specifier", "struct_specifier")
    builtin_names = CProfile.builtin_names | {
        # C++ specific
        "class",
        "namespace",
        "template",
        "typename",
        "new",
        "delete",
        "this",
        "friend",
        "virtual",
        "override",
        "final",
        "constexpr",
        "noexcept",
        "throw",
        "try",
        "catch",
        "private",
        "protected",
        "public",
        "using",
        "operator",
        "explicit",
        "mutable",
        "std",
        "cout",
        "cin",
        "endl",
        # STL containers and types
        "vector",
        "map",
        "set",
        "unordered_map",
        "unordered_set",
        "list",
        "deque",
        "array",
        "string",
        "pair",
        "tuple",
        "optional",
        "variant",
        "any",
        "function",
        "unique_ptr",
        "shared_ptr",
    }
    comment_markers = {"/"}


class JavaProfile(LanguageProfile):
    """Java language profile."""

    language_code = "java"
    function_node_types = ("method_declaration", "constructor_declaration")
    class_node_types = ("class_declaration", "interface_declaration")
    builtin_names = {
        # Primitives and common classes
        "int",
        "long",
        "short",
        "byte",
        "float",
        "double",
        "char",
        "boolean",
        "void",
        "null",
        "true",
        "false",
        "String",
        "Object",
        "Class",
        "System",
        "Math",
        "Integer",
        "Long",
        "Double",
        "Float",
        "Boolean",
        "List",
        "Map",
        "Set",
        "ArrayList",
        "HashMap",
        "HashSet",
        "LinkedList",
        "TreeMap",
        "TreeSet",
        # Modifiers
        "public",
        "private",
        "protected",
        "static",
        "final",
        "abstract",
        "synchronized",
        "volatile",
        "transient",
        # Keywords
        "if",
        "else",
        "for",
        "while",
        "do",
        "switch",
        "case",
        "default",
        "break",
        "continue",
        "return",
        "try",
        "catch",
        "finally",
        "throw",
        "throws",
        "new",
        "instanceof",
        "extends",
        "implements",
        "interface",
        "class",
        "package",
        "import",
        "super",
        "this",
        # Common methods
        "main",
        "toString",
        "equals",
        "hashCode",
        "getClass",
        "notify",
        "wait",
        "clone",
    }
    comment_markers = {"/"}


class JavaScriptProfile(LanguageProfile):
    """JavaScript language profile."""

    language_code = "javascript"
    function_node_types = ("function_declaration", "arrow_function", "method_definition")
    class_node_types = ("class_declaration",)
    builtin_names = {
        # Global objects
        "Object",
        "Array",
        "String",
        "Number",
        "Boolean",
        "Function",
        "Promise",
        "Set",
        "Map",
        "WeakMap",
        "WeakSet",
        "JSON",
        "Math",
        "Date",
        "RegExp",
        "Error",
        "TypeError",
        "SyntaxError",
        "ReferenceError",
        # Built-in functions
        "console",
        "log",
        "warn",
        "error",
        "parseInt",
        "parseFloat",
        "isNaN",
        "isFinite",
        "eval",
        "setTimeout",
        "setInterval",
        "clearTimeout",
        "clearInterval",
        "requestAnimationFrame",
        # Keywords and operators
        "var",
        "let",
        "const",
        "function",
        "class",
        "if",
        "else",
        "for",
        "while",
        "do",
        "switch",
        "case",
        "default",
        "break",
        "continue",
        "return",
        "try",
        "catch",
        "finally",
        "throw",
        "new",
        "delete",
        "typeof",
        "instanceof",
        "in",
        "of",
        "void",
        "yield",
        "await",
        "async",
        "this",
        "super",
        "null",
        "undefined",
        "true",
        "false",
        "NaN",
        "Infinity",
        # Common array methods
        "push",
        "pop",
        "shift",
        "unshift",
        "slice",
        "splice",
        "concat",
        "join",
        "map",
        "filter",
        "reduce",
        "forEach",
        "some",
        "every",
        "find",
        "findIndex",
        "includes",
        "indexOf",
        "lastIndexOf",
    }
    comment_markers = {"/"}


class TypeScriptProfile(JavaScriptProfile):
    """TypeScript language profile (extends JavaScript)."""

    language_code = "typescript"
    function_node_types = ("function_declaration", "arrow_function", "method_definition")
    class_node_types = ("class_declaration", "interface_declaration", "type_alias_declaration")
    builtin_names = JavaScriptProfile.builtin_names | {
        # TypeScript specific
        "any",
        "unknown",
        "never",
        "void",
        "boolean",
        "number",
        "string",
        "symbol",
        "bigint",
        "type",
        "interface",
        "enum",
        "namespace",
        "module",
        "declare",
        "abstract",
        "readonly",
        "as",
        " satisfies ",
        "keyof",
        "typeof",
        "instanceof",
        "is",
        "asserts",
        "assert",
        "Partial",
        "Required",
        "Readonly",
        "Record",
        "Pick",
        "Omit",
        "Exclude",
        "Extract",
        "NonNullable",
        "Parameters",
        "ReturnType",
        "ConstructorParameters",
        "ThisParameterType",
        "OmitThisParameter",
    }
    comment_markers = {"/"}


class TSXProfile(TypeScriptProfile):
    """TSX language profile (TypeScript with JSX)."""

    language_code = "tsx"
    function_node_types = ("function_declaration", "arrow_function", "method_definition")
    class_node_types = ("class_declaration", "interface_declaration")
    # TSX uses same builtins as TypeScript
    builtin_names = TypeScriptProfile.builtin_names
    comment_markers = {"/"}


class GoProfile(LanguageProfile):
    """Go language profile."""

    language_code = "go"
    function_node_types = ("function_declaration", "method_declaration")
    class_node_types = ("type_declaration",)  # struct, interface, type aliases
    builtin_names = {
        # Built-in types
        "bool",
        "byte",
        "complex64",
        "complex128",
        "float32",
        "float64",
        "int",
        "int8",
        "int16",
        "int32",
        "int64",
        "rune",
        "string",
        "uint",
        "uint8",
        "uint16",
        "uint32",
        "uint64",
        "uintptr",
        "error",
        # Built-in functions
        "append",
        "cap",
        "close",
        "complex",
        "copy",
        "delete",
        "imag",
        "len",
        "make",
        "new",
        "panic",
        "print",
        "println",
        "real",
        "recover",
        "clear",
        "min",
        "max",
        "abs",
        # Zero values
        "nil",
        "true",
        "false",
        # Keywords and declarations
        "var",
        "const",
        "func",
        "type",
        "struct",
        "interface",
        "map",
        "chan",
        "slice",
        "array",
        "if",
        "else",
        "for",
        "range",
        "switch",
        "case",
        "default",
        "break",
        "continue",
        "goto",
        "return",
        "defer",
        "go",
        "package",
        "import",
        "select",
        # Common interfaces and types
        "io",
        "fmt",
        "os",
        "bufio",
        "bytes",
        "strings",
        "strconv",
        "time",
        "context",
        "sync",
        "atomic",
        "http",
        "json",
        "xml",
        "html",
        "database",
        "sql",
        "testing",
        "ioutil",
        "log",
    }
    comment_markers = {"/"}


class RustProfile(LanguageProfile):
    """Rust language profile."""

    language_code = "rust"
    function_node_types = ("function_item",)
    class_node_types = ("struct_item", "enum_item", "trait_item", "impl_item")
    builtin_names = {
        # Primitives
        "bool",
        "i8",
        "i16",
        "i32",
        "i64",
        "i128",
        "isize",
        "u8",
        "u16",
        "u32",
        "u64",
        "u128",
        "usize",
        "f32",
        "f64",
        "char",
        "str",
        "String",
        "tuple",
        "array",
        "slice",
        "Vec",
        "Option",
        "Result",
        # Keywords
        "fn",
        "pub",
        "priv",
        "crate",
        "super",
        "self",
        "Self",
        "struct",
        "enum",
        "union",
        "trait",
        "impl",
        "type",
        "const",
        "static",
        "async",
        "await",
        "move",
        "clone",
        "copy",
        "send",
        "sync",
        "Sized",
        "unsafe",
        "if",
        "else",
        "match",
        "for",
        "while",
        "loop",
        "break",
        "continue",
        "return",
        "yield",
        "let",
        "mut",
        "ref",
        "mut ref",
        "in",
        "as",
        "dyn",
        "extern",
        "use",
        "mod",
        "where",
        "true",
        "false",
        "nil",
        "Some",
        "None",
        "Ok",
        "Err",
        # Common macros and attributes
        "println",
        "print",
        "eprintln",
        "eprint",
        "format",
        "panic",
        "assert",
        "debug_assert",
        "todo",
        "vec",
        "Box",
        "Rc",
        "Arc",
        "Cell",
        "RefCell",
        "Mutex",
        "RwLock",
        "HashMap",
        "HashSet",
        "BTreeMap",
        "Deref",
        "Drop",
        "Fn",
        "FnOnce",
        "FnMut",
    }
    comment_markers = {"/"}


# Registry for auto-discovery and instantiation of profiles
_language_registry: dict[str, type[LanguageProfile]] = {}


def register_language_profile(profile_class: type[LanguageProfile]) -> None:
    """Register a language profile in the global registry."""
    _language_registry[profile_class.language_code] = profile_class


# Auto-register all concrete profiles
for _profile_class in [
    PythonProfile,
    CProfile,
    CppProfile,
    JavaProfile,
    JavaScriptProfile,
    TypeScriptProfile,
    TSXProfile,
    GoProfile,
    RustProfile,
]:
    register_language_profile(_profile_class)


def get_language_profile(lang_code: str) -> LanguageProfile:
    """Get language profile for given language code."""
    if lang_code not in _language_registry:
        raise ValueError(
            f"Unsupported language: {lang_code}. Supported: {list(_language_registry.keys())}"
        )
    return _language_registry[lang_code]()


def get_supported_languages() -> list[str]:
    """Get list of supported language codes."""
    return list(_language_registry.keys())
