#!/usr/bin/env python3
"""
Comprehensive benchmark: Old (AST) vs New (FP overlap) on real dataset files.

Measures:
  - Speed: pairs/sec, latency per pair
  - Accuracy: correlation, agreement, detection rates per clone type
  - Distribution: similarity score buckets for both methods
"""

import os
import sys
import time
import statistics
import random
import argparse
import tempfile
import shutil
from pathlib import Path
from itertools import combinations
from collections import Counter

# Setup paths
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, root_dir)
sys.path.insert(0, os.path.join(root_dir, 'worker'))
sys.path.insert(0, os.path.join(root_dir, 'tests', 'plagiarism'))

from cli.analyzer import (
    tokenize_with_tree_sitter,
    compute_fingerprints,
    winnow_fingerprints,
    extract_ast_hashes,
    ast_similarity,
    analyze_plagiarism,
)
from py_clone_generator import CloneGenerator

DATASET_PATH = "/home/bobbybrown/RestAPI-plagiarism/dataset"


def get_dataset_files(max_files=None, min_size=50):
    """Get real Python files from dataset."""
    files = []
    for f in sorted(Path(DATASET_PATH).glob("*.py")):
        if f.stat().st_size >= min_size:
            files.append(str(f))
            if max_files and len(files) >= max_files:
                break
    return files


def prepare_file(path):
    """Extract fingerprints and AST hashes for a file."""
    tokens = tokenize_with_tree_sitter(path, 'python')
    fps = winnow_fingerprints(compute_fingerprints(tokens))
    ast_hashes = extract_ast_hashes(path, 'python', min_depth=3)
    return fps, ast_hashes


def fp_similarity(fps_a, fps_b):
    """New method: Jaccard on fingerprint hash sets."""
    ha = {str(fp['hash']) for fp in fps_a}
    hb = {str(fp['hash']) for fp in fps_b}
    inter = len(ha & hb)
    union = len(ha | hb)
    return inter / union if union else 0.0


def categorize(sim):
    """Categorize similarity into buckets."""
    if sim >= 0.95:
        return "exact"
    elif sim >= 0.80:
        return "high"
    elif sim >= 0.50:
        return "medium"
    elif sim >= 0.30:
        return "low"
    else:
        return "none"


# ================================================================
# BENCHMARK 1: Speed on random pairs from dataset
# ================================================================
def benchmark_speed(files, n_pairs, seed=42):
    """Compare speed of old vs new pipeline on real dataset pairs."""
    random.seed(seed)
    all_pairs = list(combinations(files, 2))
    if len(all_pairs) > n_pairs:
        pairs = random.sample(all_pairs, n_pairs)
    else:
        pairs = all_pairs

    print(f"  Benchmarking {len(pairs)} pairs from {len(files)} files")

    # Pre-compute fingerprints for all files
    print("  Pre-computing fingerprints...")
    t0 = time.perf_counter()
    file_fps = {}
    file_ast = {}
    for f in files:
        fps, ast = prepare_file(f)
        file_fps[f] = fps
        file_ast[f] = ast
    index_time = time.perf_counter() - t0
    print(f"  Indexing: {index_time:.2f}s ({len(files)/index_time:.0f} files/sec)")

    # OLD pipeline: AST similarity + full analysis (fragment building etc.)
    from cli.analyzer import find_paired_occurrences, build_fragments, squash_fragments, index_fingerprints, compute_similarity_metrics

    print("  Running OLD pipeline (AST + fragments)...")
    old_times = []
    for f1, f2 in pairs:
        t0 = time.perf_counter()
        # AST similarity
        sim = ast_similarity(file_ast[f1], file_ast[f2])
        # If above threshold, do fragment building (like real pipeline)
        if sim >= 0.30:
            idx1 = index_fingerprints(file_fps[f1])
            idx2 = index_fingerprints(file_fps[f2])
            occurrences = find_paired_occurrences(idx1, idx2)
            fragments = build_fragments(occurrences, minimum_occurrences=1)
            metrics = compute_similarity_metrics(occurrences, len(file_fps[f1]), len(file_fps[f2]))
        old_times.append(time.perf_counter() - t0)

    # NEW: FP overlap only (no fragments)
    print("  Running NEW pipeline (FP overlap only)...")
    new_times = []
    for f1, f2 in pairs:
        t0 = time.perf_counter()
        sim = fp_similarity(file_fps[f1], file_fps[f2])
        new_times.append(time.perf_counter() - t0)

    old_total = sum(old_times)
    new_total = sum(new_times)

    return {
        "n_pairs": len(pairs),
        "old": {
            "total_s": old_total,
            "mean_ms": statistics.mean(old_times) * 1000,
            "pairs_per_sec": len(pairs) / old_total if old_total > 0 else 0,
        },
        "new": {
            "total_s": new_total,
            "mean_ms": statistics.mean(new_times) * 1000,
            "pairs_per_sec": len(pairs) / new_total if new_total > 0 else 0,
        },
        "speedup": (len(pairs) / new_total) / (len(pairs) / old_total) if old_total > 0 and new_total > 0 else 0,
    }


# ================================================================
# BENCHMARK 2: Accuracy on synthetic clones
# ================================================================
def benchmark_accuracy(files, n_source, clone_types, seed=42):
    """Compare accuracy of old vs new on synthetic clones."""
    random.seed(seed)
    generator = CloneGenerator()

    source_files = files[:n_source]

    results = {
        "old": {t: {"similarities": [], "detected": 0, "total": 0} for t in clone_types},
        "new": {t: {"similarities": [], "detected": 0, "total": 0} for t in clone_types},
    }

    THRESHOLD = 0.30

    for source_path in source_files:
        with open(source_path) as f:
            source_code = f.read()

        source_fps, source_ast = prepare_file(source_path)

        for clone_type in clone_types:
            try:
                if clone_type == 1:
                    clones = generator.generate_type1(source_code, clone_num=1)
                elif clone_type == 2:
                    clones = generator.generate_type2(source_code, clone_num=1)
                elif clone_type == 3:
                    clones = generator.generate_type3(source_code, clone_num=1)
                elif clone_type == 4:
                    clones = generator.generate_type4(source_code, clone_num=1)
                elif clone_type == 5:
                    clones = generator.generate_type5(source_code, clone_num=1)
                else:
                    continue
            except Exception:
                continue

            for clone_code in clones:
                # Write clone to temp file
                with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as tmp:
                    tmp.write(clone_code)
                    clone_path = tmp.name

                try:
                    clone_fps, clone_ast = prepare_file(clone_path)

                    # OLD: AST similarity
                    old_sim = ast_similarity(source_ast, clone_ast)
                    results["old"][clone_type]["similarities"].append(old_sim)
                    results["old"][clone_type]["total"] += 1
                    if old_sim >= THRESHOLD:
                        results["old"][clone_type]["detected"] += 1

                    # NEW: FP overlap
                    new_sim = fp_similarity(source_fps, clone_fps)
                    results["new"][clone_type]["similarities"].append(new_sim)
                    results["new"][clone_type]["total"] += 1
                    if new_sim >= THRESHOLD:
                        results["new"][clone_type]["detected"] += 1
                finally:
                    os.unlink(clone_path)

    return results


# ================================================================
# BENCHMARK 3: Correlation on random pairs
# ================================================================
def benchmark_correlation(files, n_pairs, seed=42):
    """Measure correlation between old and new scores on real pairs."""
    random.seed(seed)
    all_pairs = list(combinations(files, 2))
    if len(all_pairs) > n_pairs:
        pairs = random.sample(all_pairs, n_pairs)
    else:
        pairs = all_pairs

    file_data = {}
    for f in files:
        fps, ast = prepare_file(f)
        file_data[f] = (fps, ast)

    old_scores = []
    new_scores = []

    for f1, f2 in pairs:
        fps1, ast1 = file_data[f1]
        fps2, ast2 = file_data[f2]
        old_sim = ast_similarity(ast1, ast2)
        new_sim = fp_similarity(fps1, fps2)
        old_scores.append(old_sim)
        new_scores.append(new_sim)

    # Compute Pearson correlation
    n = len(old_scores)
    if n < 2:
        return {"correlation": 0, "n_pairs": n}

    mean_old = sum(old_scores) / n
    mean_new = sum(new_scores) / n
    cov = sum((o - mean_old) * (nw - mean_new) for o, nw in zip(old_scores, new_scores)) / n
    std_old = (sum((o - mean_old) ** 2 for o in old_scores) / n) ** 0.5
    std_new = (sum((nw - mean_new) ** 2 for nw in new_scores) / n) ** 0.5

    correlation = cov / (std_old * std_new) if std_old > 0 and std_new > 0 else 0

    # Rank agreement (Spearman-like): do they rank pairs the same way?
    ranked_old = sorted(range(n), key=lambda i: old_scores[i], reverse=True)
    ranked_new = sorted(range(n), key=lambda i: new_scores[i], reverse=True)
    rank_diff = sum(abs(ranked_old.index(i) - ranked_new.index(i)) for i in range(n))
    max_rank_diff = n * n / 2 if n % 2 == 0 else (n * n - 1) / 2
    rank_agreement = 1 - (rank_diff / max_rank_diff) if max_rank_diff > 0 else 1

    # Bucket agreement
    agreements = sum(1 for o, nw in zip(old_scores, new_scores)
                     if categorize(o) == categorize(nw))

    return {
        "n_pairs": n,
        "pearson_r": correlation,
        "rank_agreement": rank_agreement,
        "bucket_agreement": agreements / n,
        "old_mean": mean_old,
        "new_mean": mean_new,
        "old_std": std_old,
        "new_std": std_new,
    }


# ================================================================
# MAIN
# ================================================================
def main():
    parser = argparse.ArgumentParser(description="Benchmark: AST vs FP overlap")
    parser.add_argument("--max-files", type=int, default=50, help="Max files to use")
    parser.add_argument("--speed-pairs", type=int, default=200, help="Pairs for speed test")
    parser.add_argument("--accuracy-files", type=int, default=20, help="Source files for accuracy test")
    parser.add_argument("--correlation-pairs", type=int, default=500, help="Pairs for correlation test")
    parser.add_argument("--clone-types", type=int, nargs="+", default=[1, 2, 3, 4, 5], help="Clone types to test")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    print("=" * 70)
    print("BENCHMARK: AST Similarity (old) vs Fingerprint Overlap (new)")
    print("=" * 70)

    files = get_dataset_files(args.max_files)
    print(f"\nDataset: {len(files)} files from {DATASET_PATH}")
    print(f"File sizes: {min(f.stat().st_size for f in map(Path, files))}-"
          f"{max(f.stat().st_size for f in map(Path, files))} bytes")

    # --- Speed benchmark ---
    print(f"\n{'=' * 70}")
    print("SPEED BENCHMARK")
    print("=" * 70)
    speed = benchmark_speed(files, args.speed_pairs, args.seed)

    print(f"\n  {'Metric':<25} {'Old (full pipeline)':>20} {'New (overlap only)':>20} {'Speedup':>10}")
    print(f"  {'-'*25} {'-'*20} {'-'*20} {'-'*10}")
    print(f"  {'Total time':<25} {speed['old']['total_s']:>19.2f}s {speed['new']['total_s']:>19.4f}s")
    print(f"  {'Mean latency':<25} {speed['old']['mean_ms']:>18.2f}ms {speed['new']['mean_ms']:>18.4f}ms")
    print(f"  {'Pairs/sec':<25} {speed['old']['pairs_per_sec']:>19.1f} {speed['new']['pairs_per_sec']:>19.0f} {speed['speedup']:>9.0f}x")
    print(f"\n  Scale projection (10,000 pairs):")
    old_10k = 10000 / speed['old']['pairs_per_sec']
    new_10k = 10000 / speed['new']['pairs_per_sec']
    print(f"    Old: {old_10k:.0f}s ({old_10k/60:.1f} min)")
    print(f"    New: {new_10k:.2f}s")

    # --- Correlation benchmark ---
    print(f"\n{'=' * 70}")
    print("CORRELATION BENCHMARK")
    print("=" * 70)
    corr = benchmark_correlation(files, args.correlation_pairs, args.seed)

    print(f"  Pairs analyzed: {corr['n_pairs']}")
    print(f"  Pearson correlation: {corr['pearson_r']:.4f}")
    print(f"  Rank agreement: {corr['rank_agreement']:.1%}")
    print(f"  Bucket agreement: {corr['bucket_agreement']:.1%}")
    print(f"  Old mean: {corr['old_mean']:.1%} (std: {corr['old_std']:.1%})")
    print(f"  New mean: {corr['new_mean']:.1%} (std: {corr['new_std']:.1%})")

    # --- Accuracy benchmark ---
    print(f"\n{'=' * 70}")
    print("ACCURACY BENCHMARK (synthetic clones)")
    print("=" * 70)

    type_names = {
        1: "Type 1 (whitespace/comments)",
        2: "Type 2 (renamed identifiers)",
        3: "Type 3 (reordered statements)",
        4: "Type 4 (modified logic)",
        5: "Type 5 (mixed: T1+T2+T3+T4)",
    }

    acc = benchmark_accuracy(files, args.accuracy_files, args.clone_types, args.seed)

    THRESHOLD = 0.30
    for clone_type in sorted(args.clone_types):
        name = type_names.get(clone_type, f"Type {clone_type}")
        old_data = acc["old"].get(clone_type, {})
        new_data = acc["new"].get(clone_type, {})

        if not old_data.get("similarities"):
            continue

        old_avg = statistics.mean(old_data["similarities"]) if old_data["similarities"] else 0
        new_avg = statistics.mean(new_data["similarities"]) if new_data["similarities"] else 0
        old_det = old_data["detected"] / old_data["total"] * 100 if old_data["total"] else 0
        new_det = new_data["detected"] / new_data["total"] * 100 if new_data["total"] else 0

        print(f"\n  {name} ({old_data['total']} clones):")
        print(f"    {'':<20} {'Old (AST)':>12} {'New (FP)':>12}")
        print(f"    {'Avg similarity':<20} {old_avg:>11.1%} {new_avg:>11.1%}")
        print(f"    {'Detection rate':<20} {old_det:>10.1f}% {new_det:>10.1f}%")

        # Distribution
        for bucket in ["exact", "high", "medium", "low", "none"]:
            old_count = sum(1 for s in old_data["similarities"] if categorize(s) == bucket)
            new_count = sum(1 for s in new_data["similarities"] if categorize(s) == bucket)
            if old_count > 0 or new_count > 0:
                print(f"    {bucket:>10}: {old_count:>3} / {new_count:>3}")

    # --- Summary ---
    print(f"\n{'=' * 70}")
    print("SUMMARY")
    print("=" * 70)
    print(f"  Speed: {speed['speedup']:.0f}x faster")
    print(f"  Correlation: {corr['pearson_r']:.4f} (1.0 = perfect)")
    print(f"  Rank agreement: {corr['rank_agreement']:.1%}")
    print(f"  Bucket agreement: {corr['bucket_agreement']:.1%}")
    print("=" * 70)


if __name__ == "__main__":
    main()
