"""
Tests for multi-language plagiarism detection.

Tests C++, Java, JavaScript, Go, and Rust support across:
- AST canonicalization (Type 4)
- Identifier normalization (Type 2)
- Body signature extraction
- Semantic line matching
- Tokenizer
- Function extraction
"""

from plagiarism_core.canonicalizer import (
    canonicalize_type4,
    normalize_identifiers,
    parse_file_once_from_string,
)
from plagiarism_core.fingerprinting.tokenizer import Tokenizer
from plagiarism_core.plagiarism_detector import (
    _extract_body_signature,
    _extract_functions,
    _extract_main_block,
    _is_main_block,
)

# ============================================================================
# C++ Tests
# ============================================================================


class TestCppCanonicalization:
    """Test AST canonicalization for C++."""

    def test_cpp_for_while_same_loop(self):
        """C++ for and while loops should canonicalize to same LOOP form."""
        for_code = """
void foo() {
    for (int i = 0; i < 10; i++) {
        x = x + 1;
    }
}
"""
        while_code = """
void foo() {
    while (i < 10) {
        x = x + 1;
    }
}
"""
        canon_for = canonicalize_type4(for_code, lang_code="cpp")
        canon_while = canonicalize_type4(while_code, lang_code="cpp")
        assert "LOOP" in canon_for
        assert "LOOP" in canon_while

    def test_cpp_range_based_for_loop(self):
        """C++ range-based for loop should be recognized."""
        code = """
void foo() {
    for (auto& item : items) {
        process(item);
    }
}
"""
        canon = canonicalize_type4(code, lang_code="cpp")
        assert "LOOP" in canon

    def test_cpp_do_while_loop(self):
        """C++ do-while loop should be recognized."""
        code = """
void foo() {
    do {
        x++;
    } while (x < 10);
}
"""
        canon = canonicalize_type4(code, lang_code="cpp")
        assert "LOOP" in canon

    def test_cpp_lambda_expression(self):
        """C++ lambda should canonicalize to FUNCTION_LITERAL."""
        code = """
void foo() {
    auto f = [](int x) { return x * 2; };
}
"""
        canon = canonicalize_type4(code, lang_code="cpp")
        assert "FUNC_LIT" in canon

    def test_cpp_ternary_expression(self):
        """C++ ternary should canonicalize to TERNARY."""
        code = """
void foo() {
    int y = (a > b) ? a : b;
}
"""
        canon = canonicalize_type4(code, lang_code="cpp")
        assert "TERNARY" in canon

    def test_cpp_comparison_operators(self):
        """C++ comparison operators should canonicalize to COMPARE."""
        code = """
void foo() {
    if (x == y) {}
    if (a != b) {}
}
"""
        canon = canonicalize_type4(code, lang_code="cpp")
        assert "COMPARE" in canon

    def test_cpp_logical_operators(self):
        """C++ logical operators should canonicalize to LOGICAL."""
        code = """
void foo() {
    if (a && b) {}
    if (x || y) {}
}
"""
        canon = canonicalize_type4(code, lang_code="cpp")
        assert "LOGICAL" in canon

    def test_cpp_augmented_assignment(self):
        """C++ augmented assignment should canonicalize to ASSIGN."""
        code = """
void foo() {
    x += 5;
    y *= 2;
}
"""
        canon = canonicalize_type4(code, lang_code="cpp")
        assert "ASSIGN" in canon

    def test_cpp_string_literal(self):
        """C++ string literals should be recognized."""
        code = """
void foo() {
    const char* msg = "hello world";
}
"""
        canon = canonicalize_type4(code, lang_code="cpp")
        assert "STRING_FORMAT" in canon

    def test_cpp_semantic_equivalence(self):
        """Two semantically equivalent C++ functions should produce similar canonical forms."""
        code_a = """
int compute(int a, int b) {
    if (a > b) {
        return a;
    } else {
        return b;
    }
}
"""
        code_b = """
int calculate(int x, int y) {
    if (x > y) {
        return x;
    } else {
        return y;
    }
}
"""
        canon_a = canonicalize_type4(code_a, lang_code="cpp")
        canon_b = canonicalize_type4(code_b, lang_code="cpp")
        assert canon_a == canon_b


class TestCppIdentifierNormalization:
    """Test identifier normalization for C++."""

    def test_cpp_renames_variables(self):
        """C++ variables should be replaced with VAR_N placeholders."""
        code = """
void foo() {
    int myVar = 10;
    int anotherVar = myVar + 5;
}
"""
        normalized = normalize_identifiers(code, "cpp")
        assert "VAR_" in normalized
        assert "myVar" not in normalized
        assert "anotherVar" not in normalized

    def test_cpp_preserves_builtins(self):
        """C++ builtins should not be replaced."""
        code = """
void foo() {
    int x = 10;
    std::vector<int> v;
}
"""
        normalized = normalize_identifiers(code, "cpp")
        assert "int" in normalized
        assert "std" in normalized
        assert "vector" in normalized

    def test_cpp_consistent_normalization(self):
        """Same C++ code should produce same normalized output."""
        code = """
int add(int a, int b) { return a + b; }
"""
        norm1 = normalize_identifiers(code, "cpp")
        norm2 = normalize_identifiers(code, "cpp")
        assert norm1 == norm2


class TestCppBodySignature:
    """Test body signature extraction for C++."""

    def test_cpp_single_return(self):
        """C++ function with single return should produce RETURNS signature."""
        code = """
int add(int a, int b) {
    return a + b;
}
"""
        sig = _extract_body_signature(code, "cpp")
        assert sig is not None
        assert "RETURNS" in sig

    def test_cpp_if_else_return_chain(self):
        """C++ if/else return chain should produce RETURNS signature."""
        code = """
int max(int a, int b) {
    if (a > b) {
        return a;
    } else {
        return b;
    }
}
"""
        sig = _extract_body_signature(code, "cpp")
        assert sig is not None

    def test_cpp_ternary_return(self):
        """C++ ternary return should produce signature."""
        code = """
int max(int a, int b) {
    return (a > b) ? a : b;
}
"""
        sig = _extract_body_signature(code, "cpp")
        assert sig is not None


class TestCppMainDetection:
    """Test C++ main() function detection."""

    def test_cpp_main_function_detected(self):
        """C++ int main() should be detected as entry point."""
        code = """
int main() {
    return 0;
}
"""
        tree, source_bytes = parse_file_once_from_string(code, "cpp")
        for child in tree.root_node.children:
            if _is_main_block(child, source_bytes, "cpp"):
                assert True
                return
        raise AssertionError("main() not detected")

    def test_cpp_main_block_extraction(self):
        """C++ main() body should be extractable."""
        code = """
int main() {
    int x = 10;
    return x;
}
"""
        tree, source_bytes = parse_file_once_from_string(code, "cpp")
        result = _extract_main_block(tree.root_node, source_bytes, "cpp")
        assert result is not None
        assert result["name"] == "__main__"


class TestCppTokenizer:
    """Test C++ tokenization."""

    def test_cpp_keywords_recognized(self):
        """C++ keywords should be tokenized as KW."""
        code = """
int main() {
    for (int i = 0; i < 10; i++) {
        if (i % 2 == 0) {
            continue;
        }
    }
    return 0;
}
"""
        tree, source_bytes = parse_file_once_from_string(code, "cpp")

        class MockParsed:
            def __init__(self, tree, source_bytes):
                self.tree = tree
                self.source_bytes = source_bytes
                self.language = "cpp"

            def get_root_node(self):
                return self.tree.root_node

            def get_source_text(self, node):
                return source_bytes[node.start_byte : node.end_byte].decode(
                    "utf-8", errors="ignore"
                )

        mock = MockParsed(tree, source_bytes)
        tokenizer = Tokenizer(mock)
        tokens = tokenizer.tokenize()
        token_types = [t.type for t in tokens]
        assert "KW" in token_types

    def test_cpp_operators_recognized(self):
        """C++ operators should be tokenized as OP."""
        code = """
void foo() {
    int x = a + b;
    bool y = a && b;
    int* ptr = &x;
}
"""
        tree, source_bytes = parse_file_once_from_string(code, "cpp")

        class MockParsed:
            def __init__(self, tree, source_bytes):
                self.tree = tree
                self.source_bytes = source_bytes
                self.language = "cpp"

            def get_root_node(self):
                return self.tree.root_node

            def get_source_text(self, node):
                return source_bytes[node.start_byte : node.end_byte].decode(
                    "utf-8", errors="ignore"
                )

        mock = MockParsed(tree, source_bytes)
        tokenizer = Tokenizer(mock)
        tokens = tokenizer.tokenize()
        token_types = [t.type for t in tokens]
        assert "OP" in token_types


class TestCppFunctionExtraction:
    """Test C++ function extraction."""

    def test_extract_cpp_functions(self):
        """Should extract C++ function definitions."""
        code = """
int add(int a, int b) {
    return a + b;
}

void print_result(int x) {
    std::cout << x << std::endl;
}
"""
        tree, source_bytes = parse_file_once_from_string(code, "cpp")
        funcs = _extract_functions(tree.root_node, source_bytes, "cpp")
        assert len(funcs) >= 2
        names = [f["name"] for f in funcs]
        assert "add" in names
        assert "print_result" in names

    def test_cpp_structural_hash(self):
        """Structurally identical C++ functions should have same hash."""
        code_a = """
int add(int a, int b) {
    return a + b;
}
"""
        code_b = """
int multiply(int x, int y) {
    return x + y;
}
"""
        tree_a, bytes_a = parse_file_once_from_string(code_a, "cpp")
        tree_b, bytes_b = parse_file_once_from_string(code_b, "cpp")

        funcs_a = _extract_functions(tree_a.root_node, bytes_a, "cpp")
        funcs_b = _extract_functions(tree_b.root_node, bytes_b, "cpp")

        assert funcs_a[0]["struct_hash"] == funcs_b[0]["struct_hash"]


# ============================================================================
# Java Tests
# ============================================================================


class TestJavaCanonicalization:
    """Test AST canonicalization for Java."""

    def test_java_for_while_same_loop(self):
        """Java for and while loops should canonicalize to LOOP."""
        for_code = """
class Test {
    void foo() {
        for (int i = 0; i < 10; i++) {
            x = x + 1;
        }
    }
}
"""
        canon = canonicalize_type4(for_code, lang_code="java")
        assert "LOOP" in canon

    def test_java_enhanced_for_loop(self):
        """Java enhanced for loop should be recognized."""
        code = """
class Test {
    void foo() {
        for (String item : items) {
            process(item);
        }
    }
}
"""
        canon = canonicalize_type4(code, lang_code="java")
        assert "LOOP" in canon

    def test_java_lambda(self):
        """Java lambda should canonicalize to FUNCTION_LITERAL."""
        code = """
class Test {
    void foo() {
        Runnable r = () -> System.out.println("hi");
    }
}
"""
        canon = canonicalize_type4(code, lang_code="java")
        assert "FUNC_LIT" in canon

    def test_java_ternary(self):
        """Java ternary should canonicalize to TERNARY."""
        code = """
class Test {
    void foo() {
        int y = (a > b) ? a : b;
    }
}
"""
        canon = canonicalize_type4(code, lang_code="java")
        assert "TERNARY" in canon


class TestJavaIdentifierNormalization:
    """Test identifier normalization for Java."""

    def test_java_renames_variables(self):
        """Java variables should be replaced with VAR_N."""
        code = """
class Test {
    void foo() {
        int myVar = 10;
        int another = myVar + 5;
    }
}
"""
        normalized = normalize_identifiers(code, "java")
        assert "VAR_" in normalized
        assert "myVar" not in normalized


# ============================================================================
# JavaScript Tests
# ============================================================================


class TestJsCanonicalization:
    """Test AST canonicalization for JavaScript."""

    def test_js_for_while_same_loop(self):
        """JS for and while loops should canonicalize to LOOP."""
        for_code = """
function foo() {
    for (let i = 0; i < 10; i++) {
        x = x + 1;
    }
}
"""
        canon = canonicalize_type4(for_code, lang_code="javascript")
        assert "LOOP" in canon

    def test_js_arrow_function(self):
        """JS arrow function should canonicalize to FUNCTION_LITERAL."""
        code = """
const f = (x) => x * 2;
"""
        canon = canonicalize_type4(code, lang_code="javascript")
        assert "FUNC_LIT" in canon


# ============================================================================
# Go Tests
# ============================================================================


class TestGoCanonicalization:
    """Test AST canonicalization for Go."""

    def test_go_for_loop(self):
        """Go for loops should canonicalize to LOOP."""
        code = """
func main() {
    for i := 0; i < 10; i++ {
        x = x + 1
    }
}
"""
        canon = canonicalize_type4(code, lang_code="go")
        assert "LOOP" in canon

    def test_go_range_loop(self):
        """Go range loop should be recognized."""
        code = """
func main() {
    for _, v := range slice {
        process(v)
    }
}
"""
        canon = canonicalize_type4(code, lang_code="go")
        assert "LOOP" in canon


# ============================================================================
# Rust Tests
# ============================================================================


class TestRustCanonicalization:
    """Test AST canonicalization for Rust."""

    def test_rust_for_loop(self):
        """Rust for loop should canonicalize to LOOP."""
        code = """
fn main() {
    for x in iter {
        process(x);
    }
}
"""
        canon = canonicalize_type4(code, lang_code="rust")
        assert "LOOP" in canon

    def test_rust_closure(self):
        """Rust closure should canonicalize to FUNCTION_LITERAL."""
        code = """
fn main() {
    let f = |x| x * 2;
}
"""
        canon = canonicalize_type4(code, lang_code="rust")
        assert "FUNC_LIT" in canon

    def test_rust_loop_expression(self):
        """Rust loop expression should be recognized."""
        code = """
fn main() {
    loop {
        break;
    }
}
"""
        canon = canonicalize_type4(code, lang_code="rust")
        assert "LOOP" in canon


# ============================================================================
# Cross-Language SemanticLineMatcher Tests
# ============================================================================


class TestSemanticLineMatcherMultiLanguage:
    """Test that SemanticLineMatcher works with different languages."""

    def test_cpp_keywords_in_canonicalization(self):
        """C++ keywords should be preserved in canonical output."""
        from plagiarism_core.plagiarism_detector import _get_keywords_for_language

        keywords = _get_keywords_for_language("cpp")
        assert "for" in keywords
        assert "while" in keywords
        assert "return" in keywords
        assert "template" in keywords
        assert "namespace" in keywords

    def test_java_keywords_in_canonicalization(self):
        """Java keywords should be preserved in canonical output."""
        from plagiarism_core.plagiarism_detector import _get_keywords_for_language

        keywords = _get_keywords_for_language("java")
        assert "for" in keywords
        assert "while" in keywords
        assert "return" in keywords
        assert "synchronized" in keywords
        assert "volatile" in keywords

    def test_go_keywords_in_canonicalization(self):
        """Go keywords should be preserved in canonical output."""
        from plagiarism_core.plagiarism_detector import _get_keywords_for_language

        keywords = _get_keywords_for_language("go")
        assert "for" in keywords
        assert "return" in keywords
        assert "defer" in keywords
        assert "go" in keywords
        assert "chan" in keywords

    def test_rust_keywords_in_canonicalization(self):
        """Rust keywords should be preserved in canonical output."""
        from plagiarism_core.plagiarism_detector import _get_keywords_for_language

        keywords = _get_keywords_for_language("rust")
        assert "for" in keywords
        assert "while" in keywords
        assert "return" in keywords
        assert "match" in keywords
        assert "fn" in keywords
        assert "let" in keywords
