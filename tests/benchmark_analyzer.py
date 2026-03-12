#!/usr/bin/env python3
"""
Benchmark analyzer.Start() speed.
Measures pairs/sec and latency for plagiarism analysis.
"""

import os
import sys
import time
import statistics
import random
import argparse
from pathlib import Path
from itertools import combinations, islice

# Setup paths
script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
sys.path.insert(0, root_dir)

from cli.analyzer import Analyzer

DATASET_PATH = "/home/bobbybrown/RestAPI-plagiarism/dataset"


def get_sample_files(num_files=None):
    """Get sample Python files from dataset."""
    files = []
    if os.path.exists(DATASET_PATH):
        # Discover all .py files in the dataset directory
        for filename in sorted(os.listdir(DATASET_PATH)):  # Sorted for determinism
            if filename.endswith('.py'):
                files.append(os.path.join(DATASET_PATH, filename))
    
    if not files:
        # Fallback: create tiny synthetic files
        print("Warning: No dataset found, using synthetic test files")
        return create_synthetic_files()
    
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
    result = None
    
    for _ in range(iterations):
        start = time.perf_counter()
        result = analyzer.Start(file1, file2, language)
        elapsed = time.perf_counter() - start
        timings.append(elapsed)
    
    return timings, result


def main():
    parser = argparse.ArgumentParser(
        description="Benchmark analyzer.Start() speed"
    )
    parser.add_argument(
        "--max-files", 
        type=int, 
        default=None,
        help="Maximum number of files to use from dataset (default: all)"
    )
    parser.add_argument(
        "--max-pairs", 
        type=int, 
        default=100,
        help="Maximum number of pairs to benchmark (default: 100)"
    )
    parser.add_argument(
        "--iterations", 
        type=int, 
        default=3,
        help="Number of iterations per pair (default: 3)"
    )
    parser.add_argument(
        "--seed", 
        type=int, 
        default=42,
        help="Random seed for deterministic results (default: 42)"
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("Analyzer.Start() Benchmark")
    print("="*60)
    
    # Set random seed for deterministic results
    random.seed(args.seed)
    
    files = get_sample_files(args.max_files)
    print(f"\nUsing {len(files)} files from dataset")
    
    if len(files) < 2:
        print("Need at least 2 files to benchmark")
        return
    
    # Generate pairs deterministically
    all_pairs = list(combinations(files, 2))
    print(f"Total possible pairs: {len(all_pairs):,}")
    
    # Limit pairs if needed
    if len(all_pairs) > args.max_pairs:
        # Use random sampling for deterministic selection
        pairs = random.sample(all_pairs, args.max_pairs)
        print(f"Sampling {args.max_pairs} pairs for benchmarking")
    else:
        pairs = all_pairs
        print(f"Benchmarking all {len(pairs):,} pairs")
    
    print(f"Iterations per pair: {args.iterations}")
    print(f"Total analysis runs: {len(pairs) * args.iterations}\n")
    
    all_timings = []
    
    for idx, (f1, f2) in enumerate(pairs, 1):
        if idx % 20 == 0 or idx == len(pairs):
            print(f"[{idx}/{len(pairs)}] Progress...", end=" ", flush=True)
        
        try:
            timings, result = benchmark_pair(f1, f2, iterations=args.iterations)
            all_timings.extend(timings)
            
            if idx <= 5 or idx % 20 == 0:  # Show first few and every 20th
                avg = statistics.mean(timings)
                print(f"avg={avg:.4f}s")
        except Exception as e:
            if idx <= 5:  # Show errors for first few pairs
                print(f"[{idx}/{len(pairs)}] ERROR: {e}")
    
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