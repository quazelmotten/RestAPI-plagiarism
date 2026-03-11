#!/usr/bin/env python3
"""
Benchmark analyzer.Start() speed.
Measures pairs/sec and latency for plagiarism analysis.
"""

import os
import sys
import time
import statistics
from pathlib import Path
from itertools import combinations

# Setup paths
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
sys.path.insert(0, root_dir)

from cli.analyzer import Analyzer

DATASET_PATH = os.path.join(root_dir, "dataset")
NUM_ITERATIONS = 10  # Run each pair multiple times for stats
SAMPLE_PAIRS = 20    # Number of random pairs to benchmark


def get_sample_files(num_files=None):
    """Get sample Python files from dataset."""
    files = []
    if os.path.exists(DATASET_PATH):
        for i in range(1, 40):
            f = os.path.join(DATASET_PATH, f"file_{i}.py")
            if os.path.exists(f):
                files.append(f)
    if not files:
        # Fallback: create tiny synthetic files
        print("Warning: No dataset found, using synthetic test files")
        return create_synthetic_files()
    
    if num_files:
        files = files[:num_files]
    return files


def create_synthetic_files():
    """Create tiny synthetic test files if no dataset exists."""
    tmp_dir = os.path.join(root_dir, "tests", "tmp_synthetic")
    os.makedirs(tmp_dir, exist_ok=True)
    
    files = []
    # Create simple Python files
    for i in range(5):
        path = os.path.join(tmp_dir, f"synthetic_{i}.py")
        with open(path, 'w') as f:
            f.write(f"def func_{i}():\n    return {i}\n")
        files.append(path)
    return files


def benchmark_pair(file1, file2, language='python', iterations=1):
    """Benchmark a single pair, returning list of timings."""
    analyzer = Analyzer()
    timings = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        result = analyzer.Start(file1, file2, language)
        elapsed = time.perf_counter() - start
        timings.append(elapsed)
    
    return timings, result


def main():
    print("="*60)
    print("Analyzer.Start() Benchmark")
    print("="*60)
    
    files = get_sample_files()
    print(f"\nUsing {len(files)} files")
    
    if len(files) < 2:
        print("Need at least 2 files to benchmark")
        return
    
    # Generate pairs
    pairs = list(combinations(files, 2))
    if len(pairs) > SAMPLE_PAIRS:
        pairs = pairs[:SAMPLE_PAIRS]
    
    print(f"Benchmarking {len(pairs)} pairs")
    print(f"Iterations per pair: {NUM_ITERATIONS}")
    print(f"Total analysis runs: {len(pairs) * NUM_ITERATIONS}\n")
    
    all_timings = []
    cache_hits = 0
    
    for idx, (f1, f2) in enumerate(pairs, 1):
        print(f"[{idx}/{len(pairs)}] Benchmarking {os.path.basename(f1)} vs {os.path.basename(f2)}...", end=" ", flush=True)
        
        try:
            timings, result = benchmark_pair(f1, f2, iterations=NUM_ITERATIONS)
            all_timings.extend(timings)
            
            # Check if result was from cache (should not be in this benchmark as we use fresh Analyzer each time)
            avg = statistics.mean(timings)
            print(f"avg={avg:.4f}s")
        except Exception as e:
            print(f"ERROR: {e}")
    
    if all_timings:
        print("\n" + "="*60)
        print("RESULTS")
        print("="*60)
        
        mean_time = statistics.mean(all_timings)
        median_time = statistics.median(all_timings)
        min_time = min(all_timings)
        max_time = max(all_timings)
        total_time = sum(all_timings)
        total_pairs = len(all_timings)
        pairs_per_sec = total_pairs / total_time if total_time > 0 else 0
        
        print(f"Total pairs analyzed: {total_pairs}")
        print(f"Total time: {total_time:.2f}s")
        print(f"Mean latency: {mean_time:.4f}s")
        print(f"Median latency: {median_time:.4f}s")
        print(f"Min latency: {min_time:.4f}s")
        print(f"Max latency: {max_time:.4f}s")
        print(f"Throughput: {pairs_per_sec:.2f} pairs/sec")
        
        # Percentiles
        if len(all_timings) > 1:
            p95 = sorted(all_timings)[int(len(all_timings) * 0.95)]
            p99 = sorted(all_timings)[int(len(all_timings) * 0.99)]
            print(f"P95 latency: {p95:.4f}s")
            print(f"P99 latency: {p99:.4f}s")
        
        print("\n" + "="*60)
        print("RECOMMENDATION")
        print("="*60)
        if pairs_per_sec >= 10:
            print("✅ Analyzer is fast enough. Optimization focus should be elsewhere.")
        elif pairs_per_sec >= 5:
            print("⚠️  Analyzer is moderate speed. Consider profiling if it's the bottleneck.")
        else:
            print("❌ Analyzer is slow. This is likely the bottleneck in your pipeline.")
            print("   Consider: optimizing tree-sitter usage, caching fingerprints,")
            print("   or parallelizing analysis across multiple processes.")


if __name__ == "__main__":
    main()
