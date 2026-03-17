"""
Integration tests for ProcessorService with mock Redis.
Tests that indexing and pair generation work correctly with the in-memory Redis mock.
"""

import pytest
import os
from unittest.mock import patch

pytestmark = pytest.mark.integration


class TestServiceIntegration:
    """Integration tests for ProcessorService."""

    @pytest.fixture(autouse=True)
    def setup_redis(self, redis_test_instance):
        """Provide a mock Redis instance for each test and configure global cache."""
        self.redis = redis_test_instance
        self.redis.flushdb()
        # Configure the top-level redis_cache.cache to use this mock Redis
        import worker.redis_cache as redis_cache
        redis_cache.cache._redis = self.redis
        redis_cache.cache._connected = True
        # Also configure inverted_index.redis to use this mock
        import worker.inverted_index as inverted_index
        inverted_index.redis = self.redis
        yield
        self.redis.flushdb()

    def test_processor_index_stores_fingerprints_in_cache_and_index(self, temp_dir):
        """Test that indexing a file stores fingerprints in both cache and inverted index."""
        from worker.services.plagiarism_service import PlagiarismService
        from worker.services.processor_service import ProcessorService

        # Fake analyzer output (positions as lists for JSON serialization)
        fake_fingerprints = [
            {'hash': 123, 'start': [0, 0], 'end': [1, 0]},
            {'hash': 456, 'start': [1, 0], 'end': [2, 0]}
        ]
        fake_ast_hashes = [789]
        fake_tokens = [{'type': 'def', 'start': [0, 0], 'end': [0, 3]}]

        ps = PlagiarismService(analysis_executor=None)
        proc = ProcessorService(ps)

        # Debug: check cache._redis
        import sys
        print(f"DEBUG: cache._redis type: {type(proc.cache._redis)} id={id(proc.cache._redis)}", file=sys.stderr)
        print(f"DEBUG: self.redis type: {type(self.redis)} id={id(self.redis)}", file=sys.stderr)
        print(f"DEBUG: same object? {proc.cache._redis is self.redis}", file=sys.stderr)

        file_info = {
            'id': '1',
            'file_hash': 'filehash123',
            'file_path': os.path.join(temp_dir, 'test.py'),
            'filename': 'test.py'
        }
        with open(file_info['file_path'], 'w') as f:
            f.write("def foo():\n    return 42\n")

        # Mock fingerprint generation
        with patch.object(ps, 'safe_run_cli_fingerprint', return_value={
            'fingerprints': fake_fingerprints,
            'ast_hashes': fake_ast_hashes,
            'tokens': fake_tokens
        }):
            result = proc.index_file_fingerprints(file_info, 'python', 'test_task')

        assert result  # Returns fingerprints list on success

        # Verify cached fingerprints can be retrieved
        cached_fps = proc.cache.get_fingerprints(file_info['file_hash'])
        assert cached_fps is not None
        assert len(cached_fps) == len(fake_fingerprints)

        # Verify inverted index contains fingerprints for this file
        indexed_fps = proc.inverted_index.get_file_fingerprints(file_info['file_hash'], 'python')
        assert indexed_fps is not None
        assert len(indexed_fps) == len(fake_fingerprints)

    def test_processor_find_intra_task_pairs(self, temp_dir):
        """Test that find_intra_task_pairs generates pairs using inverted index."""
        from worker.services.plagiarism_service import PlagiarismService
        from worker.services.processor_service import ProcessorService

        ps = PlagiarismService(analysis_executor=None)
        proc = ProcessorService(ps)

        # Create 5 files
        files = []
        for i in range(5):
            path = os.path.join(temp_dir, f'f{i}.py')
            with open(path, 'w') as f:
                f.write(f'def func{i}():\n    return {i}\n')
            files.append({
                'id': str(i),
                'file_hash': f'hash{i}',
                'file_path': path,
                'filename': f'f{i}.py'
            })

        # Index all files with many fingerprints to ensure candidate generation
        for f in files:
            with patch.object(ps, 'safe_run_cli_fingerprint', return_value={
                'fingerprints': [{'hash': j, 'start': [0,0], 'end': [1,0]} for j in range(100)],
                'ast_hashes': list(range(100)),
                'tokens': []
            }):
                result = proc.index_file_fingerprints(f, 'python', 'setup')
                assert result  # Returns fingerprints list on success

        # Generate intra-task pairs
        pairs = proc.find_intra_task_pairs(files, 'python', 'test_task')

        assert len(pairs) > 0
        for a, b, score in pairs:
            assert a in files and b in files
            assert a['id'] != b['id']

    def test_processor_find_cross_task_pairs(self, temp_dir):
        """Test cross-task pair generation."""
        from worker.services.plagiarism_service import PlagiarismService
        from worker.services.processor_service import ProcessorService

        ps = PlagiarismService(analysis_executor=None)
        proc = ProcessorService(ps)

        # New files
        new_files = []
        for i in range(2):
            path = os.path.join(temp_dir, f'new{i}.py')
            with open(path, 'w') as f:
                f.write(f'def new{i}():\n    return {i}\n')
            new_files.append({
                'id': f'n{i}',
                'file_hash': f'newhash{i}',
                'file_path': path,
                'filename': f'new{i}.py'
            })
        # Existing files
        existing_files = []
        for i in range(3):
            path = os.path.join(temp_dir, f'exist{i}.py')
            with open(path, 'w') as f:
                f.write(f'def exist{i}():\n    return {i}\n')
            existing_files.append({
                'id': f'e{i}',
                'file_hash': f'existhash{i}',
                'file_path': path,
                'filename': f'exist{i}.py'
            })

        # Index all files with many fingerprints
        for f in new_files + existing_files:
            with patch.object(ps, 'safe_run_cli_fingerprint', return_value={
                'fingerprints': [{'hash': j, 'start': [0,0], 'end': [1,0]} for j in range(100)],
                'ast_hashes': list(range(100)),
                'tokens': []
            }):
                result = proc.index_file_fingerprints(f, 'python', 'setup')
                assert result  # Returns fingerprints list on success

        # Generate cross-task pairs
        pairs = proc.find_cross_task_pairs(new_files, existing_files, 'python', 'test_task')

        assert len(pairs) == len(new_files) * len(existing_files)
        for new_file, old_file, score in pairs:
            assert new_file in new_files
            assert old_file in existing_files
