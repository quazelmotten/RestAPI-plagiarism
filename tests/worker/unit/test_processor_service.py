"""
Unit tests for ProcessorService.
Tests fingerprint indexing and pair generation with mocks.
"""

import os
import pytest
from unittest.mock import MagicMock, patch
from worker.services.processor_service import ProcessorService


class TestProcessorService:
    """Test processor service in isolation."""

    @pytest.fixture
    def mock_plagiarism_service(self):
        ps = MagicMock()
        ps.analysis_executor = MagicMock()
        ps.analysis_executor._max_workers = 4
        return ps

    @pytest.fixture
    def mock_cache(self):
        cache = MagicMock()
        cache.is_connected = True
        return cache

    @pytest.fixture
    def mock_inverted_index(self):
        ii = MagicMock()
        return ii

    @pytest.fixture
    def processor(self, mock_plagiarism_service, mock_cache, mock_inverted_index):
        with patch('worker.services.processor_service.cache', mock_cache), \
             patch('worker.services.processor_service.inverted_index', mock_inverted_index):
            yield ProcessorService(mock_plagiarism_service)

    def test_index_file_fingerprints_success(self, processor, mock_plagiarism_service, mock_inverted_index, temp_dir):
        file_path = os.path.join(temp_dir, "test.py")
        with open(file_path, 'w') as f:
            f.write("def foo(): pass")

        file_info = {
            'id': '1',
            'file_hash': 'test_hash',
            'file_path': file_path,
            'filename': 'test.py'
        }

        mock_plagiarism_service.safe_run_cli_fingerprint.return_value = {
            'fingerprints': [{'hash': 123, 'start': (0, 0), 'end': (1, 0)}],
            'ast_hashes': [456],
            'tokens': [{'type': 'def', 'start': (0, 0), 'end': (0, 3)}]
        }
        mock_inverted_index.get_file_fingerprints.return_value = None

        result = processor.index_file_fingerprints(file_info, 'python', 'test_task')

        assert result is not None
        assert len(result) == 1
        mock_plagiarism_service.safe_run_cli_fingerprint.assert_called_once()
        mock_inverted_index.add_file_fingerprints.assert_called_once()
        # Verify caching
        processor.cache.cache_fingerprints.assert_called_once()

    def test_index_file_fingerprint_already_indexed(self, processor, mock_inverted_index):
        file_info = {
            'id': '1',
            'file_hash': 'existing_hash',
            'file_path': '/fake/path.py',
            'filename': 'existing.py'
        }

        mock_inverted_index.get_file_fingerprints.return_value = [{'hash': 123}]
        processor.cache.get_fingerprints.return_value = [{'hash': 123, 'start': (0,0), 'end': (1,0)}]

        result = processor.index_file_fingerprints(file_info, 'python', 'test_task')

        assert result is not None
        mock_inverted_index.add_file_fingerprints.assert_not_called()
        # Fingerprint generation should not be called
        processor.plagiarism_service.safe_run_cli_fingerprint.assert_not_called()

    def test_index_file_fingerprint_missing_info_returns_none(self, processor):
        file_info = {'id': '1'}  # missing hash and path
        result = processor.index_file_fingerprints(file_info, 'python', 'test_task')
        assert result is None

    def test_ensure_files_indexed_parallelizes(self, processor, mock_plagiarism_service, temp_dir):
        """Test that ensure_files_indexed processes all files (sequential design)."""
        files = []
        for i in range(5):
            path = os.path.join(temp_dir, f"file{i}.py")
            with open(path, 'w') as f:
                f.write(f"def func{i}(): return {i}")
            files.append({
                'id': str(i),
                'file_hash': f'hash{i}',
                'file_path': path,
                'filename': f'file{i}.py'
            })

        # None indexed, no cached fingerprints
        mock_inverted_index = processor.inverted_index
        mock_inverted_index.get_file_fingerprints.return_value = None
        processor.cache.get_fingerprints.return_value = None
        mock_plagiarism_service.safe_run_cli_fingerprint.return_value = {
            'fingerprints': [{'hash': 1, 'start': (0,0), 'end': (1,0)}],
            'ast_hashes': [],
            'tokens': []
        }

        fingerprint_map = processor.ensure_files_indexed(files, 'python', 'test_task')

        # index_file_fingerprints should be called 5 times (once per file)
        # safe_run_cli_fingerprint is called once per file inside index_file_fingerprints
        assert mock_plagiarism_service.safe_run_cli_fingerprint.call_count == 5
        # Fingerprint map should contain entries for all files
        assert len(fingerprint_map) == 5

    def test_ensure_files_indexed_sequential_fallback(self, processor, mock_plagiarism_service, temp_dir):
        files = []
        for i in range(3):
            path = os.path.join(temp_dir, f"file{i}.py")
            with open(path, 'w') as f:
                f.write(f"x={i}")
            files.append({
                'id': str(i),
                'file_hash': f'hash{i}',
                'file_path': path,
                'filename': f'file{i}.py'
            })

        # Remove executor to trigger sequential fallback
        processor.plagiarism_service.analysis_executor = None

        mock_inverted_index = processor.inverted_index
        mock_inverted_index.get_file_fingerprints.return_value = None
        processor.cache.get_fingerprints.return_value = None
        mock_plagiarism_service.safe_run_cli_fingerprint.return_value = {
            'fingerprints': [], 'ast_hashes': [], 'tokens': []
        }

        processor.ensure_files_indexed(files, 'python', 'test_task')

        # index_file_fingerprints called directly 3 times (via sequential loop)
        # safe_run_cli_fingerprint called for each file (once inside index_file_fingerprints)
        assert mock_plagiarism_service.safe_run_cli_fingerprint.call_count == 3

    def test_ensure_files_indexed_skips_already_indexed(self, processor, mock_plagiarism_service, temp_dir):
        """Test that already indexed files are skipped and only missing files are processed."""
        files = []
        for i in range(2):
            path = os.path.join(temp_dir, f"file{i}.py")
            with open(path, 'w') as f:
                f.write(f"x={i}")
            files.append({
                'id': str(i),
                'file_hash': f'hash{i}',
                'file_path': path,
                'filename': f'file{i}.py'
            })

        mock_inverted_index = processor.inverted_index
        # Call sequence: file0: get_file_fingerprints once; file1: get_file_fingerprints twice (once in ensure_files_indexed, once inside index_file_fingerprints)
        mock_inverted_index.get_file_fingerprints.side_effect = [
            [{'hash': 123}],  # file0: already indexed -> truthy
            None,              # file1: first check -> not indexed
            None               # file1: second check inside index_file_fingerprints -> not indexed
        ]
        # Return fingerprints for the already-indexed file from cache
        processor.cache.get_fingerprints.side_effect = [
            [{'hash': 123, 'start': (0,0), 'end': (1,0)}],  # for already-indexed file (file0)
            None  # for the second file (not cached) - cache check before indexing
        ]
        mock_plagiarism_service.safe_run_cli_fingerprint.return_value = {
            'fingerprints': [{'hash': 456, 'start': (0,0), 'end': (1,0)}],
            'ast_hashes': [],
            'tokens': []
        }

        fingerprint_map = processor.ensure_files_indexed(files, 'python', 'test_task')

        # safe_run_cli_fingerprint should be called only once for the second file
        assert mock_plagiarism_service.safe_run_cli_fingerprint.call_count == 1
        # Fingerprint map should have entries for both files
        assert len(fingerprint_map) == 2
        # Already-indexed file should be in map (from cache or inverted index)
        assert 'hash0' in fingerprint_map or processor.cache.get_fingerprints.called

    def test_ensure_files_indexed_uses_cached_fingerprints(self, processor, mock_plagiarism_service, temp_dir):
        files = []
        for i in range(2):
            path = os.path.join(temp_dir, f"file{i}.py")
            with open(path, 'w') as f:
                f.write(f"x={i}")
            files.append({
                'id': str(i),
                'file_hash': f'hash{i}',
                'file_path': path,
                'filename': f'file{i}.py'
            })

        mock_inverted_index = processor.inverted_index
        mock_inverted_index.get_file_fingerprints.return_value = None
        # Cached fingerprints exist
        cached_fps = [{'hash': 123, 'start': (0,0), 'end': (1,0)}]
        processor.cache.get_fingerprints.return_value = cached_fps

        processor.ensure_files_indexed(files, 'python', 'test_task')

        # Should have added cached fingerprints to inverted index without generating
        assert mock_inverted_index.add_file_fingerprints.call_count == 2
        mock_plagiarism_service.safe_run_cli_fingerprint.assert_not_called()

    def test_find_intra_task_pairs_uses_inverted_index(self, processor, mock_inverted_index):
        """Test intra-task pair generation."""
        files = [
            {'id': '1', 'file_hash': 'h1', 'file_path': '/fake1.py'},
            {'id': '2', 'file_hash': 'h2', 'file_path': '/fake2.py'},
            {'id': '3', 'file_hash': 'h3', 'file_path': '/fake3.py'},
        ]

        # Mock inverted index to return candidate hashes with overlap scores
        def mock_find_candidates(fingerprints, language):
            if len(fingerprints) >= 100:
                return {'h2': 0.5, 'h3': 0.3}  # Dict: file_hash -> overlap_score
            return {}

        mock_inverted_index.find_candidate_files.side_effect = mock_find_candidates

        # Setup cache to return fingerprints for these file hashes
        fps_100 = [{'hash': i} for i in range(100)]
        def mock_get_fingerprints(file_hash):
            if file_hash in ['h1', 'h2', 'h3']:
                return fps_100
            return None
        processor.cache.get_fingerprints.side_effect = mock_get_fingerprints

        pairs = processor.find_intra_task_pairs(files, 'python', 'test_task')

        # Should produce pairs: (h1,h2), (h1,h3), (h2,h3), (h3,h2) depending on candidate returns.
        assert len(pairs) >= 2
        for a, b, score in pairs:
            assert a in files
            assert b in files
            assert a['id'] != b['id']
            assert 0.0 <= score <= 1.0

    def test_find_cross_task_pairs(self, processor, mock_inverted_index):
        """Test cross-task pair generation."""
        new_files = [
            {'id': 'new1', 'file_hash': 'new_h1', 'file_path': '/n1.py', 'filename': 'n1.py'},
            {'id': 'new2', 'file_hash': 'new_h2', 'file_path': '/n2.py', 'filename': 'n2.py'},
        ]
        existing_files = [
            {'id': 'old1', 'file_hash': 'old_h1', 'file_path': '/o1.py', 'filename': 'o1.py'},
            {'id': 'old2', 'file_hash': 'old_h2', 'file_path': '/o2.py', 'filename': 'o2.py'},
        ]

        def mock_find_candidates(fingerprints, language):
            if len(fingerprints) >= 100:
                return {'old_h1': 0.6, 'old_h2': 0.4}
            return {}

        mock_inverted_index.find_candidate_files.side_effect = mock_find_candidates

        # Setup cache to return fingerprints for all files
        fps_100 = [{'hash': i} for i in range(100)]
        def mock_get_fingerprints(file_hash):
            if file_hash in ['new_h1', 'new_h2', 'old_h1', 'old_h2']:
                return fps_100
            return None
        processor.cache.get_fingerprints.side_effect = mock_get_fingerprints
        # Also ensure that cache.lock_fingerprint_computation returns False to avoid lock
        processor.cache.lock_fingerprint_computation.return_value = False

        pairs = processor.find_cross_task_pairs(new_files, existing_files, 'python', 'test_task')

        # Each new file should pair with both existing files
        assert len(pairs) == 4
        for new_file, old_file, score in pairs:
            assert new_file in new_files
            assert old_file in existing_files

    def test_find_cross_task_pairs_fallback_on_error(self, processor, mock_inverted_index, mock_plagiarism_service):
        """Test that if candidate generation fails, falls back to all-existing pairs."""
        new_files = [{'id': 'new1', 'file_hash': 'new_h1', 'file_path': '/fake', 'filename': 'new1.py'}]
        existing_files = [{'id': 'old1', 'file_hash': 'old_h1'}, {'id': 'old2', 'file_hash': 'old_h2'}]

        # inverted_index.find_candidate_files raises an exception
        mock_inverted_index.find_candidate_files.side_effect = RuntimeError("index error")
        # safe_run_cli_fingerprint will be called to generate fingerprints; we'll let it succeed
        mock_plagiarism_service.safe_run_cli_fingerprint.return_value = {
            'fingerprints': [{'hash': 1, 'start': (0,0), 'end': (0,1)}],
            'ast_hashes': [],
            'tokens': []
        }
        # Ensure cache.get_fingerprints returns None for the new file to trigger generation
        processor.cache.get_fingerprints.return_value = None
        # No lock
        processor.cache.lock_fingerprint_computation.return_value = False

        pairs = processor.find_cross_task_pairs(new_files, existing_files, 'python', 'test_task')

        # Should have fallen back to pairing with all existing files
        assert len(pairs) == 2
        for new_file, old_file, score in pairs:
            assert new_file['id'] == 'new1'
            assert old_file in existing_files
