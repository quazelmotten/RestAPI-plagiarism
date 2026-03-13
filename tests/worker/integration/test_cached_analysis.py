"""
Integration tests for worker components.
Requires Redis (and optionally DB) to be running.
"""

import pytest
import os
import sys
import tempfile
import shutil
from pathlib import Path

# Mark all tests in this file as integration tests
pytestmark = pytest.mark.integration


class TestCachedAnalysis:
    """Integration tests with real Redis and file system."""

    @pytest.fixture(autouse=True)
    def setup_redis(self, redis_test_instance):
        """Ensure Redis is connected and clean before each test."""
        self.redis = redis_test_instance
        # Clear any existing data
        self.redis.flushdb()
        yield
        # Cleanup after test
        self.redis.flushdb()

    def test_full_workflow_with_caching(self, temp_dir):
        """
        Test complete workflow:
        1. Compute and cache fingerprints manually
        2. Run analysis using cached data (should not re-read files)
        3. Verify result matches direct Analyzer.Start()
        """
        from cli.analyzer import Analyzer, parse_file, tokenize_with_tree_sitter, \
            compute_fingerprints, winnow_fingerprints, extract_ast_hashes, index_fingerprints
        from worker.redis_cache import cache

        # Ensure cache is connected to our test redis
        cache._redis = self.redis
        cache._connected = True

        # Create two nearly identical Python files
        code1 = """
def add(a, b):
    return a + b

def multiply(x, y):
    return x * y
"""
        code2 = """
def add(a, b):
    return a + b

def multiply(x, y):
    return x * y
"""
        file1 = os.path.join(temp_dir, "a.py")
        file2 = os.path.join(temp_dir, "b.py")
        with open(file1, 'w') as f:
            f.write(code1)
        with open(file2, 'w') as f:
            f.write(code2)

        # Compute fingerprints for both files (simulating indexing phase)
        _, tree1 = parse_file(file1, "python")
        tokens1 = tokenize_with_tree_sitter(file1, "python", tree=tree1)
        fps1 = winnow_fingerprints(compute_fingerprints(tokens1))
        ast1 = extract_ast_hashes(file1, "python", tree=tree1)

        _, tree2 = parse_file(file2, "python")
        tokens2 = tokenize_with_tree_sitter(file2, "python", tree=tree2)
        fps2 = winnow_fingerprints(compute_fingerprints(tokens2))
        ast2 = extract_ast_hashes(file2, "python", tree=tree2)

        # Cache them
        hash1 = "test_integration_hash1"
        hash2 = "test_integration_hash2"
        cache.cache_fingerprints(hash1, fps1, ast1, tokens1)
        cache.cache_fingerprints(hash2, fps2, ast2, tokens2)

        # Verify they are cached
        assert cache.get_fingerprints(hash1) is not None
        assert cache.get_ast_hashes(hash1) is not None

        # Now run cached analysis (this is what worker does)
        from worker.services.plagiarism_service import PlagiarismService
        from worker.services.result_service import ResultService

        # Use a small executor for testing
        from concurrent.futures import ProcessPoolExecutor
        executor = ProcessPoolExecutor(max_workers=2)
        ps = PlagiarismService(analysis_executor=executor)
        rs = ResultService(ps)

        # Process the pair (this should use cached fingerprints)
        file_a_info = {
            'id': '1',
            'file_hash': hash1,
            'file_path': file1,
            'filename': 'a.py'
        }
        file_b_info = {
            'id': '2',
            'file_hash': hash2,
            'file_path': file2,
            'filename': 'b.py'
        }

        result = rs.process_pair(file_a_info, file_b_info, "python", "test_task")

        # Should have a valid similarity score
        assert result['ast_similarity'] is not None
        assert result['ast_similarity'] > 0

        # Compare with direct Analyzer.Start()
        direct = Analyzer().Start(file1, file2, "python")

        # Similarity must match (within small tolerance for floating point)
        diff = abs(result['ast_similarity'] - direct['similarity_ratio'])
        assert diff < 0.001, f"Similarity mismatch: {result['ast_similarity']} vs {direct['similarity_ratio']}"

        # Verify pairwise result was cached
        cached_pair = cache.get_cached_similarity(hash1, hash2)
        assert cached_pair is not None

        executor.shutdown(wait=True)

    def test_cache_miss_triggers_fingerprint_generation(self, temp_dir):
        """Test that if fingerprints are not in cache, they are generated and stored."""
        from worker.services.processor_service import ProcessorService
        from worker.services.plagiarism_service import PlagiarismService
        from inverted_index import inverted_index

        # Clear inverted index
        inverted_index.clear_all()

        # Setup
        code = "def foo():\n    return 42\n"
        file_path = os.path.join(temp_dir, "test.py")
        with open(file_path, 'w') as f:
            f.write(code)

        file_info = {
            'id': '1',
            'file_hash': 'missing_hash',
            'file_path': file_path,
            'filename': 'test.py'
        }

        # Use real services (with small executor)
        from concurrent.futures import ProcessPoolExecutor
        executor = ProcessPoolExecutor(max_workers=2)
        ps = PlagiarismService(analysis_executor=executor)
        proc = ProcessorService(ps)

        # This should generate fingerprints and add to index
        proc.index_file_fingerprints(file_info, 'python', 'test_task')

        # Verify fingerprints are now in inverted index
        indexed_fps = inverted_index.get_file_fingerprints('missing_hash', 'python')
        assert indexed_fps is not None
        assert len(indexed_fps) > 0

        # Verify fingerprints are also cached in Redis
        cached_fps = proc.cache.get_fingerprints('missing_hash')
        assert cached_fps is not None

        executor.shutdown(wait=True)

    def test_pair_generation_uses_inverted_index(self, temp_dir):
        """Test that candidate pairs are generated efficiently via inverted index."""
        from worker.services.processor_service import ProcessorService
        from worker.services.plagiarism_service import PlagiarismService
        from inverted_index import inverted_index

        inverted_index.clear_all()

        # Create multiple similar files
        files = []
        code_template = "def func{i}():\n    return {i}\n"
        for i in range(5):
            path = os.path.join(temp_dir, f"file{i}.py")
            with open(path, 'w') as f:
                f.write(code_template.format(i=i))
            files.append({
                'id': str(i),
                'file_hash': f"hash{i}",
                'file_path': path,
                'filename': f"file{i}.py"
            })

        # Index all files first
        from concurrent.futures import ProcessPoolExecutor
        executor = ProcessPoolExecutor(max_workers=2)
        ps = PlagiarismService(analysis_executor=executor)
        proc = ProcessorService(ps)

        # Pre-index to avoid fingerprinting during pair gen
        for f in files:
            proc.index_file_fingerprints(f, 'python', 'setup')

        # Now generate intra-task pairs
        pairs = proc.find_intra_task_pairs(files, 'python', 'test_task')

        # Should have some pairs (depending on fingerprint overlap)
        assert isinstance(pairs, list)
        # Each pair is (file_a, file_b)
        for a, b in pairs:
            assert a in files
            assert b in files
            assert a['id'] != b['id']

        executor.shutdown(wait=True)


class TestFingerprintIndexingPerformance:
    """Performance tests for indexing."""

    def test_indexing_30_files_completes_quickly(self, temp_dir):
        """Integration: indexing 30 files should complete in reasonable time."""
        from worker.services.processor_service import ProcessorService
        from worker.services.plagiarism_service import PlagiarismService
        from inverted_index import inverted_index
        import time

        inverted_index.clear_all()

        # Generate 30 small files
        files = []
        for i in range(30):
            path = os.path.join(temp_dir, f"file{i}.py")
            with open(path, 'w') as f:
                f.write(f"def func{i}():\n    return {i}\n")
            files.append({
                'id': str(i),
                'file_hash': f"hash{i}",
                'file_path': path,
                'filename': f"file{i}.py"
            })

        from concurrent.futures import ProcessPoolExecutor
        executor = ProcessPoolExecutor(max_workers=4)
        ps = PlagiarismService(analysis_executor=executor)
        proc = ProcessorService(ps)

        start = time.time()
        proc.ensure_files_indexed(files, 'python', 'perf_test')
        elapsed = time.time() - start

        print(f"Indexing 30 files took {elapsed:.2f}s")
        # This is a performance test - should complete in under 2 seconds
        assert elapsed < 2.0, f"Indexing too slow: {elapsed:.2f}s"

        executor.shutdown(wait=True)
