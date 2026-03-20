"""
Integration tests for new service architecture with mock Redis.
Tests real interactions between services using in-memory Redis.
"""

import pytest
import os
from unittest.mock import patch, MagicMock

from worker.infrastructure.redis_cache import RedisFingerprintCache
from worker.infrastructure.inverted_index import RedisInvertedIndex
from worker.services.fingerprint_service import FingerprintService
from worker.services.indexing_service import IndexingService
from worker.services.candidate_service import CandidateService
from worker.services.task_service import TaskService
from worker.services.result_service import ResultService

pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def mock_core_functions(monkeypatch):
    """Mock core plagiarism functions to provide deterministic data."""
    def dummy_tokenize(file_path, language):
        return [{'type': 'function_definition', 'start': (0, 0), 'end': (2, 0), 'text': 'def func():'}]
    def dummy_compute(tokens):
        return [{'hash': 12345, 'start': (0, 0), 'end': (2, 0)}]
    def dummy_winnow(raw_fps):
        return [{'hash': fp['hash'], 'start': list(fp['start']), 'end': list(fp['end'])} for fp in raw_fps]
    def dummy_extract(file_path, language):
        return [123456]
    monkeypatch.setattr('worker.services.fingerprint_service.tokenize_with_tree_sitter', dummy_tokenize)
    monkeypatch.setattr('worker.services.fingerprint_service.compute_fingerprints', dummy_compute)
    monkeypatch.setattr('worker.services.fingerprint_service.winnow_fingerprints', dummy_winnow)
    monkeypatch.setattr('worker.services.fingerprint_service.extract_ast_hashes', dummy_extract)


class TestServiceIntegration:
    """Integration tests for new service architecture."""

    @pytest.fixture
    def services(self, redis_test_instance):
        """Setup full service stack with test Redis."""
        cache = RedisFingerprintCache(redis_test_instance, ttl=3600)
        index = RedisInvertedIndex(redis_test_instance, min_overlap_threshold=0.15)
        fpsvc = FingerprintService(cache)
        idxsvc = IndexingService(index, cache, fpsvc)
        candsvc = CandidateService(index)
        return {
            'cache': cache,
            'index': index,
            'fingerprint_svc': fpsvc,
            'indexing_svc': idxsvc,
            'candidate_svc': candsvc
        }

    def test_fingerprint_service_generates_and_caches(self, services, temp_dir):
        """Test fingerprint generation and caching."""
        fpsvc = services['fingerprint_svc']
        cache = services['cache']

        file_path = os.path.join(temp_dir, "simple.py")
        with open(file_path, "w") as f:
            f.write("def hello():\n    print('world')\n")

        file_info = {
            'file_hash': 'test_hash_123',
            'file_path': file_path
        }

        # First call generates
        fps1 = fpsvc.ensure_fingerprinted(file_info, 'python')
        assert fps1 is not None
        assert len(fps1) > 0

        # Verify cache contains fingerprints
        cached = cache.get_fingerprints('test_hash_123')
        assert cached is not None
        assert len(cached) == len(fps1)

        # Second call from cache returns same
        fps2 = fpsvc.ensure_fingerprinted(file_info, 'python')
        assert fps2 == fps1

    def test_indexing_service_indexes_files(self, services, temp_dir):
        """Test indexing service populates inverted index."""
        idxsvc = services['indexing_svc']
        cache = services['cache']
        index = services['index']

        file_path = os.path.join(temp_dir, "test.py")
        with open(file_path, "w") as f:
            f.write("def hello():\n    print('world')\n")

        file_info = {
            'file_hash': 'file123',
            'file_path': file_path
        }

        fingerprint_map = idxsvc.ensure_files_indexed([file_info], 'python', existing_files=[])

        assert 'file123' in fingerprint_map
        assert len(fingerprint_map['file123']) > 0

        # Verify inverted index has file
        stored_hashes = index.get_file_fingerprints('file123', 'python')
        assert stored_hashes is not None
        assert len(stored_hashes) > 0

    def test_candidate_service_intra_task_pairs(self, services, temp_dir):
        """Test candidate service finds pairs within files."""
        candsvc = services['candidate_svc']
        idxsvc = services['indexing_svc']

        files = []
        for i in range(3):
            path = os.path.join(temp_dir, f'file{i}.py')
            with open(path, 'w') as f:
                f.write(f'def func{i}():\n    return {i}\n')
            files.append({
                'file_hash': f'hash{i}',
                'file_path': path
            })

        idxsvc.ensure_files_indexed(files, 'python', existing_files=[])
        pairs = candsvc.find_candidate_pairs(files, language='python', deduplicate=True)

        assert isinstance(pairs, list)
        for a, b, score in pairs:
            assert a in files and b in files
            assert a['file_hash'] != b['file_hash']
            assert 0 <= score <= 1

    def test_candidate_service_cross_task_pairs(self, services, temp_dir):
        """Test candidate service finds pairs between file sets."""
        idxsvc = services['indexing_svc']
        candsvc = services['candidate_svc']

        # Existing files
        existing_files = []
        for i in range(2):
            path = os.path.join(temp_dir, f'exist{i}.py')
            with open(path, 'w') as f:
                f.write(f'def exist{i}():\n    return {i}\n')
            existing_files.append({'file_hash': f'exist_hash{i}', 'file_path': path})

        idxsvc.ensure_files_indexed(existing_files, 'python', existing_files=[])

        # New files
        new_files = []
        for i in range(2):
            path = os.path.join(temp_dir, f'new{i}.py')
            with open(path, 'w') as f:
                f.write(f'def new{i}():\n    return {i}\n')
            new_files.append({'file_hash': f'new_hash{i}', 'file_path': path})

        idxsvc.ensure_files_indexed(new_files, 'python', existing_files=existing_files)

        cross_pairs = candsvc.find_candidate_pairs(new_files, existing_files, language='python', deduplicate=False)

        assert isinstance(cross_pairs, list)
        for a, b, score in cross_pairs:
            assert a in new_files
            assert b in existing_files
            assert 0 <= score <= 1

    def test_task_service_full_workflow(self, redis_test_instance, temp_dir):
        """Test TaskService completes full workflow."""
        # Use custom repository to avoid DB
        from unittest.mock import MagicMock

        # Create fake repository
        fake_repo = MagicMock()
        fake_repo.get_all_files.return_value = []
        fake_repo.get_max_similarity.return_value = 0.0

        # Need to build task_service with our test Redis services but custom repo
        cache = RedisFingerprintCache(redis_test_instance, ttl=3600)
        index = RedisInvertedIndex(redis_test_instance, min_overlap_threshold=0.15)
        fpsvc = FingerprintService(cache)
        idxsvc = IndexingService(index, cache, fpsvc)
        candsvc = CandidateService(index)
        result_svc = ResultService(fake_repo)
        # Spy on store_similarity_scores and finalize_task
        result_svc.store_similarity_scores = MagicMock(wraps=result_svc.store_similarity_scores)
        result_svc.finalize_task = MagicMock(wraps=result_svc.finalize_task)

        task_service = TaskService(
            fingerprint_service=fpsvc,
            indexing_service=idxsvc,
            candidate_service=candsvc,
            analysis_service=None,
            result_service=result_svc,
            repository=fake_repo
        )

        # Create files
        content = 'def func():\n    return 42\n'
        files = []
        for i in range(2):
            path = os.path.join(temp_dir, f'file{i}.py')
            with open(path, 'w') as f:
                f.write(content)
            files.append({'id': f'file{i}', 'file_hash': f'h{i}', 'file_path': path})

        task_id = "integration_test"
        task_service.process_task(task_id, files, 'python')

        # Verify interactions
        fake_repo.update_task.assert_called()
        result_svc.store_similarity_scores.assert_called_once()
        result_svc.finalize_task.assert_called_once()
        fake_repo.bulk_insert_results.assert_called()
