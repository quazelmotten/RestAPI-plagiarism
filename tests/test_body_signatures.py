"""Tests for plagiarism_core.detection.body_signatures module."""

import pytest
from plagiarism_core.canonicalizer import parse_file_once_from_string
from plagiarism_core.detection.body_signatures import (
    _extract_body_signature,
    _extract_comprehension_pattern,
    _extract_conditional_assign_signature,
    _extract_lbyl_signature,
    _extract_loop_append_pattern,
    _extract_map_lambda_parts,
    _extract_nested_if_signature,
    _extract_return_chain_signature,
    _extract_return_value,
    _extract_ternary_signature,
    _extract_try_signature,
    _extract_tuple_return_signature,
)


class TestExtractComprehensionPattern:
    def test_loop_append(self):
        source = (
            "def foo():\n"
            "    result = []\n"
            "    for x in items:\n"
            "        result.append(x)\n"
            "    return result\n"
        )
        result = _extract_comprehension_pattern(source, "python")
        assert result is not None
        assert result["pattern"] == "loop_append"

    def test_non_python(self):
        source = "def foo():\n    return [x for x in items]\n"
        result = _extract_comprehension_pattern(source, "cpp")
        assert result is None

    def test_no_match(self):
        source = "def foo():\n    return 42\n"
        result = _extract_comprehension_pattern(source, "python")
        assert result is None


class TestExtractLoopAppendPattern:
    def test_basic_loop_append(self):
        source = "for x in items:\n    result.append(x)\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        root = tree.root_node
        for_stmts = [c for c in root.children if c.type == "for_statement"]
        if for_stmts:
            result = _extract_loop_append_pattern(for_stmts[0], "result", source_bytes)
            assert result is not None
            assert result["pattern"] == "loop_append"

    def test_loop_append_with_filter(self):
        source = "for x in items:\n    if x > 0:\n        result.append(x)\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        root = tree.root_node
        for_stmts = [c for c in root.children if c.type == "for_statement"]
        if for_stmts:
            result = _extract_loop_append_pattern(for_stmts[0], "result", source_bytes)
            assert result is not None


class TestExtractReturnValue:
    def test_single_return(self):
        source = "return 42\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        result = _extract_return_value(tree.root_node, source_bytes)
        assert result == "42"

    def test_no_return(self):
        source = "x = 1\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        result = _extract_return_value(tree.root_node, source_bytes)
        assert result is None


class TestExtractMapLambdaParts:
    def test_map_lambda_returns_none_for_lambda_parameters(self):
        source = "list(map(lambda x: x * 2, items))\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        root = tree.root_node

        def find_call(node, name):
            if node.type == "call":
                for c in node.children:
                    if c.type == "identifier":
                        txt = source_bytes[c.start_byte : c.end_byte].decode(
                            "utf-8", errors="ignore"
                        )
                        if txt == name:
                            return node
            for c in node.children:
                result = find_call(c, name)
                if result:
                    return result
            return None

        map_call = find_call(root, "map")
        if map_call:
            result = _extract_map_lambda_parts(map_call, source_bytes)
            assert result is None


class TestExtractConditionalAssignSignature:
    def test_if_else_assign_return(self):
        source = "if cond:\n    x = 1\nelse:\n    x = 2\nreturn x\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        stmts = [c for c in tree.root_node.children if c.type not in ("comment", "NEWLINE", "")]
        result = _extract_conditional_assign_signature(stmts, source_bytes)
        assert result is not None
        assert "COND_ASSIGN" in result


class TestExtractNestedIfSignature:
    def test_nested_if_return(self):
        source = "if cond1:\n    if cond2:\n        return True\nreturn False\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        stmts = [c for c in tree.root_node.children if c.type not in ("comment", "NEWLINE", "")]
        result = _extract_nested_if_signature(stmts, source_bytes)
        assert result is not None
        assert "BOOL_CHECK" in result


class TestExtractTupleReturnSignature:
    def test_single_return_tuple(self):
        source = "return (a, b)\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        stmts = [c for c in tree.root_node.children if c.type not in ("comment", "NEWLINE", "")]
        result = _extract_tuple_return_signature(stmts, source_bytes)
        assert result is not None
        assert "RETURNS_TUPLE" in result

    def test_assignments_then_return_tuple(self):
        source = "a = 1\nb = 2\nreturn (a, b)\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        stmts = [c for c in tree.root_node.children if c.type not in ("comment", "NEWLINE", "")]
        result = _extract_tuple_return_signature(stmts, source_bytes)
        assert result is not None
        assert "RETURNS_TUPLE" in result


class TestExtractReturnChainSignature:
    def test_if_elif_else_chain(self):
        source = "if cond1:\n    return 1\nelif cond2:\n    return 2\nelse:\n    return 3\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        root = tree.root_node
        if_stmt = [c for c in root.children if c.type == "if_statement"][0]
        result = _extract_return_chain_signature(if_stmt, source_bytes)
        assert result is not None
        assert "RETURNS" in result


class TestExtractBodySignature:
    def test_if_else_return_chain(self):
        source = (
            "def foo():\n"
            "    if cond1:\n"
            "        return 1\n"
            "    elif cond2:\n"
            "        return 2\n"
            "    else:\n"
            "        return 3\n"
        )
        sig = _extract_body_signature(source, "python")
        assert sig is not None

    def test_lbyl_pattern(self):
        source = "def foo():\n    if x is None:\n        return default\n    return process(x)\n"
        sig = _extract_body_signature(source, "python")
        assert sig is not None

    def test_no_match(self):
        source = "def foo():\n    pass\n"
        sig = _extract_body_signature(source, "python")
        assert sig is None

    def test_invalid_source(self):
        sig = _extract_body_signature("{{{{not valid python", "python")
        assert sig is None

    def test_non_python(self):
        source = "def foo():\n    return 1\n"
        sig = _extract_body_signature(source, "cpp")
        assert sig is None


class TestExtractTernarySignature:
    def test_conditional_expression(self):
        source = "x = a if cond else b\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        root = tree.root_node
        for stmt in root.children:
            if stmt.type == "expression_statement":
                for c in stmt.children:
                    if c.type == "assignment":
                        for sub in c.children:
                            if sub.type == "conditional_expression":
                                result = _extract_ternary_signature(sub, source_bytes)
                                assert result is not None
                                assert "COND_ASSIGN" in result
                                return
        pytest.fail("Could not find conditional expression node")


class TestExtractDictPattern:
    def test_dict_comprehension_returns_none(self):
        source = "def foo():\n    return {k: v for k, v in items}\n"
        sig = _extract_body_signature(source, "python")
        assert sig is None


class TestExtractTrySignature:
    def test_try_except_return(self):
        source = "try:\n    return int(x)\nexcept ValueError:\n    return 0\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        root = tree.root_node
        try_nodes = [c for c in root.children if c.type == "try_statement"]
        if try_nodes:
            result = _extract_try_signature(try_nodes[0], source_bytes)
            assert result is not None
            assert "SAFE_OP" in result


class TestExtractLbylSignature:
    def test_lbyl_pattern(self):
        source = "if x is None:\n    return default\nreturn process(x)\n"
        tree, source_bytes = parse_file_once_from_string(source, "python")
        stmts = [c for c in tree.root_node.children if c.type not in ("comment", "NEWLINE", "")]
        result = _extract_lbyl_signature(stmts, source_bytes)
        assert result is not None
        assert "SAFE_OP" in result
