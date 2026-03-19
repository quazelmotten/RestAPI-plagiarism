#!/usr/bin/env python3
"""
Fine-tuning algorithm for plagiarism detection parameters.
Searches for parameter combinations that optimize accuracy and match size.
"""

import os
import sys
import json
import argparse
import subprocess
import random
import itertools
from pathlib import Path
from typing import Dict, List, Tuple, Any
from collections import defaultdict
import shutil
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from py_clone_generator import generate_dataset

DATASET_DIR = Path("/home/bobbybrown/RestAPI-plagiarism/dataset")
PLAGIARISM_DIR = Path("/home/bobbybrown/RestAPI-plagiarism/tests/plagiarism")
CLI_PATH = "/home/bobbybrown/RestAPI-plagiarism/cli/cli.py"
ANALYZER_PATH = Path("/home/bobbybrown/RestAPI-plagiarism/cli/analyzer.py")

def compute_total_match_size(matches: List[Dict]) -> int:
    """Compute total size of all matching regions (in tokens/characters)."""
    total = 0
    for match in matches:
        # Approximate size from selection ranges
        f1 = match.get('file1', {})
        f2 = match.get('file2', {})
        # Use line count * average line length estimate, or just line count
        lines1 = f1.get('end_line', 0) - f1.get('start_line', 0) + 1
        lines2 = f2.get('end_line', 0) - f2.get('start_line', 0) + 1
        total += (lines1 + lines2) / 2  # Average of both files
    return total

def modify_analyzer_parameters(params: Dict[str, Any]) -> bool:
    """Modify the analyzer.py file with new parameter values by editing specific lines."""
    try:
        with open(ANALYZER_PATH, 'r') as f:
            lines = f.readlines()
        
        # Track modifications
        modified = []
        
        # compute_fingerprints line 124 (0-indexed: 123)
        if 'k' in params:
            idx = 123
            if idx < len(lines):
                k = params['k']
                # Keep the original base and mod values
                lines[idx] = f"def compute_fingerprints(tokens, k={k}, base=257, mod=10**9 + 7):\n"
                modified.append(idx)
        
        # hash_ast_subtrees line 181 (0-indexed: 180)
        if 'min_depth' in params:
            idx = 180
            if idx < len(lines):
                lines[idx] = f"def hash_ast_subtrees(root, min_depth={params['min_depth']}):\n"
                modified.append(idx)
            # extract_ast_hashes line 218 (0-indexed: 217)
            idx = 217
            if idx < len(lines):
                lines[idx] = f"def extract_ast_hashes(file_path, lang_code, min_depth={params['min_depth']}, tree=None):\n"
                modified.append(idx)
            # Replace hardcoded min_depth=3 in function calls (lines 459, 460, 554, 597, 696, 713)
            call_line_indices = [458, 459, 553, 596, 695, 712]  # 0-based
            for call_idx in call_line_indices:
                if call_idx < len(lines) and 'min_depth=3' in lines[call_idx]:
                    lines[call_idx] = lines[call_idx].replace('min_depth=3', f"min_depth={params['min_depth']}")
                    modified.append(call_idx)
        
        # build_fragments line 276 (0-indexed: 275)
        if 'minimum_occurrences' in params:
            idx = 275
            if idx < len(lines):
                lines[idx] = lines[idx].replace('minimum_occurrences=1', f"minimum_occurrences={params['minimum_occurrences']}")
                modified.append(idx)
        
        # ast_threshold in function signatures and calls
        if 'ast_threshold' in params:
            # analyze_plagiarism - the parameter line, line 442 (0-indexed: 441)
            idx = 441
            if idx < len(lines):
                lines[idx] = f"    ast_threshold={params['ast_threshold']},\n"
                modified.append(idx)
            # analyze_plagiarism_cached - line 505 (0-indexed: 504)
            idx = 504
            if idx < len(lines):
                lines[idx] = f"    ast_threshold: float = {params['ast_threshold']},\n"
                modified.append(idx)
            # analyze_plagiarism_batch - line 651 (0-indexed: 650)
            idx = 650
            if idx < len(lines):
                lines[idx] = f"    ast_threshold: float = {params['ast_threshold']},\n"
                modified.append(idx)
            # Analyzer.Start - line 772 (0-indexed: 771)
            idx = 771
            if idx < len(lines):
                lines[idx] = f"            ast_threshold={params['ast_threshold']}\n"
                modified.append(idx)
        
        # Write back
        with open(ANALYZER_PATH, 'w') as f:
            f.writelines(lines)
        
        return True
    except Exception as e:
        print(f"Error modifying analyzer: {e}")
        import traceback
        traceback.print_exc()
        return False

def run_analyze_with_params(file1: str, file2: str, threshold: float = 0.0) -> Dict[str, Any]:
    """Run the analyzer CLI with current parameters."""
    cmd = [
        "python3", CLI_PATH, "analyze",
        file1, file2,
        "--language", "python",
        "--threshold", str(threshold)
    ]
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30
        )
        
        if result.returncode != 0:
            return {"error": result.stderr, "similarity": 0, "matches": []}
        
        parsed = json.loads(result.stdout)
        # Ensure matches key exists
        if "matches" not in parsed:
            parsed["matches"] = []
        return parsed
    
    except subprocess.TimeoutExpired:
        return {"error": "Timeout", "similarity": 0, "matches": []}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON", "similarity": 0, "matches": []}
    except Exception as e:
        return {"error": str(e), "similarity": 0, "matches": []}

def run_accuracy_test_with_dataset(
    dataset_dir: Path,
    n_files: int = 10,
    n_clones: int = 1,
    file_range: Tuple[int, int] = (0, 50),
    types: List[int] = [1, 2, 3, 4],
    threshold: float = 0.30,
    cleanup: bool = True
) -> Dict[str, Any]:
    """Run accuracy test on the generated dataset with current parameters."""
    
    source_files = []
    all_files = sorted(dataset_dir.glob("*.py"))
    for f in all_files:
        if len(source_files) >= n_files:
            break
        with open(f, 'r') as fp:
            content = fp.read()
            if len(content) >= 50:
                source_files.append(f)
    
    source_files = source_files[:n_files]
    
    results = {
        "summary": {},
        "by_type": {},
        "details": []
    }
    
    for type_num in types:
        type_dir = PLAGIARISM_DIR / f"type{type_num}"
        if not type_dir.exists():
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
            "total_match_size": 0,
            "avg_match_size": 0
        }
        
        clone_files = sorted(type_dir.glob("*.py"))
        
        for clone_file in clone_files:
            parts = clone_file.stem.split("_")
            if len(parts) < 3:
                continue
            
            original_stem = "_".join(parts[:-2])
            original_file = dataset_dir / f"{original_stem}.py"
            
            if not original_file.exists():
                continue
            
            analysis = run_analyze_with_params(str(original_file), str(clone_file), threshold)
            
            if "error" in analysis:
                type_results["errors"] += 1
                continue
            
            similarity = analysis.get("similarity", 0)
            matches = analysis.get("matches", [])
            
            type_results["total"] += 1
            type_results["similarities"].append(similarity)
            
            # Categorize
            if similarity >= 95:
                type_results["exact"] += 1
            elif similarity >= 80:
                type_results["high"] += 1
            elif similarity >= 50:
                type_results["medium"] += 1
            elif similarity >= 30:
                type_results["low"] += 1
            else:
                type_results["none"] += 1
            
            if similarity >= threshold * 100:
                type_results["detected"] += 1
            
            # Calculate match size
            match_size = compute_total_match_size(matches)
            type_results["total_match_size"] += match_size
            
            results["details"].append({
                "type": type_num,
                "original": str(original_file),
                "clone": str(clone_file),
                "similarity": similarity,
                "detected": similarity >= threshold * 100,
                "match_count": len(matches),
                "match_size": match_size
            })
        
        if type_results["total"] > 0:
            type_results["avg_similarity"] = sum(type_results["similarities"]) / len(type_results["similarities"])
            type_results["detection_rate"] = (type_results["detected"] / type_results["total"]) * 100
            type_results["exact_rate"] = (type_results["exact"] / type_results["total"]) * 100
            type_results["avg_match_size"] = type_results["total_match_size"] / type_results["total"]
        else:
            type_results["avg_similarity"] = 0
            type_results["detection_rate"] = 0
            type_results["exact_rate"] = 0
            type_results["avg_match_size"] = 0
        
        results["by_type"][f"type{type_num}"] = type_results
    
    total_tests = sum(r["total"] for r in results["by_type"].values())
    total_detected = sum(r["detected"] for r in results["by_type"].values())
    total_exact = sum(r["exact"] for r in results["by_type"].values())
    total_errors = sum(r["errors"] for r in results["by_type"].values())
    total_match_size = sum(r["total_match_size"] for r in results["by_type"].values())
    
    all_similarities = []
    for r in results["by_type"].values():
        all_similarities.extend(r.get("similarities", []))
    
    results["summary"] = {
        "total_tests": total_tests,
        "total_detected": total_detected,
        "total_exact": total_exact,
        "total_errors": total_errors,
        "total_match_size": total_match_size,
        "overall_detection_rate": (total_detected / total_tests * 100) if total_tests > 0 else 0,
        "overall_exact_rate": (total_exact / total_tests * 100) if total_tests > 0 else 0,
        "avg_similarity": sum(all_similarities) / len(all_similarities) if all_similarities else 0,
        "avg_match_size": total_match_size / total_tests if total_tests > 0 else 0,
    }
    
    if cleanup:
        for type_num in types:
            type_dir = PLAGIARISM_DIR / f"type{type_num}"
            if type_dir.exists():
                shutil.rmtree(type_dir)
    
    return results

def calculate_score(results: Dict[str, Any], weight_accuracy: float = 0.6, weight_match_size: float = 0.4) -> float:
    """
    Calculate a composite score from accuracy and match size.
    Higher is better.
    """
    summary = results["summary"]
    
    detection_rate = summary["overall_detection_rate"] / 100.0
    exact_rate = summary["overall_exact_rate"] / 100.0
    avg_match_size = summary.get("avg_match_size", 0)
    
    # Normalize match size (empirically, typical range 0-1000)
    # We'll use a sigmoid to keep it between 0 and 1
    normalized_match_size = 1.0 / (1.0 + pow(2.718, -avg_match_size / 200.0))
    
    # Composite score
    accuracy_score = (detection_rate * 0.5 + exact_rate * 0.5)  # Balanced accuracy
    score = (accuracy_score * weight_accuracy) + (normalized_match_size * weight_match_size)
    
    return score

def generate_parameter_combinations() -> List[Dict[str, Any]]:
    """Generate all parameter combinations to test."""
    param_grid = {
        'k': [4, 5, 6, 7, 8],
        'window_size': [3, 4, 5, 6, 7],
        'min_depth': [2, 3, 4, 5],
        'ast_threshold': [0.20, 0.25, 0.30, 0.35, 0.40],
        'minimum_occurrences': [1, 2, 3],
    }
    
    # Generate combinations (limited subset to avoid combinatorial explosion)
    keys = list(param_grid.keys())
    values = list(param_grid.values())
    
    combinations = []
    for combination in itertools.product(*values):
        params = dict(zip(keys, combination))
        combinations.append(params)
    
    # Shuffle for diversity
    random.shuffle(combinations)
    return combinations

def print_parameter_set(params: Dict[str, Any], score: float, results: Dict[str, Any]):
    """Print detailed info about a parameter set."""
    print("\n" + "=" * 80)
    print(f"PARAMETER SET - Score: {score:.4f}")
    print("-" * 80)
    print("Parameters:")
    for key, value in params.items():
        print(f"  {key}: {value}")
    
    print("\nResults:")
    summary = results["summary"]
    print(f"  Total tests: {summary['total_tests']}")
    print(f"  Detection rate: {summary['overall_detection_rate']:.1f}%")
    print(f"  Exact rate: {summary['overall_exact_rate']:.1f}%")
    print(f"  Average similarity: {summary['avg_similarity']:.1f}%")
    print(f"  Total match size: {summary['total_match_size']:.0f}")
    print(f"  Average match size: {summary['avg_match_size']:.1f}")
    print(f"  Errors: {summary['total_errors']}")
    
    print("\nPer-Type Performance:")
    for type_name, data in sorted(results["by_type"].items()):
        if data["total"] == 0:
            continue
        print(f"  {type_name}: avg_sim={data['avg_similarity']:.1f}%, "
              f"detected={data['detection_rate']:.1f}%, "
              f"match_size={data['avg_match_size']:.1f}")

def main():
    parser = argparse.ArgumentParser(
        description="Fine-tune plagiarism detection parameters"
    )
    parser.add_argument("--n-files", type=int, default=10,
                        help="Number of files to test per run (default: 10)")
    parser.add_argument("--n-clones", type=int, default=1,
                        help="Number of clones per type per file (default: 1)")
    parser.add_argument("--max-combinations", type=int, default=50,
                        help="Maximum number of parameter combinations to test (default: 50)")
    parser.add_argument("--start", type=int, default=0,
                        help="Starting file index (default: 0)")
    parser.add_argument("--end", type=int, default=50,
                        help="Ending file index (default: 50)")
    parser.add_argument("--types", type=int, nargs="+", default=[1, 2, 3, 4],
                        help="Clone types to test (default: 1 2 3 4)")
    parser.add_argument("--threshold", type=float, default=0.30,
                        help="Detection threshold (default: 0.30)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--output", type=str, default=None,
                        help="Output JSON file for results")
    parser.add_argument("--resume", type=str, default=None,
                        help="Resume from previous results file")
    parser.add_argument("--weight-accuracy", type=float, default=0.6,
                        help="Weight for accuracy in score (default: 0.6)")
    parser.add_argument("--weight-match-size", type=float, default=0.4,
                        help="Weight for match size in score (default: 0.4)")
    parser.add_argument("--keep-dataset", action="store_true",
                        help="Keep generated dataset between runs (faster, but uses disk space)")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("PLAGIARISM DETECTION PARAMETER FINE-TUNING")
    print("=" * 80)
    print(f"Testing up to {args.max_combinations} parameter combinations")
    print(f"Dataset: {args.n_files} files, {args.n_clones} clones per type")
    print(f"File range: {args.start} - {args.end}")
    print(f"Types: {args.types}")
    print(f"Detection threshold: {args.threshold}")
    print(f"Weights: accuracy={args.weight_accuracy}, match_size={args.weight_match_size}")
    print()
    
    # Set random seed
    random.seed(args.seed)
    
    # Load previous results if resuming
    previous_results = []
    if args.resume and Path(args.resume).exists():
        with open(args.resume, 'r') as f:
            previous_results = json.load(f)
        print(f"Resuming from {args.resume} with {len(previous_results)} previous runs")
    
    # Generate parameter combinations
    all_combinations = generate_parameter_combinations()
    print(f"Total possible combinations: {len(all_combinations)}")
    
    # Filter out already tested combinations if resuming
    tested_params = set()
    if previous_results:
        for entry in previous_results:
            param_tuple = tuple(sorted(entry['params'].items()))
            tested_params.add(param_tuple)
        
        combinations = [c for c in all_combinations if tuple(sorted(c.items())) not in tested_params]
        print(f"Remaining combinations to test: {len(combinations)}")
    else:
        combinations = all_combinations
    
    # Limit to max_combinations
    if len(combinations) > args.max_combinations:
        combinations = combinations[:args.max_combinations]
    
    print(f"Will test {len(combinations)} combinations")
    print()
    
    # Prepare output
    all_results = previous_results.copy() if previous_results else []
    
    # Backup original analyzer
    analyzer_backup = ANALYZER_PATH.with_suffix('.py.backup')
    if not analyzer_backup.exists():
        shutil.copy(ANALYZER_PATH, analyzer_backup)
    
    # Generate dataset ONCE before all parameter tests
    print("Generating dataset (once for all parameter combinations)...")
    generate_dataset(
        source_dir=str(DATASET_DIR),
        output_dir=str(PLAGIARISM_DIR),
        n=args.n_clones,
        file_range=(args.start, args.end),
        types=args.types
    )
    print(f"Dataset generated with {args.n_files} files x {len(args.types)} types x {args.n_clones} clones\n")
    
    try:
        for i, params in enumerate(combinations, 1):
            print(f"\n{'='*80}")
            print(f"Testing combination {i}/{len(combinations)}")
            print(f"{'='*80}")
            
            # Restore analyzer to clean state
            shutil.copy(analyzer_backup, ANALYZER_PATH)
            
            # Modify analyzer with current parameters
            if not modify_analyzer_parameters(params):
                print("Failed to modify analyzer, skipping...")
                continue
            
            # Run accuracy test on already-generated dataset
            print("Running accuracy test...")
            results = run_accuracy_test_with_dataset(
                dataset_dir=DATASET_DIR,
                n_files=args.n_files,
                n_clones=args.n_clones,
                file_range=(args.start, args.end),
                types=args.types,
                threshold=args.threshold,
                cleanup=False  # We'll clean up at end
            )
            
            # Calculate score
            score = calculate_score(
                results,
                weight_accuracy=args.weight_accuracy,
                weight_match_size=args.weight_match_size
            )
            
            # Print detailed results
            print_parameter_set(params, score, results)
            
            # Store result
            result_entry = {
                'params': params,
                'score': score,
                'results_summary': results['summary'],
                'results_by_type': results['by_type']
            }
            all_results.append(result_entry)
            
            # Save intermediate results
            if args.output:
                with open(args.output, 'w') as f:
                    json.dump(all_results, f, indent=2)
            
            # Do NOT delete dataset between runs unless cleanup flag is set
            # We'll clean up at the very end
    
    except KeyboardInterrupt:
        print("\n\nInterrupted! Saving partial results...")
    finally:
        # Restore analyzer
        if analyzer_backup.exists():
            shutil.copy(analyzer_backup, ANALYZER_PATH)
            analyzer_backup.unlink()
        
        # Cleanup generated clones unless keep-dataset flag
        if not args.keep_dataset:
            for type_num in args.types:
                type_dir = PLAGIARISM_DIR / f"type{type_num}"
                if type_dir.exists():
                    shutil.rmtree(type_dir)
        else:
            print(f"\nKeeping generated dataset in {PLAGIARISM_DIR} for reuse")
    
    # Sort by score
    all_results.sort(key=lambda x: x['score'], reverse=True)
    
    # Print top results
    print("\n" + "=" * 80)
    print("FINE-TUNING COMPLETE - TOP 5 PARAMETER SETS")
    print("=" * 80)
    
    for idx, entry in enumerate(all_results[:5], 1):
        print(f"\n#{idx} - Score: {entry['score']:.4f}")
        print("Parameters:")
        for key, value in entry['params'].items():
            print(f"  {key}: {value}")
        summary = entry['results_summary']
        print(f"Performance: detection={summary['overall_detection_rate']:.1f}%, "
              f"exact={summary['overall_exact_rate']:.1f}%, "
              f"avg_match_size={summary['avg_match_size']:.1f}")
    
    # Save final results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"\nAll results saved to {args.output}")
    
    # Recommend best set
    if all_results:
        best = all_results[0]
        print("\n" + "=" * 80)
        print("RECOMMENDED PARAMETERS:")
        print("=" * 80)
        for key, value in best['params'].items():
            print(f"{key}: {value}")
        print("\nTo apply these parameters, update the following in cli/analyzer.py:")
        for key, value in best['params'].items():
            if key == 'k':
                print(f"  - compute_fingerprints: k={value}")
            elif key == 'window_size':
                print(f"  - winnow_fingerprints: window_size={value}")
            elif key == 'min_depth':
                print(f"  - hash_ast_subtrees: min_depth={value}")
            elif key == 'ast_threshold':
                print(f"  - analyze_plagiarism: ast_threshold={value}")
            elif key == 'minimum_occurrences':
                print(f"  - build_fragments: minimum_occurrences={value}")
            elif key == 'base':
                print(f"  - compute_fingerprints: base={value}")

if __name__ == "__main__":
    main()
