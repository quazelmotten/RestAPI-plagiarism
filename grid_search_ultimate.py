#!/usr/bin/env python3
"""
Ultimate grid search over all detection thresholds.

Sweeps:
  - jaccard_t3 (Type 3 norm_jaccard threshold, default 0.55)
  - lcs_t3     (Type 3 LCS ratio threshold, default 0.95)
  - shadow_gate (Type 4 precision gate, default 0.85)

Strategy: parallel evaluation across threshold combos.
Each worker creates its own PlagiarismDetector with the given thresholds
and evaluates all 500 benchmark pairs.

Usage:
  # Exhaustive grid (560 combos, ~8 hrs single-threaded, ~1 hr with 8 workers)
  python3 grid_search_ultimate.py

  # Random sample (50 combos recommended, ~5 min with 8 workers)
  python3 grid_search_ultimate.py --random 50

  # Custom grid:
  python3 grid_search_ultimate.py \
    --jaccard 0.45,0.55,0.65 \
    --lcs 0.92,0.95,0.98 \
    --gate 0.75,0.85,0.95

  # Dry run to estimate time:
  python3 grid_search_ultimate.py --random 50 --dry-run
"""

import argparse
import itertools
import json
import random
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from functools import partial
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from plagiarism_core.detector import PlagiarismDetector

GROUND_TRUTH_FILE = Path(__file__).parent / "benchmarks" / "ground_truth.jsonl"
DEFAULT_JACCARD = [0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80]
DEFAULT_LCS = [0.85, 0.88, 0.90, 0.92, 0.94, 0.95, 0.96, 0.98]
DEFAULT_GATE = [0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]


def load_pairs(path):
    pairs = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                pairs.append(json.loads(line))
    return pairs


def evaluate_combo(pairs, jaccard_t3, lcs_t3, shadow_gate):
    """Run all pairs with one threshold combo and return metrics."""
    detector = PlagiarismDetector(
        jaccard_t3=jaccard_t3,
        lcs_t3=lcs_t3,
        shadow_jaccard_gate=shadow_gate,
    )
    tp = Counter()
    fp = Counter()
    fn = Counter()
    latencies = []

    for pair in pairs:
        expected = pair["type"]
        start = time.perf_counter()
        try:
            result = detector.detect(pair["original"], pair["clone"])
        except Exception:
            result = None
        elapsed = time.perf_counter() - start
        latencies.append(elapsed)

        if result is None or not result.matches:
            fn[expected] += 1
            continue

        detected_types = {int(m.plagiarism_type) for m in result.matches}

        for t in (1, 2, 3, 4):
            if expected == t:
                if t in detected_types:
                    tp[t] += 1
                else:
                    fn[t] += 1
            elif t in detected_types:
                fp[t] += 1

    # Per-type metrics
    f1_scores = {}
    for t in (1, 2, 3, 4):
        p = tp[t] / (tp[t] + fp[t]) if (tp[t] + fp[t]) > 0 else 0.0
        r = tp[t] / (tp[t] + fn[t]) if (tp[t] + fn[t]) > 0 else 0.0
        f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
        f1_scores[t] = f1

    overall_tp = sum(tp.values())
    overall_fp = sum(fp.values())
    overall_fn = sum(fn.values())
    overall_p = overall_tp / (overall_tp + overall_fp) if (overall_tp + overall_fp) > 0 else 0.0
    overall_r = overall_tp / (overall_tp + overall_fn) if (overall_tp + overall_fn) > 0 else 0.0
    overall_f1 = 2 * overall_p * overall_r / (overall_p + overall_r) if (overall_p + overall_r) > 0 else 0.0

    return {
        "jaccard_t3": jaccard_t3,
        "lcs_t3": lcs_t3,
        "shadow_gate": shadow_gate,
        "overall_f1": overall_f1,
        "per_type": {str(t): {"f1": f1_scores[t], "tp": tp[t], "fp": fp[t], "fn": fn[t]} for t in (1, 2, 3, 4)},
        "tp": dict(tp),
        "fp": dict(fp),
        "fn": dict(fn),
        "mean_latency": sum(latencies) / len(latencies) if latencies else 0,
    }


def format_result(r):
    return (
        f"  j={r['jaccard_t3']:.2f} lcs={r['lcs_t3']:.2f} gate={r['shadow_gate']:.2f}  "
        f"F1={r['overall_f1']:.4f}  "
        f"T1={r['per_type']['1']['f1']:.3f} T2={r['per_type']['2']['f1']:.3f} "
        f"T3={r['per_type']['3']['f1']:.3f} T4={r['per_type']['4']['f1']:.3f}  "
        f"TP={r['tp']} FP={r['fp']} FN={r['fn']}"
    )


def main():
    parser = argparse.ArgumentParser(description="Ultimate grid search over detection thresholds")
    parser.add_argument("--random", type=int, default=None, help="Number of random combos to sample")
    parser.add_argument("--processes", type=int, default=None, help="Number of parallel workers (default: cpu count)")
    parser.add_argument("--jaccard", type=str, default=None, help="Comma-separated jaccard_t3 values")
    parser.add_argument("--lcs", type=str, default=None, help="Comma-separated lcs_t3 values")
    parser.add_argument("--gate", type=str, default=None, help="Comma-separated shadow_gate values")
    parser.add_argument("--output", type=str, default="grid_search_ultimate_results.json")
    parser.add_argument("--dry-run", action="store_true", help="Print time estimate without running")
    args = parser.parse_args()

    # Load pairs
    pairs = load_pairs(GROUND_TRUTH_FILE)
    print(f"Loaded {len(pairs)} benchmark pairs.")

    # Build grid
    jaccard_values = [float(x) for x in args.jaccard.split(",")] if args.jaccard else DEFAULT_JACCARD
    lcs_values = [float(x) for x in args.lcs.split(",")] if args.lcs else DEFAULT_LCS
    gate_values = [float(x) for x in args.gate.split(",")] if args.gate else DEFAULT_GATE

    all_combos = list(itertools.product(jaccard_values, lcs_values, gate_values))

    if args.random:
        random.seed(42)
        combos = random.sample(all_combos, min(args.random, len(all_combos)))
    else:
        combos = all_combos

    total = len(combos)
    print(f"\nGrid: {len(jaccard_values)} jaccard × {len(lcs_values)} lcs × {len(gate_values)} gate = {len(all_combos)} total")
    print(f"Sampled: {total} combos")
    print(f"Default: jaccard={DEFAULT_JACCARD[DEFAULT_JACCARD.index(0.55)]} lcs={DEFAULT_LCS[DEFAULT_LCS.index(0.95)]} gate={DEFAULT_GATE[DEFAULT_GATE.index(0.85)]}")
    print()

    # Estimate time
    est_per_pair = 0.1  # seconds
    total_seconds = total * len(pairs) * est_per_pair
    print(f"Estimated single-threaded: {total_seconds:.0f}s ({total_seconds / 60:.1f} min)")

    if args.dry_run:
        return

    # Evaluate
    workers = args.processes or None  # None = cpu_count
    print(f"Workers: {workers or 'auto'}\n")
    start = time.time()
    best = {"overall_f1": -1}
    results = []

    if workers == 1:
        # Single-threaded (useful for debugging)
        for i, (j, l, g) in enumerate(combos):
            r = evaluate_combo(pairs, j, l, g)
            results.append(r)
            if r["overall_f1"] > best["overall_f1"]:
                best = r
                print(f"[{i+1}/{total}] NEW BEST: {format_result(r)}")
            elif (i + 1) % 5 == 0:
                elapsed = time.time() - start
                eta = (elapsed / (i + 1)) * (total - i - 1)
                print(f"[{i+1}/{total}] best so far: F1={best['overall_f1']:.4f}  "
                      f"({elapsed:.0f}s elapsed, ETA {eta:.0f}s)")
    else:
        # Parallel evaluation
        worker = partial(evaluate_combo, pairs)
        done = 0
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(worker, j, l, g): (j, l, g) for j, l, g in combos}
            for future in as_completed(futures):
                done += 1
                r = future.result()
                results.append(r)
                if r["overall_f1"] > best["overall_f1"]:
                    best = r
                    print(f"[{done}/{total}] NEW BEST (p={r['jaccard_t3']:.2f}/{r['lcs_t3']:.2f}/{r['shadow_gate']:.2f}): "
                          f"F1={r['overall_f1']:.4f}  T3={r['per_type']['3']['f1']:.3f} T4={r['per_type']['4']['f1']:.3f}")
                elif done % 5 == 0:
                    elapsed = time.time() - start
                    eta = (elapsed / done) * (total - done)
                    print(f"[{done}/{total}] best F1={best['overall_f1']:.4f}  "
                          f"({elapsed:.0f}s elapsed, ETA {eta:.0f}s)")

    elapsed = time.perf_counter() - start
    print(f"\n{'='*60}")
    print(f"COMPLETE in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    print(f"{'='*60}")
    print(f"\nBEST CONFIGURATION:")
    print(f"  jaccard_t3 = {best['jaccard_t3']:.2f}")
    print(f"  lcs_t3     = {best['lcs_t3']:.2f}")
    print(f"  shadow_gate = {best['shadow_gate']:.2f}")
    print(f"  Overall F1 = {best['overall_f1']:.4f}")
    for t in (1, 2, 3, 4):
        pt = best['per_type'][str(t)]
        print(f"  Type {t}: F1={pt['f1']:.3f}  TP={pt['tp']} FP={pt['fp']} FN={pt['fn']}")
    print(f"  TP={best['tp']} FP={best['fp']} FN={best['fn']}")

    # Print top 5
    results_sorted = sorted(results, key=lambda r: -r['overall_f1'])[:5]
    print(f"\nTOP 5 CONFIGURATIONS:")
    for i, r in enumerate(results_sorted, 1):
        print(f"  #{i}: {format_result(r)}")

    # Save
    output = {
        "best": best,
        "top5": results_sorted,
        "all": results,
        "grid": {
            "jaccard_values": jaccard_values,
            "lcs_values": lcs_values,
            "gate_values": gate_values,
            "total_combos": len(all_combos),
            "sampled": len(combos),
        },
        "runtime_seconds": elapsed,
    }
    with open(args.output, "w") as f:
        json.dump(output, f, indent=2)
    print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
