#!/usr/bin/env python3
"""
Accuracy test for plagiarism detection algorithm.
Tests how well the algorithm detects synthetic clones of different types.
"""

import argparse
import json
import random
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from py_clone_generator import generate_dataset

DATASET_DIR = "/home/bobbybrown/RestAPI-plagiarism/dataset"
PLAGIARISM_DIR = "/home/bobbybrown/RestAPI-plagiarism/tests/plagiarism"
CLI_PATH = "/home/bobbybrown/RestAPI-plagiarism/cli/cli.py"


def run_analyze(file1: str, file2: str, threshold: float = 0.0) -> dict[str, Any]:
    """Run the analyzer CLI and return parsed JSON result."""
    cmd = [
        "python3",
        CLI_PATH,
        "analyze",
        file1,
        file2,
        "--language",
        "python",
        "--threshold",
        str(threshold),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)

        if result.returncode != 0:
            return {"error": result.stderr, "similarity": 0}

        return json.loads(result.stdout)

    except subprocess.TimeoutExpired:
        return {"error": "Timeout", "similarity": 0}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON", "similarity": 0}
    except Exception as e:
        return {"error": str(e), "similarity": 0}


def categorize_similarity(similarity: float) -> str:
    """Categorize similarity score into buckets."""
    if similarity >= 95:
        return "exact"
    elif similarity >= 80:
        return "high"
    elif similarity >= 50:
        return "medium"
    elif similarity >= 30:
        return "low"
    else:
        return "none"


def run_accuracy_test(
    n_files: int = 20,
    n_clones: int = 1,
    file_range: tuple[int, int] = (0, 100),
    types: list[int] = None,
    threshold: float = 0.30,
    cleanup: bool = True,
    seed: int = 42,
) -> dict[str, Any]:
    """Run accuracy test on synthetic clones."""

    if types is None:
        types = [1, 2, 3, 4]
    print("=== Plagiarism Detection Accuracy Test ===")
    print(f"Files to test: {n_files}")
    print(f"Clones per file: {n_clones}")
    print(f"File range: {file_range[0]} - {file_range[1]}")
    print(f"Types: {types}")
    print(f"Threshold: {threshold}")
    print(f"Random seed: {seed}")
    print()

    # Set random seed for deterministic results
    random.seed(seed)

    dataset_path = Path(DATASET_DIR)
    output_path = Path(PLAGIARISM_DIR)

    source_files = []
    all_files = sorted(dataset_path.glob("*.py"))
    for f in all_files:
        if len(source_files) >= n_files:
            break
        with open(f) as fp:
            content = fp.read()
            if len(content) >= 50:
                source_files.append(f)

    if len(source_files) < n_files:
        print(f"Warning: Only found {len(source_files)} valid source files")

    source_files = source_files[:n_files]
    print(f"Using {len(source_files)} source files")

    print("\nGenerating clones...")
    generate_dataset(
        source_dir=DATASET_DIR,
        output_dir=PLAGIARISM_DIR,
        n=n_clones,
        file_range=(file_range[0], file_range[1]),
        types=types,
    )

    results = {"summary": {}, "by_type": {}, "details": []}

    for type_num in types:
        type_dir = output_path / f"type{type_num}"
        if not type_dir.exists():
            print(f"Warning: {type_dir} does not exist")
            continue

        type_results = {
            "total": 0,
            "similarities": [],
            "detected": 0,
            "exact": 0,
            "high": 0,
            "medium": 0,
            "low": 0,
            "none": 0,
            "errors": 0,
        }

        clone_files = sorted(type_dir.glob("*.py"))
        print(f"Testing {len(clone_files)} {type_num} clones...")

        for clone_file in clone_files:
            parts = clone_file.stem.split("_")
            if len(parts) < 3:
                continue

            # Clone filename format: {original_stem}_type{type_num}_{j+1}
            original_stem = "_".join(parts[:-2])  # Everything except last two parts
            original_file = dataset_path / f"{original_stem}.py"

            if not original_file.exists():
                continue

            analysis = run_analyze(str(original_file), str(clone_file), threshold)

            if "error" in analysis:
                type_results["errors"] += 1
                print(f"  Error analyzing {clone_file.name}: {analysis['error'][:100]}")
                continue

            similarity = analysis.get("similarity", 0)
            type_results["total"] += 1
            type_results["similarities"].append(similarity)

            category = categorize_similarity(similarity)
            type_results[category] += 1

            if similarity >= threshold * 100:
                type_results["detected"] += 1

            results["details"].append(
                {
                    "type": type_num,
                    "original": str(original_file),
                    "clone": str(clone_file),
                    "similarity": similarity,
                    "category": category,
                    "detected": similarity >= threshold * 100,
                }
            )

        if type_results["total"] > 0:
            type_results["avg_similarity"] = sum(type_results["similarities"]) / len(
                type_results["similarities"]
            )
            type_results["detection_rate"] = (
                type_results["detected"] / type_results["total"]
            ) * 100
            type_results["exact_rate"] = (type_results["exact"] / type_results["total"]) * 100
        else:
            type_results["avg_similarity"] = 0
            type_results["detection_rate"] = 0
            type_results["exact_rate"] = 0

        results["by_type"][f"type{type_num}"] = type_results

    total_tests = sum(r["total"] for r in results["by_type"].values())
    total_detected = sum(r["detected"] for r in results["by_type"].values())
    total_exact = sum(r["exact"] for r in results["by_type"].values())
    total_errors = sum(r["errors"] for r in results["by_type"].values())

    all_similarities = []
    for r in results["by_type"].values():
        all_similarities.extend(r.get("similarities", []))

    results["summary"] = {
        "total_tests": total_tests,
        "total_detected": total_detected,
        "total_exact": total_exact,
        "total_errors": total_errors,
        "overall_detection_rate": (total_detected / total_tests * 100) if total_tests > 0 else 0,
        "overall_exact_rate": (total_exact / total_tests * 100) if total_tests > 0 else 0,
        "avg_similarity": sum(all_similarities) / len(all_similarities) if all_similarities else 0,
    }

    print("\n" + "-" * 40)
    print("Analyzing results...")

    if cleanup:
        print("\nCleaning up generated clones...")
        for type_num in types:
            type_dir = output_path / f"type{type_num}"
            if type_dir.exists():
                shutil.rmtree(type_dir)

    return results


def print_results(results: dict[str, Any]):
    """Print formatted results."""
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)

    summary = results["summary"]
    print("\nOverall Statistics:")
    print(f"  Total tests: {summary['total_tests']}")
    print(f"  Total detected (>=30%): {summary['total_detected']}")
    print(f"  Total exact (>=95%): {summary['total_exact']}")
    print(f"  Errors: {summary['total_errors']}")
    print(f"  Detection rate: {summary['overall_detection_rate']:.1f}%")
    print(f"  Exact match rate: {summary['overall_exact_rate']:.1f}%")
    print(f"  Average similarity: {summary['avg_similarity']:.1f}%")

    print("\nPer-Type Breakdown:")
    print("-" * 60)

    for type_name, data in sorted(results["by_type"].items()):
        if data["total"] == 0:
            continue

        print(f"\n{type_name.upper()}:")
        print(f"  Tests: {data['total']}")
        print(f"  Errors: {data['errors']}")
        print(f"  Average similarity: {data['avg_similarity']:.1f}%")
        print(f"  Detection rate (>={data.get('threshold', 30)}%): {data['detection_rate']:.1f}%")
        print(f"  Exact rate (>=95%): {data['exact_rate']:.1f}%")
        print("  Category distribution:")
        print(f"    Exact (>=95%): {data['exact']} ({data['exact'] / data['total'] * 100:.1f}%)")
        print(f"    High (80-94%): {data['high']} ({data['high'] / data['total'] * 100:.1f}%)")
        print(
            f"    Medium (50-79%): {data['medium']} ({data['medium'] / data['total'] * 100:.1f}%)"
        )
        print(f"    Low (30-49%): {data['low']} ({data['low'] / data['total'] * 100:.1f}%)")
        print(f"    None (<30%): {data['none']} ({data['none'] / data['total'] * 100:.1f}%)")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Accuracy test for plagiarism detection algorithm")
    parser.add_argument(
        "--n-files", type=int, default=20, help="Number of files to test (default: 20)"
    )
    parser.add_argument(
        "--n-clones", type=int, default=1, help="Number of clones per file per type (default: 1)"
    )
    parser.add_argument("--start", type=int, default=0, help="Starting file index (default: 0)")
    parser.add_argument("--end", type=int, default=100, help="Ending file index (default: 100)")
    parser.add_argument(
        "--types",
        type=int,
        nargs="+",
        default=[1, 2, 3, 4],
        help="Clone types to test (default: 1 2 3 4)",
    )
    parser.add_argument(
        "--threshold", type=float, default=0.30, help="Detection threshold (default: 0.30)"
    )
    parser.add_argument(
        "--no-cleanup", action="store_true", help="Don't delete generated clones after test"
    )
    parser.add_argument(
        "--seed", type=int, default=42, help="Random seed for deterministic results (default: 42)"
    )
    parser.add_argument("--output", type=str, default=None, help="Output JSON file for results")

    args = parser.parse_args()

    results = run_accuracy_test(
        n_files=args.n_files,
        n_clones=args.n_clones,
        file_range=(args.start, args.end),
        types=args.types,
        threshold=args.threshold,
        cleanup=not args.no_cleanup,
        seed=args.seed,
    )

    print_results(results)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to {args.output}")


if __name__ == "__main__":
    main()
