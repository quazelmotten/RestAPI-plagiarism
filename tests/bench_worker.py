#!/usr/bin/env python3
"""
Worker pipeline benchmark harness.

Measures the complete worker pipeline: indexing, candidate finding, and result storage.
Supports two modes:
  --mode light  : In-memory only (no Redis/PostgreSQL needed)
  --mode full   : Live Redis + PostgreSQL (real worker pipeline)

Usage:
  # Run benchmark and save baseline
  python tests/bench_worker.py run --files 50 --output baseline.json

  # Run with dataset files
  python tests/bench_worker.py run --dataset --files 50 --output baseline.json

  # Compare two baselines
  python tests/bench_worker.py compare baseline_before.json baseline_after.json

  # Quick smoke test (10 files, light mode)
  python tests/bench_worker.py run --files 10
"""

import os
import sys
import json
import time
import hashlib
import statistics
import argparse
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
from contextlib import contextmanager
from unittest.mock import patch

# Path setup
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, ROOT_DIR)
sys.path.insert(0, os.path.join(ROOT_DIR, 'worker'))

DATASET_PATH = os.path.join(ROOT_DIR, "dataset")


# ====================================================================
# Timing + instrumentation helpers
# ====================================================================

class PhaseTimer:
    """Context manager that records wall time for a phase."""

    def __init__(self, name: str, results: dict):
        self.name = name
        self.results = results
        self.start = None

    def __enter__(self):
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc):
        self.results[self.name] = time.perf_counter() - self.start


class RedisInstrumenter:
    """Wraps a Redis client to count commands and round-trips."""

    def __init__(self, client):
        self.client = client
        self.commands = 0
        self.pipeline_batches = 0
        self.pipeline_commands = 0

    @contextmanager
    def instrument(self):
        """Patch the Redis client to count operations."""
        orig_execute = self.client.pipeline().__class__.execute
        orig_sadd = self.client.sadd
        orig_smembers = self.client.smembers
        orig_scard = self.client.scard

        instrumenter = self

        def counted_execute(pipe_self, *a, **kw):
            cmds = len(pipe_self.command_stack) if hasattr(pipe_self, 'command_stack') else 0
            instrumenter.pipeline_batches += 1
            instrumenter.pipeline_commands += cmds
            instrumenter.commands += 1
            return orig_execute(pipe_self, *a, **kw)

        def counted_sadd(*a, **kw):
            instrumenter.commands += 1
            return orig_sadd(*a, **kw)

        def counted_smembers(*a, **kw):
            instrumenter.commands += 1
            return orig_smembers(*a, **kw)

        def counted_scard(*a, **kw):
            instrumenter.commands += 1
            return orig_scard(*a, **kw)

        pipe_cls = self.client.pipeline().__class__
        patches = [
            patch.object(pipe_cls, 'execute', counted_execute),
            patch.object(self.client.__class__, 'sadd', counted_sadd),
            patch.object(self.client.__class__, 'smembers', counted_smembers),
            patch.object(self.client.__class__, 'scard', counted_scard),
        ]
        for p in patches:
            p.start()
        try:
            yield self
        finally:
            for p in patches:
                p.stop()

    def reset(self):
        self.commands = 0
        self.pipeline_batches = 0
        self.pipeline_commands = 0

    @property
    def round_trips(self):
        """Effective round-trips = standalone commands + pipeline batches."""
        return self.commands - self.pipeline_batches + self.pipeline_batches


def percentile(data, p):
    if not data:
        return 0.0
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]


# ====================================================================
# File preparation
# ====================================================================

def get_dataset_files(n: int, min_size: int = 50) -> List[str]:
    """Get N real Python files from the dataset directory."""
    files = []
    if os.path.exists(DATASET_PATH):
        for fname in sorted(os.listdir(DATASET_PATH)):
            if fname.endswith('.py'):
                fpath = os.path.join(DATASET_PATH, fname)
                if os.path.getsize(fpath) >= min_size:
                    files.append(fpath)
                    if len(files) >= n:
                        break
    return files


def generate_synthetic_files(n: int, tmpdir: str) -> List[str]:
    """Generate synthetic Python files with varying complexity."""
    import random
    random.seed(42)

    files = []
    for i in range(n):
        path = os.path.join(tmpdir, f"file_{i:04d}.py")
        # Vary file sizes to simulate realistic workload
        n_funcs = random.randint(2, 15)
        lines = [f'"""Module {i} - generated for benchmarking."""\n', '\n']
        for j in range(n_funcs):
            n_params = random.randint(1, 5)
            params = ', '.join(f'p{k}' for k in range(n_params))
            body_lines = random.randint(3, 20)
            lines.append(f'def func_{i}_{j}({params}):\n')
            for k in range(body_lines):
                indent = '    ' * random.randint(1, 3)
                lines.append(f'{indent}result_{k} = {params.split(", ")[0] if params else "0"} + {k}\n')
            lines.append(f'    return result_{body_lines - 1}\n\n')

        # Add some class definitions
        for c in range(random.randint(0, 3)):
            lines.append(f'class Class_{i}_{c}:\n')
            lines.append(f'    def __init__(self):\n')
            lines.append(f'        self.value = {i}\n\n')

        with open(path, 'w') as f:
            f.writelines(lines)
        files.append(path)

    return files


def prepare_file_info(file_path: str, file_id: int, task_id: str) -> Dict[str, Any]:
    """Create a file info dict matching the worker's expected format."""
    with open(file_path, 'rb') as f:
        content = f.read()
    file_hash = hashlib.sha256(content).hexdigest()
    return {
        'id': str(file_id),
        'task_id': task_id,
        'file_hash': file_hash,
        'hash': file_hash,
        'file_path': file_path,
        'path': file_path,
        'filename': os.path.basename(file_path),
        'language': 'python',
    }


# ====================================================================
# Benchmark phases
# ====================================================================

def bench_indexing(
    files: List[Dict[str, Any]],
    language: str,
    cache,
    index,
    timings: dict,
    per_file: list,
) -> Dict[str, Any]:
    """
    Phase 1: Fingerprint + index all files.
    Returns stats about the indexing phase.
    """
    from plagiarism_core.fingerprints import (
        tokenize_with_tree_sitter,
        compute_fingerprints,
        winnow_fingerprints,
        compute_and_winnow,
        parse_file_once,
        tokenize_and_hash_ast,
    )

    total_tokens = 0
    total_fps = 0
    total_ast = 0
    file_latencies = []

    with PhaseTimer("indexing", timings):
        for fi in files:
            t0 = time.perf_counter()

            # Single parse + single tree walk + single fingerprint pass
            tree, _ = parse_file_once(fi['file_path'], language)
            tokens, ast_hashes = tokenize_and_hash_ast(fi['file_path'], language, tree=tree)
            fps = compute_and_winnow(tokens)

            fps_for_storage = [
                {'hash': fp['hash'], 'start': tuple(fp['start']), 'end': tuple(fp['end'])}
                for fp in fps
            ]

            cache.batch_cache([(fi['file_hash'], fps_for_storage, ast_hashes)])
            index.add_file_fingerprints(fi['file_hash'], fps_for_storage, language)

            elapsed = time.perf_counter() - t0
            file_latencies.append(elapsed)
            per_file.append({'file': fi['filename'], 'index_ms': elapsed * 1000})

            total_tokens += len(tokens)
            total_fps += len(fps)
            total_ast += len(ast_hashes)

    return {
        'files_indexed': len(files),
        'total_tokens': total_tokens,
        'total_fingerprints': total_fps,
        'total_ast_hashes': total_ast,
        'avg_tokens_per_file': total_tokens / len(files) if files else 0,
        'avg_fps_per_file': total_fps / len(files) if files else 0,
        'file_latency_p50_ms': percentile(file_latencies, 50) * 1000,
        'file_latency_p95_ms': percentile(file_latencies, 95) * 1000,
    }


def bench_candidate_finding(
    files: List[Dict[str, Any]],
    language: str,
    index,
    timings: dict,
    per_file: list,
) -> Dict[str, Any]:
    """
    Phase 2: Find candidate pairs via inverted index.
    Returns stats about candidate finding.
    """
    from worker.services.candidate_service import CandidateService

    svc = CandidateService(index)

    lookup_latencies = []

    with PhaseTimer("candidate_finding", timings):
        pairs = svc.find_candidate_pairs(
            files_a=files,
            language=language,
            deduplicate=True,
        )

    # Per-file lookup timing (intra only)
    for i, fi in enumerate(files):
        t0 = time.perf_counter()
        fps = index.get_file_fingerprints(fi['file_hash'], language)
        if fps:
            _ = index.find_candidates(fps, language)
        elapsed = time.perf_counter() - t0
        lookup_latencies.append(elapsed)
        if i < len(per_file):
            per_file[i]['candidate_lookup_ms'] = elapsed * 1000

    return {
        'candidate_pairs_found': len(pairs),
        'lookup_latency_p50_ms': percentile(lookup_latencies, 50) * 1000,
        'lookup_latency_p95_ms': percentile(lookup_latencies, 95) * 1000,
    }


def bench_candidate_finding_cross(
    files_new: List[Dict[str, Any]],
    files_existing: List[Dict[str, Any]],
    language: str,
    index,
    timings: dict,
) -> Dict[str, Any]:
    """Phase 2b: Cross-task candidate finding."""
    from worker.services.candidate_service import CandidateService

    svc = CandidateService(index)

    with PhaseTimer("candidate_finding_cross", timings):
        pairs = svc.find_candidate_pairs(
            files_a=files_new,
            files_b=files_existing,
            language=language,
            deduplicate=False,
        )

    return {
        'cross_pairs_found': len(pairs),
    }


def bench_result_storage(
    task_id: str,
    pairs: List[Tuple[Dict, Dict, float]],
    repository,
    timings: dict,
) -> Dict[str, Any]:
    """Phase 3: Bulk insert results."""
    from worker.services.result_service import ResultService

    svc = ResultService(repository)

    with PhaseTimer("result_storage", timings):
        svc.store_similarity_scores(task_id, pairs, batch_size=100)

    return {
        'results_stored': len(pairs),
    }


# ====================================================================
# Main benchmark runner
# ====================================================================

def run_benchmark(args) -> dict:
    """Run the full benchmark and return results dict."""

    mode = args.mode
    n_files = args.files
    language = args.language
    use_dataset = args.dataset
    seed = args.seed

    import random
    random.seed(seed)

    print(f"\n{'='*70}")
    print(f"WORKER PIPELINE BENCHMARK")
    print(f"{'='*70}")
    print(f"  Mode:     {mode}")
    print(f"  Files:    {n_files}")
    print(f"  Language: {language}")
    print(f"  Dataset:  {'real' if use_dataset else 'synthetic'}")
    print(f"  Seed:     {seed}")

    # --- Setup infrastructure ---
    tmpdir = tempfile.mkdtemp(prefix="bench_worker_")
    redis_instrumenter = None

    try:
        if mode == 'light':
            from tests.bench_inmemory import (
                InMemoryFingerprintCache,
                InMemoryCandidateIndex,
                InMemoryTaskRepository,
            )
            cache = InMemoryFingerprintCache()
            index = InMemoryCandidateIndex(min_overlap_threshold=0.15)
            repository = InMemoryTaskRepository()
            print(f"  Infra:    in-memory (no Redis/PG)")
        else:
            # Full mode: use real Redis + PostgreSQL
            from worker.dependencies import get_redis_client, get_cache, get_index, get_repository
            redis_client = get_redis_client()
            redis_client.ping()
            cache = get_cache()
            index = get_index()
            repository = get_repository()
            redis_instrumenter = RedisInstrumenter(redis_client)
            print(f"  Infra:    Redis + PostgreSQL (live)")

        # --- Prepare files ---
        if use_dataset:
            file_paths = get_dataset_files(n_files)
            if len(file_paths) < n_files:
                print(f"  Warning: only {len(file_paths)} dataset files available (requested {n_files})")
                n_files = len(file_paths)
        else:
            file_paths = generate_synthetic_files(n_files, tmpdir)

        task_id = f"bench_{int(time.time())}"
        files = [prepare_file_info(fp, i, task_id) for i, fp in enumerate(file_paths)]

        print(f"  Prepared: {len(files)} files")
        print(f"  Sizes:    {min(os.path.getsize(f['file_path']) for f in files)}-"
              f"{max(os.path.getsize(f['file_path']) for f in files)} bytes")
        print()

        # --- Run benchmarks ---
        timings = {}
        per_file = []
        results = {}

        # Phase 1: Indexing
        print("  Phase 1: Indexing files...")
        if redis_instrumenter:
            redis_instrumenter.reset()
            with redis_instrumenter.instrument():
                idx_stats = bench_indexing(files, language, cache, index, timings, per_file)
            idx_stats['redis_commands'] = redis_instrumenter.commands
            idx_stats['redis_pipeline_batches'] = redis_instrumenter.pipeline_batches
        else:
            idx_stats = bench_indexing(files, language, cache, index, timings, per_file)

        idx_stats['duration_s'] = timings['indexing']
        idx_stats['files_per_sec'] = len(files) / timings['indexing'] if timings['indexing'] > 0 else 0
        results['indexing'] = idx_stats
        print(f"    {idx_stats['files_per_sec']:.1f} files/sec  "
              f"| {idx_stats['avg_fps_per_file']:.0f} fps/file  "
              f"| {timings['indexing']:.3f}s")

        # Phase 2: Candidate finding (intra-task)
        print("  Phase 2: Finding candidate pairs...")
        if redis_instrumenter:
            redis_instrumenter.reset()
            with redis_instrumenter.instrument():
                cand_stats = bench_candidate_finding(files, language, index, timings, per_file)
            cand_stats['redis_commands'] = redis_instrumenter.commands
            cand_stats['redis_pipeline_batches'] = redis_instrumenter.pipeline_batches
        else:
            cand_stats = bench_candidate_finding(files, language, index, timings, per_file)

        cand_stats['duration_s'] = timings['candidate_finding']
        total_pairs = cand_stats['candidate_pairs_found']
        cand_stats['pairs_per_sec'] = total_pairs / timings['candidate_finding'] if timings['candidate_finding'] > 0 else 0
        results['candidate_finding'] = cand_stats
        print(f"    {total_pairs} pairs  "
              f"| {cand_stats['pairs_per_sec']:.1f} pairs/sec  "
              f"| {timings['candidate_finding']:.3f}s")

        # Phase 2b: Cross-task candidate finding (half existing, half new)
        if len(files) >= 4:
            print("  Phase 2b: Cross-task candidate finding...")
            mid = len(files) // 2
            existing_files = files[:mid]
            new_files = files[mid:]

            if redis_instrumenter:
                redis_instrumenter.reset()
                with redis_instrumenter.instrument():
                    cross_stats = bench_candidate_finding_cross(
                        new_files, existing_files, language, index, timings
                    )
                cross_stats['redis_commands'] = redis_instrumenter.commands
            else:
                cross_stats = bench_candidate_finding_cross(
                    new_files, existing_files, language, index, timings
                )

            cross_stats['duration_s'] = timings.get('candidate_finding_cross', 0)
            results['candidate_finding_cross'] = cross_stats
            print(f"    {cross_stats['cross_pairs_found']} cross pairs  "
                  f"| {cross_stats['duration_s']:.3f}s")

        # Phase 3: Result storage
        if total_pairs > 0:
            print("  Phase 3: Result storage...")
            svc = __import__('worker.services.candidate_service', fromlist=['CandidateService']).CandidateService(index)
            pairs = svc.find_candidate_pairs(files, language=language, deduplicate=True)

            if redis_instrumenter:
                redis_instrumenter.reset()
                with redis_instrumenter.instrument():
                    store_stats = bench_result_storage(task_id, pairs, repository, timings)
                store_stats['redis_commands'] = redis_instrumenter.commands
            else:
                store_stats = bench_result_storage(task_id, pairs, repository, timings)

            store_stats['duration_s'] = timings['result_storage']
            store_stats['results_per_sec'] = len(pairs) / timings['result_storage'] if timings['result_storage'] > 0 else 0
            results['result_storage'] = store_stats
            print(f"    {store_stats['results_stored']} results  "
                  f"| {store_stats['results_per_sec']:.1f} results/sec  "
                  f"| {timings['result_storage']:.3f}s")

        # --- End-to-end summary ---
        total_time = sum(timings.values())
        e2e_pairs = results.get('candidate_finding', {}).get('candidate_pairs_found', 0)
        results['end_to_end'] = {
            'total_duration_s': total_time,
            'indexing_pct': timings.get('indexing', 0) / total_time * 100 if total_time > 0 else 0,
            'candidate_finding_pct': timings.get('candidate_finding', 0) / total_time * 100 if total_time > 0 else 0,
            'result_storage_pct': timings.get('result_storage', 0) / total_time * 100 if total_time > 0 else 0,
            'pairs_per_sec_overall': e2e_pairs / total_time if total_time > 0 else 0,
        }

        print(f"\n  {'='*50}")
        print(f"  END-TO-END: {total_time:.3f}s  |  {e2e_pairs} pairs  |  "
              f"{results['end_to_end']['pairs_per_sec_overall']:.1f} pairs/sec")
        e2e = results['end_to_end']
        print(f"    Indexing:        {e2e['indexing_pct']:.1f}%")
        print(f"    Candidate find:  {e2e['candidate_finding_pct']:.1f}%")
        print(f"    Result storage:  {e2e['result_storage_pct']:.1f}%")

        # --- Build final output ---
        import platform
        output = {
            'metadata': {
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'mode': mode,
                'files_count': len(files),
                'language': language,
                'dataset': 'real' if use_dataset else 'synthetic',
                'seed': seed,
                'hostname': platform.node(),
                'python_version': platform.python_version(),
            },
            'results': results,
            'per_file': per_file[:20] if len(per_file) > 20 else per_file,  # cap output
        }

        return output

    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


# ====================================================================
# Compare two baselines
# ====================================================================

def compare_baselines(before_path: str, after_path: str):
    """Load two baseline JSON files and print a diff table."""

    with open(before_path) as f:
        before = json.load(f)
    with open(after_path) as f:
        after = json.load(f)

    b = before['results']
    a = after['results']

    print(f"\n{'='*70}")
    print(f"BENCHMARK COMPARISON")
    print(f"{'='*70}")
    print(f"  Before: {before_path}")
    print(f"    {before['metadata']['timestamp']}")
    print(f"    {before['metadata']['files_count']} files, {before['metadata']['mode']} mode")
    print(f"  After:  {after_path}")
    print(f"    {after['metadata']['timestamp']}")
    print(f"    {after['metadata']['files_count']} files, {after['metadata']['mode']} mode")
    print()

    if before['metadata']['files_count'] != after['metadata']['files_count']:
        print("  WARNING: File counts differ between baselines!")

    def fmt_delta(before_val, after_val, higher_is_better=True):
        if before_val == 0:
            return "n/a"
        pct = (after_val - before_val) / abs(before_val) * 100
        if abs(pct) < 0.5:
            return f"~0%"
        sign = "+" if pct > 0 else ""
        emoji = ""
        if higher_is_better:
            emoji = "faster" if pct > 0 else "slower"
        else:
            emoji = "faster" if pct < 0 else "slower"
        return f"{sign}{pct:.1f}% {emoji}"

    def row(label, b_key, a_key, unit="", higher_is_better=True, section=None):
        b_val = b.get(section, {}).get(b_key, 0) if section else b.get(b_key, 0)
        a_val = a.get(section, {}).get(a_key, 0) if section else a.get(a_key, 0)
        delta = fmt_delta(b_val, a_val, higher_is_better)
        print(f"  {label:<35} {b_val:>10.2f}{unit}  ->  {a_val:>10.2f}{unit}  {delta}")

    # Indexing
    print(f"  {'─'*70}")
    print(f"  INDEXING")
    print(f"  {'─'*70}")
    row("Duration", "duration_s", "duration_s", "s", higher_is_better=False, section="indexing")
    row("Files/sec", "files_per_sec", "files_per_sec", "", section="indexing")
    row("Avg tokens/file", "avg_tokens_per_file", "avg_tokens_per_file", "", section="indexing")
    row("Avg fingerprints/file", "avg_fps_per_file", "avg_fps_per_file", "", section="indexing")
    row("File latency P50", "file_latency_p50_ms", "file_latency_p50_ms", "ms",
        higher_is_better=False, section="indexing")
    row("File latency P95", "file_latency_p95_ms", "file_latency_p95_ms", "ms",
        higher_is_better=False, section="indexing")

    if 'redis_commands' in b.get('indexing', {}) or 'redis_commands' in a.get('indexing', {}):
        row("Redis commands", "redis_commands", "redis_commands", "",
            higher_is_better=False, section="indexing")

    # Candidate finding
    print(f"\n  {'─'*70}")
    print(f"  CANDIDATE FINDING")
    print(f"  {'─'*70}")
    row("Duration", "duration_s", "duration_s", "s", higher_is_better=False, section="candidate_finding")
    row("Pairs found", "candidate_pairs_found", "candidate_pairs_found", "", section="candidate_finding")
    row("Pairs/sec", "pairs_per_sec", "pairs_per_sec", "", section="candidate_finding")
    row("Lookup P50", "lookup_latency_p50_ms", "lookup_latency_p50_ms", "ms",
        higher_is_better=False, section="candidate_finding")
    row("Lookup P95", "lookup_latency_p95_ms", "lookup_latency_p95_ms", "ms",
        higher_is_better=False, section="candidate_finding")

    if 'redis_commands' in b.get('candidate_finding', {}) or 'redis_commands' in a.get('candidate_finding', {}):
        row("Redis commands", "redis_commands", "redis_commands", "",
            higher_is_better=False, section="candidate_finding")
        row("Pipeline batches", "redis_pipeline_batches", "redis_pipeline_batches", "",
            higher_is_better=False, section="candidate_finding")

    # Result storage
    if 'result_storage' in b or 'result_storage' in a:
        print(f"\n  {'─'*70}")
        print(f"  RESULT STORAGE")
        print(f"  {'─'*70}")
        row("Duration", "duration_s", "duration_s", "s", higher_is_better=False, section="result_storage")
        row("Results stored", "results_stored", "results_stored", "", section="result_storage")
        row("Results/sec", "results_per_sec", "results_per_sec", "", section="result_storage")

    # End-to-end
    print(f"\n  {'─'*70}")
    print(f"  END-TO-END")
    print(f"  {'─'*70}")
    row("Total duration", "total_duration_s", "total_duration_s", "s",
        higher_is_better=False, section="end_to_end")
    row("Overall pairs/sec", "pairs_per_sec_overall", "pairs_per_sec_overall", "", section="end_to_end")

    print()


# ====================================================================
# CLI
# ====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Worker pipeline benchmark harness",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Quick test (10 synthetic files, light mode)
  python tests/bench_worker.py run --files 10

  # Save a baseline
  python tests/bench_worker.py run --files 50 --output baseline_before.json

  # After making changes, save another baseline
  python tests/bench_worker.py run --files 50 --output baseline_after.json

  # Compare
  python tests/bench_worker.py compare baseline_before.json baseline_after.json

  # Use real dataset files
  python tests/bench_worker.py run --dataset --files 50 --output baseline.json

  # Use live Redis + PostgreSQL
  python tests/bench_worker.py run --mode full --files 50 --output baseline.json
        """,
    )

    sub = parser.add_subparsers(dest='command', required=True)

    # run subcommand
    run_parser = sub.add_parser('run', help='Run benchmark and optionally save baseline')
    run_parser.add_argument('--files', type=int, default=20, help='Number of files (default: 20)')
    run_parser.add_argument('--mode', choices=['light', 'full'], default='light',
                            help='light=in-memory, full=Redis+PG (default: light)')
    run_parser.add_argument('--language', default='python', help='Language (default: python)')
    run_parser.add_argument('--dataset', action='store_true', help='Use real dataset files')
    run_parser.add_argument('--seed', type=int, default=42, help='Random seed (default: 42)')
    run_parser.add_argument('--output', '-o', type=str, default=None,
                            help='Save results to JSON file (for later comparison)')

    # compare subcommand
    cmp_parser = sub.add_parser('compare', help='Compare two baseline JSON files')
    cmp_parser.add_argument('before', help='Before baseline JSON file')
    cmp_parser.add_argument('after', help='After baseline JSON file')

    args = parser.parse_args()

    if args.command == 'run':
        results = run_benchmark(args)

        if args.output:
            with open(args.output, 'w') as f:
                json.dump(results, f, indent=2)
            print(f"  Saved to: {args.output}")

    elif args.command == 'compare':
        compare_baselines(args.before, args.after)


if __name__ == '__main__':
    main()
