#!/usr/bin/env python3
"""
Regression test suite for worker performance.
Fails if throughput drops below thresholds.
Run: python tests/worker/performance/regression_suite.py
"""

import os
import shutil
import sys
import tempfile
import time

# Add paths
worker_dir = os.path.join(os.path.dirname(__file__), "..", "..", "worker")
sys.path.insert(0, worker_dir)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from concurrent.futures import ProcessPoolExecutor  # noqa: E402

from cli.analyzer import (  # noqa: E402
    compute_fingerprints,
    extract_ast_hashes,
    parse_file,
    tokenize_with_tree_sitter,
    winnow_fingerprints,
)
from inverted_index import inverted_index  # noqa: E402
from worker.redis_cache import cache  # noqa: E402
from worker.services.analysis_service import AnalysisService  # noqa: E402
from worker.services.result_service import ResultService  # noqa: E402
from worker.services.similarity_service import SimilarityService  # noqa: E402

# Thresholds - adjust based on your baseline measurements
THRESHOLDS = {
    "pairs_per_second_min": 60,  # Should maintain at least 60 pairs/sec
    "indexing_30_files_max_seconds": 2.0,
    "similarity_match_tolerance": 0.001,
    "analysis_100_pairs_max_seconds": 10.0,  # 100 pairs should complete in under 10s
}


def setup_test_env():
    """Initialize services and test files."""
    # Connect Redis
    if not cache.is_connected:
        if not cache.connect():
            print("ERROR: Redis not available for performance tests")
            sys.exit(1)
    cache._redis.flushdb()

    # Create executor (use 4 workers for testing, consistent with default)
    executor = ProcessPoolExecutor(max_workers=4)
    asvc = AnalysisService(analysis_executor=executor)
    ssvc = SimilarityService()
    rs = ResultService(asvc)

    # Create temp files
    tmpdir = tempfile.mkdtemp()

    return asvc, ssvc, rs, tmpdir, executor


def teardown(executor, tmpdir):
    """Clean up."""
    executor.shutdown(wait=True)
    shutil.rmtree(tmpdir)
    cache._redis.flushdb()


def generate_files(tmpdir, count=30):
    """Generate test files."""
    files = []
    for i in range(count):
        path = os.path.join(tmpdir, f"file{i}.py")
        with open(path, "w") as f:
            f.write(f"def func{i}():\n    return {i}\n")
        files.append(
            {"id": str(i), "file_hash": f"hash{i}", "file_path": path, "filename": f"file{i}.py"}
        )
    return files, tmpdir


def precompute_fingerprints(analysis_service, similarity_service, files):
    """Pre-cache fingerprints for all files using processor."""
    from worker.services.processor_service import ProcessorService

    proc = ProcessorService(analysis_service, similarity_service)
    # Clear inverted index first
    inverted_index.clear_all()
    proc.ensure_files_indexed(files, "python", "perf_test")
    return proc


def test_similarity_accuracy(analysis_service, similarity_service, result_service, tmpdir):
    """Test 1: Verify cached analysis produces identical results to Analyzer.Start()."""
    print("\n[Test 1] Accuracy verification...")
    from cli.analyzer import Analyzer

    # Create two similar files
    code = "def add(a, b):\n    return a + b\n"
    file1 = os.path.join(tmpdir, "a.py")
    file2 = os.path.join(tmpdir, "b.py")
    with open(file1, "w") as f:
        f.write(code)
    with open(file2, "w") as f:
        f.write(code)

    # Compute fingerprints
    _, tree1 = parse_file(file1, "python")
    tokens1 = tokenize_with_tree_sitter(file1, "python", tree=tree1)
    fps1 = winnow_fingerprints(compute_fingerprints(tokens1))
    ast1 = extract_ast_hashes(file1, "python", tree=tree1)
    hash1 = "acc_test_1"
    hash2 = "acc_test_2"
    cache.cache_fingerprints(hash1, fps1, ast1, tokens1)
    cache.cache_fingerprints(hash2, fps1, ast1, tokens1)

    # Cached analysis via result service
    file_a_info = {"id": "1", "file_hash": hash1, "file_path": file1, "filename": "a.py"}
    file_b_info = {"id": "2", "file_hash": hash2, "file_path": file2, "filename": "b.py"}

    result_cached = result_service.process_pair(file_a_info, file_b_info, "python", "accuracy_test")

    # Direct analyzer
    direct = Analyzer().Start(file1, file2, "python")

    diff = abs(result_cached["ast_similarity"] - direct["similarity_ratio"])
    assert diff < THRESHOLDS["similarity_match_tolerance"], (
        f"Accuracy regression: cached={result_cached['ast_similarity']} direct={direct['similarity_ratio']} diff={diff}"
    )

    print(f"  ✓ Accuracy test passed (diff={diff:.6f})")


def test_analysis_throughput(analysis_service, similarity_service, result_service, tmpdir):
    """Test 2: Throughput should meet minimum threshold."""
    print("\n[Test 2] Analysis throughput...")
    n_pairs = 100

    # Generate files and pre-cache fingerprints
    files, _ = generate_files(tmpdir, count=n_pairs)
    proc = precompute_fingerprints(analysis_service, similarity_service, files)

    # Select 100 pairs (use first 50 files to create 100 pairs)
    pairs = []
    for i in range(min(50, len(files))):
        for j in range(i + 1, min(50, len(files))):
            pairs.append((files[i], files[j]))
            if len(pairs) >= n_pairs:
                break
        if len(pairs) >= n_pairs:
            break
    pairs = pairs[:n_pairs]

    # Warm-up: run a few pairs to ensure everything is loaded
    for _ in range(5):
        result_service.process_pair(pairs[0][0], pairs[0][1], "python", "warmup")

    # Timed run
    start = time.time()
    for a, b in pairs:
        result = result_service.process_pair(a, b, "python", "throughput_test")
        assert result["ast_similarity"] is not None
    elapsed = time.time() - start

    throughput = n_pairs / elapsed
    print(f"  Throughput: {throughput:.2f} pairs/sec")
    print(f"  Total time: {elapsed:.2f}s for {n_pairs} pairs")

    assert throughput >= THRESHOLDS["pairs_per_second_min"], (
        f"Throughput too low: {throughput:.2f} < {THRESHOLDS['pairs_per_second_min']}"
    )
    assert elapsed <= THRESHOLDS["analysis_100_pairs_max_seconds"], (
        f"Analysis took too long: {elapsed:.2f}s > {THRESHOLDS['analysis_100_pairs_max_seconds']}s"
    )

    print("  ✓ Throughput test passed")


def test_indexing_performance(analysis_service, similarity_service, tmpdir):
    """Test 3: Indexing 30 files should be fast."""
    print("\n[Test 3] Indexing performance...")
    files, _ = generate_files(tmpdir, count=30)

    # Clear index
    inverted_index.clear_all()

    proc = precompute_fingerprints(analysis_service, similarity_service, files)

    # Measure time for ensure_files_indexed (already called in precompute, so it's cached)
    # To test raw indexing, we need clear index and measure again
    inverted_index.clear_all()

    start = time.time()
    proc.ensure_files_indexed(files, "python", "indexing_test")
    elapsed = time.time() - start

    print(f"  Indexing 30 files: {elapsed:.2f}s")
    assert elapsed < THRESHOLDS["indexing_30_files_max_seconds"], (
        f"Indexing too slow: {elapsed:.2f}s > {THRESHOLDS['indexing_30_files_max_seconds']}s"
    )

    print("  ✓ Indexing performance test passed")


def test_pair_generation_efficiency(analysis_service, similarity_service, tmpdir):
    """Test 4: Pair generation should scale reasonably."""
    print("\n[Test 4] Pair generation efficiency...")
    # Generate 50 files
    files, _ = generate_files(tmpdir, count=50)

    # Index them first
    proc = precompute_fingerprints(analysis_service, similarity_service, files)

    # Time intra-task pair generation
    start = time.time()
    intra_pairs = proc.find_intra_task_pairs(files, "python", "perf_test")
    intra_time = time.time() - start

    # Time cross-task pair generation (new vs existing)
    new_files = files[:10]
    existing_files = files[10:]
    start = time.time()
    cross_pairs = proc.find_cross_task_pairs(new_files, existing_files, "python", "perf_test")
    cross_time = time.time() - start

    print(f"  Intra-task pairs: {len(intra_pairs)} generated in {intra_time:.3f}s")
    print(f"  Cross-task pairs: {len(cross_pairs)} generated in {cross_time:.3f}s")

    # These are not hard thresholds, just sanity checks (should be sub-second)
    assert intra_time < 1.0, f"Intra-task pair gen too slow: {intra_time:.3f}s"
    assert cross_time < 1.0, f"Cross-task pair gen too slow: {cross_time:.3f}s"

    print("  ✓ Pair generation efficiency test passed")


def main():
    print("=" * 70)
    print("WORKER PERFORMANCE REGRESSION SUITE")
    print("=" * 70)
    print("\nThis suite verifies that performance remains within acceptable bounds.")
    print("Tests require a running Redis instance.\n")

    try:
        asvc, ssvc, rs, tmpdir, executor = setup_test_env()

        test_similarity_accuracy(asvc, ssvc, rs, tmpdir)
        test_analysis_throughput(asvc, ssvc, rs, tmpdir)
        test_indexing_performance(asvc, ssvc, tmpdir)
        test_pair_generation_efficiency(asvc, ssvc, tmpdir)

        print("\n" + "=" * 70)
        print("ALL REGRESSION TESTS PASSED ✓")
        print("=" * 70)

        teardown(executor, tmpdir)
        return 0

    except AssertionError as e:
        print(f"\n✗ TEST FAILED: {e}")
        teardown(executor, tmpdir)
        return 1
    except Exception as e:
        print(f"\n✗ ERROR: {e}")
        import traceback

        traceback.print_exc()
        teardown(executor, tmpdir)
        return 1


if __name__ == "__main__":
    sys.exit(main())
