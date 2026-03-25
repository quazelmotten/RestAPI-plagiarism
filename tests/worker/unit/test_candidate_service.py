"""
Unit tests for CandidateService.
Tests candidate pair generation (intra-task and cross-task).
"""

import pytest
from unittest.mock import MagicMock
from worker.services.candidate_service import CandidateService
from shared.interfaces import CandidateIndex


class TestCandidateService:
    """Test candidate service operations."""

    @pytest.fixture
    def mock_index(self):
        """Mock CandidateIndex (inverted index)."""
        idx = MagicMock(spec=CandidateIndex)
        idx.get_file_fingerprints = MagicMock()
        idx.get_file_fingerprints_batch = MagicMock(return_value={})
        idx.find_candidates = MagicMock(return_value={})
        return idx

    @pytest.fixture
    def service(self, mock_index):
        """CandidateService with mocked index."""
        return CandidateService(mock_index)

    def test_find_candidate_pairs_intra_task_dedupes_correctly(self, service, mock_index):
        """Test intra-task pair generation deduplicates unordered pairs."""
        # Prepare files A and B (same set)
        files = [
            {'hash': 'h1', 'id': '1'},
            {'hash': 'h2', 'id': '2'},
            {'hash': 'h3', 'id': '3'}
        ]
        language = 'python'

        # Each file has some fingerprints (as hash strings)
        fps_by_hash = {
            'h1': ['fp1', 'fp2'],
            'h2': ['fp2', 'fp3'],
            'h3': ['fp3', 'fp1']
        }

        # get_file_fingerprints_batch returns all at once
        mock_index.get_file_fingerprints_batch.side_effect = lambda hashes, lang: {
            h: fps_by_hash.get(h) for h in hashes
        }

        # find_candidates returns similarity scores for candidates when queried
        def find_candidates(fps, lang):
            if set(fps) == set(fps_by_hash['h1']):
                return {'h2': 0.5, 'h3': 0.5}
            elif set(fps) == set(fps_by_hash['h2']):
                return {'h1': 0.5, 'h3': 0.5}
            elif set(fps) == set(fps_by_hash['h3']):
                return {'h1': 0.5, 'h2': 0.5}
            return {}
        mock_index.find_candidates.side_effect = find_candidates

        pairs = service.find_candidate_pairs(files, language=language, deduplicate=True)

        # Should get 3 unique unordered pairs: (1,2), (1,3), (2,3)
        assert len(pairs) == 3
        pairs_sorted = [sorted((a['id'], b['id'])) for a, b, s in pairs]
        assert ['1', '2'] in pairs_sorted
        assert ['1', '3'] in pairs_sorted
        assert ['2', '3'] in pairs_sorted
        # No pair with same id
        for a, b, s in pairs:
            assert a['id'] != b['id']

    def test_find_candidate_pairs_cross_task_no_dedup(self, service, mock_index):
        """Test cross-task pairs generate all A->B pairs without deduplication."""
        files_a = [
            {'hash': 'a1', 'id': 'a1'},
            {'hash': 'a2', 'id': 'a2'}
        ]
        files_b = [
            {'hash': 'b1', 'id': 'b1'},
            {'hash': 'b2', 'id': 'b2'}
        ]
        language = 'python'

        # Batch fetch returns fingerprints for all files
        all_fps = {'a1': ['a1_fp'], 'a2': ['a2_fp']}
        mock_index.get_file_fingerprints_batch.side_effect = lambda hashes, lang: {
            h: all_fps.get(h) for h in hashes
        }

        # find_candidates for each A returns all B files as candidates
        def find_candidates(fps, lang):
            if fps[0].startswith('a1'):
                return {'b1': 0.7, 'b2': 0.8}
            elif fps[0].startswith('a2'):
                return {'b1': 0.6, 'b2': 0.9}
            return {}
        mock_index.find_candidates.side_effect = find_candidates

        pairs = service.find_candidate_pairs(files_a, files_b, language, deduplicate=False)

        # Should get all 2x2 = 4 pairs
        assert len(pairs) == 4
        for a, b, s in pairs:
            assert a in files_a
            assert b in files_b

    def test_find_candidate_pairs_empty_files_returns_empty(self, service, mock_index):
        """Test empty files_a returns empty list."""
        pairs = service.find_candidate_pairs([], language='python')
        assert pairs == []

    def test_find_candidate_pairs_skips_files_without_fingerprints(self, service, mock_index):
        """Test files with no cached fingerprints are skipped."""
        files = [
            {'hash': 'h1', 'id': '1'},
            {'hash': 'h2', 'id': '2'}
        ]
        # h1 has fingerprints, h2 returns None (not indexed)
        mock_index.get_file_fingerprints_batch.side_effect = lambda hashes, lang: {
            h: ['fp1'] if h == 'h1' else None for h in hashes
        }

        mock_index.find_candidates.return_value = {}

        pairs = service.find_candidate_pairs(files, language='python')

        # Only h1 is processed; h2 skipped (None fingerprints)
        mock_index.find_candidates.assert_called_once()
        called_fps = mock_index.find_candidates.call_args[0][0]
        assert called_fps == ['fp1']

    def test_find_candidate_pairs_skips_self_for_intra_task(self, service, mock_index):
        """Test intra-task comparisons skip self-comparison."""
        files = [{'hash': 'h1', 'id': '1'}]
        mock_index.get_file_fingerprints_batch.return_value = {'h1': ['fp1']}
        mock_index.find_candidates.return_value = {'h1': 1.0}  # candidate includes self

        pairs = service.find_candidate_pairs(files, language='python', deduplicate=True)

        # Should be empty since only candidate is self
        assert len(pairs) == 0

    def test_find_intra_task_pairs_deprecated_wrapper(self, service):
        """Test deprecated wrapper calls unified method."""
        with pytest.warns(DeprecationWarning):
            result = service.find_intra_task_pairs([{'hash': 'h1'}], 'python')
        assert result == service.find_candidate_pairs([{'hash': 'h1'}], None, 'python', True)

    def test_find_cross_task_pairs_deprecated_wrapper(self, service):
        """Test deprecated wrapper calls unified method."""
        with pytest.warns(DeprecationWarning):
            result = service.find_cross_task_pairs([{'hash': 'a'}], [{'hash': 'b'}], 'python')
        assert result == service.find_candidate_pairs([{'hash': 'a'}], [{'hash': 'b'}], 'python', False)
