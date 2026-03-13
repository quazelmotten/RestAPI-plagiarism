"""
Unit tests for ProcessorService.
Tests fingerprint indexing and pair generation.
"""

import pytest
import os
from unittest.mock import MagicMock, patch
from worker.services.processor_service import ProcessorService


class TestProcessorService:
    """Test processor service."""

    @pytest.fixture
    def mock_plagiarism_service(self):
        """Mock plagiarism service for fingerprinting."""
        ps = MagicMock()
        ps.analysis_executor = MagicMock()
        ps.analysis_executor._max_workers = 4
        return ps

    @pytest.fixture
    def processor(self, mock_plagiarism_service, mock_redis):
        """Create processor service with mocked dependencies."""
        proc = ProcessorService(mock_plagiarism_service)
        proc.cache._connected = True
        proc.cache._redis = mock_redis
        return proc

    def test_index_file_fingerprints_success(self, processor, temp_dir, mock_plagiarism_service):
        """Test successful indexing of a file."""
        file_path = os.path.join(temp_dir, "test.py")
        with open(file_path, 'w') as f:
            f.write("def foo(): pass")

        file_info = {
            'id': '1',
            'file_hash': 'test_hash',
            'file_path': file_path,
            'filename': 'test.py'
        }

        # Mock fingerprint generation
        mock_plagiarism_service.safe_run_cli_fingerprint.return_value = {
            'fingerprints': [{'hash': 123, 'start': (0,0), 'end': (1,0)}],
            'ast_hashes': [456],
            'tokens': [{'type': 'def', 'start': (0,0), 'end': (0,3)}]
        }

        # Mock inverted index check - file not indexed yet
        processor.inverted_index = MagicMock()
        processor.inverted_index.get_file_fingerprints.return_value = None

        result = processor.index_file_fingerprints(file_info, 'python', 'test_task')

        assert result is True
        mock_plagiarism_service.safe_run_cli_fingerprint.assert_called_once()
        processor.inverted_index.add_file_fingerprints.assert_called_once()

    def test_index_file_fingerprint_already_indexed(self, processor):
        """Test that already indexed file is skipped."""
        file_info = {
            'id': '1',
            'file_hash': 'existing_hash',
            'file_path': '/fake/path.py',
            'filename': 'existing.py'
        }

        # Mock inverted index to return existing fingerprints
        processor.inverted_index = MagicMock()
        processor.inverted_index.get_file_fingerprints.return_value = [{'hash': 123}]

        result = processor.index_file_fingerprints(file_info, 'python', 'test_task')

        assert result is True  # Returns True because already indexed
        processor.inverted_index.add_file_fingerprints.assert_not_called()

    def test_ensure_files_indexed_parallelizes(self, processor, mock_plagiarism_service, temp_dir):
        """Test that multiple files are indexed in parallel using executor."""
        # Create multiple file infos
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

        # Mock that none of these files are indexed yet and no cache exists
        processor.inverted_index = MagicMock()
        processor.inverted_index.get_file_fingerprints.return_value = None
        mock_plagiarism_service.analysis_executor = MagicMock()

        # Mock executor.submit to immediately return successful result
        def mock_submit(func, *args, **kwargs):
            future = MagicMock()
            future.result.return_value = True
            return future

        mock_plagiarism_service.analysis_executor.submit.side_effect = mock_submit

        processor.ensure_files_indexed(files, 'python', 'test_task')

        # Should submit all files to executor
        assert mock_plagiarism_service.analysis_executor.submit.call_count >= 5

    def test_ensure_files_indexed_sequential_fallback(self, processor, mock_plagiarism_service, temp_dir):
        """Test sequential indexing when executor is None."""
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

        # No executor - should fallback to sequential
        processor.plagiarism_service.analysis_executor = None
        processor.inverted_index = MagicMock()
        processor.inverted_index.get_file_fingerprints.return_value = None
        mock_plagiarism_service.safe_run_cli_fingerprint.return_value = {
            'fingerprints': [], 'ast_hashes': [], 'tokens': []
        }

        processor.ensure_files_indexed(files, 'python', 'test_task')

        # Should call index_file_fingerprints directly (sequentially)
        assert mock_plagiarism_service.safe_run_cli_fingerprint.call_count == 3

    def test_find_intra_task_pairs_uses_inverted_index(self, processor):
        """Test intra-task pair generation."""
        files = [
            {'id': '1', 'file_hash': 'h1'},
            {'id': '2', 'file_hash': 'h2'},
            {'id': '3', 'file_hash': 'h3'},
        ]

        # Mock inverted index to return candidate hashes for each file
        def mock_find_candidates(fps, lang):
            if len(fps) >= 100:  # file with many fingerprints
                return {'h2', 'h3'}  # overlaps with others
            return set()

        processor.inverted_index.find_candidate_files = MagicMock(side_effect=mock_find_candidates)
        processor._file_fingerprint_cache = {}  # Populate cache to avoid fingerprinting

        # Pre-cache fingerprints for each file to prevent fingerprint generation calls
        for file_info in files:
            processor._file_fingerprint_cache[file_info['file_hash']] = [{'hash': i} for i in range(100)]

        pairs = processor.find_intra_task_pairs(files, 'python', 'test_task')

        # Should produce pairs: (1,2), (1,3), (2,3) roughly
        assert len(pairs) >= 1
        # Each pair should be tuple of file dicts
        for a, b in pairs:
            assert a in files
            assert b in files
            assert a['id'] != b['id']

    def test_find_cross_task_pairs(self, processor):
        """Test cross-task pair generation."""
        new_files = [
            {'id': 'new1', 'file_hash': 'new_h1'},
            {'id': 'new2', 'file_hash': 'new_h2'},
        ]
        existing_files = [
            {'id': 'old1', 'file_hash': 'old_h1'},
            {'id': 'old2', 'file_hash': 'old_h2'},
        ]

        # Mock inverted index - new files overlap with old ones
        def mock_find_candidates(fps, lang):
            if len(fps) >= 100:
                return {'old_h1', 'old_h2'}
            return set()

        processor.inverted_index.find_candidate_files = MagicMock(side_effect=mock_find_candidates)
        processor._file_fingerprint_cache = {}

        # Pre-cache fingerprints
        for f in new_files + existing_files:
            processor._file_fingerprint_cache[f['file_hash']] = [{'hash': i} for i in range(100)]

        pairs = processor.find_cross_task_pairs(new_files, existing_files, 'python', 'test_task')

        # Should produce pairs: (new1,old1), (new1,old2), (new2,old1), (new2,old2)
        assert len(pairs) >= 2
        for new_file, old_file in pairs:
            assert new_file in new_files
            assert old_file in existing_files
