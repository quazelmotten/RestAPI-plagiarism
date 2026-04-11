"""
Unit tests for results repository normalization functions.
"""

import pytest


class TestNormalizeMatches:
    """Tests for _normalize_matches function."""

    def test_normalize_none_returns_empty_list(self):
        """Verify None returns empty list."""
        from results.repository import _normalize_matches

        result = _normalize_matches(None)
        assert result == []

    def test_normalize_valid_list_returns_same(self):
        """Verify valid list returns unchanged."""
        from results.repository import _normalize_matches

        test_list = [{"file1": {"start_line": 1}}]
        result = _normalize_matches(test_list)
        assert result == test_list

    def test_normalize_empty_string_returns_empty_list(self):
        """Verify empty string returns empty list."""
        from results.repository import _normalize_matches

        result = _normalize_matches("")
        assert result == []

    def test_normalize_empty_json_string_returns_empty_list(self):
        """Verify '[]' string returns empty list."""
        from results.repository import _normalize_matches

        result = _normalize_matches("[]")
        assert result == []

    def test_normalize_string_array_returns_list(self):
        """Verify JSON string array returns parsed list."""
        from results.repository import _normalize_matches

        result = _normalize_matches('[{"file1": {"start_line": 1}}]')
        assert result == [{"file1": {"start_line": 1}}]

    def test_normalize_invalid_string_returns_empty_list(self):
        """Verify invalid JSON string returns empty list to prevent crashes."""
        from results.repository import _normalize_matches

        result = _normalize_matches("{invalid}")
        assert result == []

    def test_normalize_object_string_returns_empty_list(self):
        """Verify object (not array) string returns empty list."""
        from results.repository import _normalize_matches

        result = _normalize_matches('{"key": "value"}')
        assert result == []


class TestNormalizeMatchesEdgeCases:
    """Edge case tests for _normalize_matches."""

    def test_normalize_whitespace_returns_empty_list(self):
        """Verify whitespace string returns empty list."""
        from results.repository import _normalize_matches

        result = _normalize_matches("   ")
        assert result == []

    def test_normalize_numeric_returns_empty_list(self):
        """Verify numeric value returns empty list."""
        from results.repository import _normalize_matches

        result = _normalize_matches(123)
        assert result == []

    def test_normalize_boolean_returns_empty_list(self):
        """Verify boolean value returns empty list."""
        from results.repository import _normalize_matches

        result = _normalize_matches(True)
        assert result == []


class TestResultItemSchema:
    """Tests for ResultItem schema validation."""

    def test_result_item_accepts_list_matches(self):
        """Verify ResultItem accepts list for matches field."""
        from results.schemas import ResultItem

        item = ResultItem(
            file_a={"id": "1", "filename": "a.py"},
            file_b={"id": "2", "filename": "b.py"},
            matches=[
                {
                    "file1": {"start_line": 1, "start_col": 0, "end_line": 5, "end_col": 10},
                    "file2": {"start_line": 1, "start_col": 0, "end_line": 5, "end_col": 10},
                    "kgram_count": 3,
                }
            ],
        )
        assert len(item.matches) == 1

    def test_result_item_accepts_none_matches(self):
        """Verify ResultItem accepts None for matches field."""
        from results.schemas import ResultItem

        item = ResultItem(
            file_a={"id": "1", "filename": "a.py"},
            file_b={"id": "2", "filename": "b.py"},
            matches=None,
        )
        assert item.matches is None

    def test_result_item_accepts_empty_list_matches(self):
        """Verify ResultItem accepts empty list for matches field."""
        from results.schemas import ResultItem

        item = ResultItem(
            file_a={"id": "1", "filename": "a.py"},
            file_b={"id": "2", "filename": "b.py"},
            matches=[],
        )
        assert item.matches == []

    def test_result_item_rejects_string_matches(self):
        """Verify ResultItem rejects string for matches (catches bad data)."""
        from pydantic import ValidationError

        from results.schemas import ResultItem

        with pytest.raises(ValidationError):
            ResultItem(
                file_a={"id": "1", "filename": "a.py"},
                file_b={"id": "2", "filename": "b.py"},
                matches="[]",
            )


class TestNoPydanticValidationErrors:
    """Integration-style tests to ensure no Pydantic validation errors in production."""

    def test_matches_field_type_enforced(self):
        """Verify matches field enforces list type at schema level."""
        from pydantic import ValidationError

        from results.schemas import ResultItem

        invalid_inputs = [
            "[]",
            "[{}]",
            '{"key": "value"}',
            "invalid",
        ]

        for invalid in invalid_inputs:
            with pytest.raises(ValidationError):
                ResultItem(
                    file_a={"id": "1", "filename": "a.py"},
                    file_b={"id": "2", "filename": "b.py"},
                    matches=invalid,
                )
