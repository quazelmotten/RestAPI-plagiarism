"""Tests for plagiarism_core.fingerprinting.winnow module."""

import pytest
from plagiarism_core.fingerprinting.winnow import (
    Fingerprint,
    Winnower,
    compute_kgram_hashes,
)


class TestFingerprint:
    def test_basic(self):
        fp = Fingerprint(hash_value=123, position=5)
        assert fp.hash_value == 123
        assert fp.position == 5
        assert fp.token_count == 1

    def test_custom_token_count(self):
        fp = Fingerprint(hash_value=456, position=10, token_count=3)
        assert fp.token_count == 3

    def test_frozen(self):
        fp = Fingerprint(hash_value=123, position=5)
        with pytest.raises(AttributeError):
            fp.hash_value = 999


class TestWinnower:
    def test_basic(self):
        w = Winnower(window_size=3)
        result = w.winnow([10, 20, 5, 15, 25])
        assert isinstance(result, list)
        assert len(result) > 0

    def test_too_few_hashes(self):
        w = Winnower(window_size=5)
        result = w.winnow([1, 2, 3])
        assert result == []

    def test_window_size_2(self):
        w = Winnower(window_size=2)
        result = w.winnow([5, 3, 8, 1])
        assert isinstance(result, list)
        assert len(result) > 0

    def test_all_same_values(self):
        w = Winnower(window_size=3)
        result = w.winnow([5, 5, 5, 5, 5])
        assert len(result) >= 1
        assert result[0].hash_value == 5

    def test_increasing_values(self):
        w = Winnower(window_size=3)
        result = w.winnow([1, 2, 3, 4, 5, 6])
        assert len(result) > 0
        assert result[0].hash_value == 1

    def test_decreasing_values(self):
        w = Winnower(window_size=3)
        result = w.winnow([6, 5, 4, 3, 2, 1])
        assert len(result) > 0

    def test_default_window_size(self):
        w = Winnower()
        assert w.window_size == 4

    def test_fingerprint_positions(self):
        w = Winnower(window_size=3)
        result = w.winnow([10, 20, 5, 15, 25])
        for fp in result:
            assert isinstance(fp.position, int)
            assert isinstance(fp.hash_value, int)


class TestComputeKgramHashes:
    def test_basic(self):
        from plagiarism_core.fingerprinting.tokenizer import Token

        tokens = [
            Token(type="identifier", value="foo", line=0, col=0),
            Token(type="operator", value="=", line=0, col=4),
            Token(type="integer", value="1", line=0, col=6),
            Token(type="newline", value="\n", line=0, col=7),
        ]
        hashes = compute_kgram_hashes(tokens, k=3)
        assert isinstance(hashes, list)
        assert len(hashes) > 0

    def test_too_few_tokens(self):
        from plagiarism_core.fingerprinting.tokenizer import Token

        tokens = [
            Token(type="identifier", value="foo", line=0, col=0),
        ]
        assert compute_kgram_hashes(tokens, k=3) == []

    def test_k_2(self):
        from plagiarism_core.fingerprinting.tokenizer import Token

        tokens = [
            Token(type="identifier", value="foo", line=0, col=0),
            Token(type="operator", value="=", line=0, col=4),
            Token(type="integer", value="1", line=0, col=6),
        ]
        hashes = compute_kgram_hashes(tokens, k=2)
        assert isinstance(hashes, list)
        assert len(hashes) > 0

    def test_deterministic(self):
        from plagiarism_core.fingerprinting.tokenizer import Token

        tokens = [
            Token(type="identifier", value="foo", line=0, col=0),
            Token(type="operator", value="=", line=0, col=4),
            Token(type="integer", value="1", line=0, col=6),
            Token(type="newline", value="\n", line=0, col=7),
        ]
        h1 = compute_kgram_hashes(tokens, k=3)
        h2 = compute_kgram_hashes(tokens, k=3)
        assert h1 == h2

    def test_different_tokens_different_hashes(self):
        from plagiarism_core.fingerprinting.tokenizer import Token

        tokens1 = [
            Token(type="identifier", value="foo", line=0, col=0),
            Token(type="operator", value="=", line=0, col=4),
            Token(type="integer", value="1", line=0, col=6),
            Token(type="newline", value="\n", line=0, col=7),
        ]
        tokens2 = [
            Token(type="identifier", value="bar", line=0, col=0),
            Token(type="operator", value="=", line=0, col=4),
            Token(type="integer", value="2", line=0, col=6),
            Token(type="newline", value="\n", line=0, col=7),
        ]
        h1 = compute_kgram_hashes(tokens1, k=3)
        h2 = compute_kgram_hashes(tokens2, k=3)
        assert h1 != h2

    def test_with_plain_objects(self):
        class FakeToken:
            def __init__(self, val):
                self.val = val

            def __str__(self):
                return self.val

        tokens = [FakeToken("a"), FakeToken("b"), FakeToken("c")]
        hashes = compute_kgram_hashes(tokens, k=3)
        assert isinstance(hashes, list)
        assert len(hashes) > 0
