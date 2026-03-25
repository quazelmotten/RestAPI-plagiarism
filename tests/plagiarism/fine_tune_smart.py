#!/usr/bin/env python3
"""
Sophisticated parameter fine-tuning using successive halving (multi-fidelity evaluation).
Optimizes for accuracy and large, representative matching regions.
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
import math

# Try to import tqdm for progress bars
try:
    from tqdm import tqdm
except ImportError:
    # Fallback: dummy tqdm that just returns the iterable
    class DummyTqdm:
        def __init__(self, iterable=None, total=None, desc=None):
            if iterable is None:
                iterable = []
            self.iterable = iterable
            self.total = total
            self.desc = desc
            if desc and total:
                print(f"{desc}... (total: {total})")
        def __iter__(self):
            return iter(self.iterable)
        def update(self, n=1):
            pass
        def close(self):
            pass
    tqdm = DummyTqdm

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from py_clone_generator import generate_dataset

DATASET_DIR = Path("/home/bobbybrown/RestAPI-plagiarism/dataset")
PLAGIARISM_DIR = Path("/home/bobbybrown/RestAPI-plagiarism/tests/plagiarism")
CLI_PATH = "/home/bobbybrown/RestAPI-plagiarism/cli/cli.py"
ANALYZER_PATH = Path("/home/bobbybrown/RestAPI-plagiarism/cli/analyzer.py")

def compute_detailed_match_statistics(matches: List[Dict], file_sizes: Dict[str, int]) -> Dict[str, Any]:
    """Compute detailed match statistics including fragment count, sizes, and large fragment detection."""
    if not matches:
        return {
            "fragment_count": 0,
            "avg_fragment_size": 0,
            "total_matched_lines": 0,
            "large_fragments_count": 0,
            "size_weighted_score": 0
        }
    
    total_size = 0
    fragment_sizes = []
    large_fragments = 0
    size_weighted_score = 0
    
    for match in matches:
        f1 = match.get('file1', {})
        f2 = match.get('file2', {})
        
        lines1 = f1.get('end_line', 0) - f1.get('start_line', 0) + 1
        lines2 = f2.get('end_line', 0) - f2.get('start_line', 0) + 1
        avg_lines = (lines1 + lines2) / 2
        fragment_sizes.append(avg_lines)
        total_size += avg_lines
        
        # Check if this is a large fragment (>80% of file)
        file_key1 = f1.get('file', '')
        file_key2 = f2.get('file', '')
        file_size1 = file_sizes.get(file_key1, 0)
        file_size2 = file_sizes.get(file_key2, 0)
        avg_file_size = (file_size1 + file_size2) / 2 if file_size1 and file_size2 else 0
        
        if avg_file_size > 0 and avg_lines >= 0.8 * avg_file_size:
            large_fragments += 1
            # Bonus for large fragments
            size_weighted_score += avg_lines * 2
        else:
            size_weighted_score += avg_lines
    
    fragment_count = len(fragment_sizes)
    avg_fragment_size = total_size / fragment_count if fragment_count > 0 else 0
    
    return {
        "fragment_count": fragment_count,
        "avg_fragment_size": avg_fragment_size,
        "total_matched_lines": total_size,
        "large_fragments_count": large_fragments,
        "size_weighted_score": size_weighted_score
    }

def get_file_sizes(dataset_dir: Path, file_list: List[Path]) -> Dict[str, int]:
    """Get line counts for a list of files."""
    sizes = {}
    for file_path in file_list:
        try:
            with open(file_path, 'r') as f:
                lines = len(f.readlines())
                sizes[str(file_path)] = lines
        except:
            sizes[str(file_path)] = 0
    return sizes

def modify_analyzer_parameters(params: Dict[str, Any]) -> bool:
    """Modify the analyzer.py file with new parameter values by editing specific lines."""
    try:
        with open(ANALYZER_PATH, 'r') as f:
            lines = f.readlines()
        
        modified = []
        
        # compute_fingerprints line 124 (0-indexed: 123)
        if 'k' in params:
            idx = 123
            if idx < len(lines):
                k = params['k']
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
            # Replace hardcoded min_depth=3 in function calls
            call_line_indices = [458, 459, 553, 596, 695, 712]
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
        
        with open(ANALYZER_PATH, 'w') as f:
            f.writelines(lines)
        
        return True
    except Exception as e:
        print(f"Error modifying analyzer: {e}")
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
        if "matches" not in parsed:
            parsed["matches"] = []
        return parsed
    
    except subprocess.TimeoutExpired:
        return {"error": "Timeout", "similarity": 0, "matches": []}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON", "similarity": 0, "matches": []}
    except Exception as e:
        return {"error": str(e), "similarity": 0, "matches": []}

def run_accuracy_test_with_files(
    dataset_files: List[Path],
    cloned_files: List[Tuple[Path, Path, int]],
    threshold: float = 0.30
) -> Dict[str, Any]:
    """Run accuracy test on specific file pairs."""
    
    # Get file sizes for weighting
    file_sizes = get_file_sizes(DATASET_DIR, dataset_files)
    
    results = {
        "summary": {},
        "by_type": {},
        "details": [],
        "match_stats": {
            "total_weighted_score": 0,
            "total_fragments": 0,
            "total_matched_lines": 0,
            "total_large_fragments": 0
        }
    }
    
    by_type = defaultdict(lambda: {
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
        "total_weighted_score": 0,
        "total_fragments": 0,
        "total_matched_lines": 0,
        "total_large_fragments": 0,
        "match_stats_details": []
    })
    
    total_weighted_score = 0
    total_fragments = 0
    total_matched_lines = 0
    total_large_fragments = 0
    
    for original_file, clone_file, type_num in cloned_files:
        analysis = run_analyze_with_params(str(original_file), str(clone_file), threshold)
        
        if "error" in analysis:
            by_type[type_num]["errors"] += 1
            continue
        
        similarity = analysis.get("similarity", 0)
        matches = analysis.get("matches", [])
        
        by_type[type_num]["total"] += 1
        by_type[type_num]["similarities"].append(similarity)
        
        if similarity >= 95:
            by_type[type_num]["exact"] += 1
        elif similarity >= 80:
            by_type[type_num]["high"] += 1
        elif similarity >= 50:
            by_type[type_num]["medium"] += 1
        elif similarity >= 30:
            by_type[type_num]["low"] += 1
        else:
            by_type[type_num]["none"] += 1
        
        if similarity >= threshold * 100:
            by_type[type_num]["detected"] += 1
        
        # Detailed match statistics
        match_stats = compute_detailed_match_statistics(matches, file_sizes)
        by_type[type_num]["total_fragments"] += match_stats["fragment_count"]
        by_type[type_num]["total_weighted_score"] += match_stats["size_weighted_score"]
        by_type[type_num]["total_matched_lines"] += match_stats["total_matched_lines"]
        by_type[type_num]["total_large_fragments"] += match_stats["large_fragments_count"]
        by_type[type_num]["match_stats_details"].append(match_stats)
        
        total_weighted_score += match_stats["size_weighted_score"]
        total_fragments += match_stats["fragment_count"]
        total_matched_lines += match_stats["total_matched_lines"]
        total_large_fragments += match_stats["large_fragments_count"]
        
        results["details"].append({
            "type": type_num,
            "original": str(original_file),
            "clone": str(clone_file),
            "similarity": similarity,
            "detected": similarity >= threshold * 100,
            "match_count": len(matches),
            "match_stats": match_stats
        })
    
    # Compute per-type summaries
    for type_num, data in by_type.items():
        if data["total"] > 0:
            data["avg_similarity"] = sum(data["similarities"]) / len(data["similarities"])
            data["detection_rate"] = (data["detected"] / data["total"]) * 100
            data["exact_rate"] = (data["exact"] / data["total"]) * 100
            data["avg_match_size"] = data["total_matched_lines"] / data["total"]
            data["avg_fragments_per_original"] = data["total_fragments"] / data["total"]
            data["avg_weighted_score"] = data["total_weighted_score"] / data["total"]
        else:
            data["avg_similarity"] = 0
            data["detection_rate"] = 0
            data["exact_rate"] = 0
            data["avg_match_size"] = 0
            data["avg_fragments_per_original"] = 0
            data["avg_weighted_score"] = 0
        
        results["by_type"][f"type{type_num}"] = dict(data)
    
    # Compute overall summary
    total_tests = sum(d["total"] for d in by_type.values())
    total_detected = sum(d["detected"] for d in by_type.values())
    total_exact = sum(d["exact"] for d in by_type.values())
    total_errors = sum(d["errors"] for d in by_type.values())
    
    all_similarities = []
    for d in by_type.values():
        all_similarities.extend(d.get("similarities", []))
    
    results["summary"] = {
        "total_tests": total_tests,
        "total_detected": total_detected,
        "total_exact": total_exact,
        "total_errors": total_errors,
        "total_matched_lines": total_matched_lines,
        "total_fragments": total_fragments,
        "total_weighted_score": total_weighted_score,
        "total_large_fragments": total_large_fragments,
        "overall_detection_rate": (total_detected / total_tests * 100) if total_tests > 0 else 0,
        "overall_exact_rate": (total_exact / total_tests * 100) if total_tests > 0 else 0,
        "avg_similarity": sum(all_similarities) / len(all_similarities) if all_similarities else 0,
        "avg_match_size": total_matched_lines / total_tests if total_tests > 0 else 0,
        "avg_fragments_per_original": total_fragments / total_tests if total_tests > 0 else 0,
        "avg_weighted_score": total_weighted_score / total_tests if total_tests > 0 else 0,
        "large_fragments_rate": (total_large_fragments / total_fragments * 100) if total_fragments > 0 else 0
    }
    
    return results

def calculate_smart_score(results: Dict[str, Any], weight_accuracy: float = 0.6, weight_match_size: float = 0.4) -> float:
    """
    Calculate a composite score based on prioritized metrics:
    1. Average fragment size (bigger is better)
    2. Detection rate (higher is better)
    3. Fragment count (fewer is better)
    4. Total matched lines (bigger is better)
    
    Soft trade-off on detection.
    """
    summary = results["summary"]
    
    # Normalize detection rate (0-100 -> 0-1)
    detection_rate = summary["overall_detection_rate"] / 100.0
    
    # Normalize average fragment size (empirical range: 0-200 lines)
    avg_fragment_size = summary.get("avg_match_size", 0)
    # Sigmoid: saturates around 200
    norm_fragment_size = 2.0 / (1.0 + math.exp(-avg_fragment_size / 100.0)) - 1.0
    norm_fragment_size = max(0, min(1, norm_fragment_size))
    
    # Normalize fragment count (want fewer)
    avg_fragments = summary.get("avg_fragments_per_original", 0)
    # Exponential decay: 0 fragments -> 1, 10 fragments -> ~0.1
    norm_fragment_count = math.exp(-avg_fragments / 5.0)
    
    # Normalize total matched lines (sigmoid)
    total_matched = summary.get("total_matched_lines", 0)
    norm_total_matched = 1.0 / (1.0 + math.exp(-total_matched / 1000.0))
    
    # Weighted combination - following user's priority order
    # Detection rate is important but soft trade-off
    accuracy_component = detection_rate  # Primary accuracy metric
    
    # Fragment quality: large fragments are good, few fragments are good
    fragment_quality = (norm_fragment_size * 0.5 + norm_fragment_count * 0.3 + norm_total_matched * 0.2)
    
    # Composite score
    score = (accuracy_component * weight_accuracy) + (fragment_quality * weight_match_size)
    
    return score

def generate_parameter_combinations(n_samples: int = 5000) -> List[Dict[str, Any]]:
    """Generate random parameter combinations covering the full range."""
    param_ranges = {
        'k': list(range(2, 13)),  # 2-12
        'window_size': list(range(2, 13)),  # 2-12
        'min_depth': list(range(2, 13)),  # 2-12
        'minimum_occurrences': list(range(2, 6)),  # 2-5
    }
    
    combinations = []
    for _ in range(n_samples):
        params = {
            key: random.choice(values)
            for key, values in param_ranges.items()
        }
        combinations.append(params)
    
    random.shuffle(combinations)
    return combinations

class SuccessiveHalvingTuner:
    """Implements successive halving with multi-fidelity evaluation."""
    
    def __init__(
        self,
        dataset_dir: Path,
        n_files_available: int,
        n_clones: int,
        types: List[int],
        threshold: float,
        weight_accuracy: float,
        weight_match_size: float,
        output_file: str,
        seed: int
    ):
        self.dataset_dir = dataset_dir
        self.n_files_available = n_files_available
        self.n_clones = n_clones
        self.types = types
        self.threshold = threshold
        self.weight_accuracy = weight_accuracy
        self.weight_match_size = weight_match_size
        self.output_file = output_file
        self.seed = seed
        
        random.seed(seed)
        
        # Results tracking
        self.all_results = []
        self.best_configs = []
        
        # Prepare file pool
        all_files = sorted(dataset_dir.glob("*.py"))
        self.file_pool = [f for f in all_files if f.stat().st_size >= 50][:n_files_available]
        random.shuffle(self.file_pool)
        print(f"File pool: {len(self.file_pool)} files")
        
        # Backup analyzer
        self.analyzer_backup = ANALYZER_PATH.with_suffix('.py.backup')
        if not self.analyzer_backup.exists():
            shutil.copy(ANALYZER_PATH, self.analyzer_backup)
    
    def restore_analyzer(self):
        shutil.copy(self.analyzer_backup, ANALYZER_PATH)
    
    def sample_file_subsets(self) -> List[List[Path]]:
        """Create non-overlapping file subsets for successive rounds."""
        # For 4 rounds: 5, 10, 15, 20 files (total 50)
        # Actually need 5+10+15+20 = 50 non-overlapping files
        
        if len(self.file_pool) < 50:
            print(f"Warning: Need at least 50 files for non-overlapping subsets. Have {len(self.file_pool)}. Will reuse some files.")
            # Fallback: allow overlap with randomization
            subsets = []
            for i in range(4):
                size = 5 * (i + 1)
                subsets.append(random.sample(self.file_pool, min(size, len(self.file_pool))))
            return subsets
        
        # Non-overlapping
        subsets = []
        used = set()
        sizes = [5, 10, 15, 20]
        idx = 0
        for size in sizes:
            subset = self.file_pool[idx:idx+size]
            subsets.append(subset)
            idx += size
        
        return subsets
    
    def build_clone_pairs(self, dataset_files: List[Path]) -> List[Tuple[Path, Path, int]]:
        """Generate clone pairs for given dataset files."""
        clone_pairs = []
        
        for type_num in self.types:
            type_dir = PLAGIARISM_DIR / f"type{type_num}"
            if not type_dir.exists():
                continue
            
            for orig_file in dataset_files:
                file_stem = orig_file.stem
                clone_files = sorted(type_dir.glob(f"{file_stem}_type{type_num}_*.py"))
                
                # Take only n_clones clones per type per file
                for clone_file in clone_files[:self.n_clones]:
                    clone_pairs.append((orig_file, clone_file, type_num))
        
        random.shuffle(clone_pairs)
        return clone_pairs
    
    def evaluate_configuration(self, params: Dict[str, Any], dataset_files: List[Path]) -> Dict[str, Any]:
        """Evaluate a parameter configuration on a given file subset."""
        self.restore_analyzer()
        
        if not modify_analyzer_parameters(params):
            return None
        
        clone_pairs = self.build_clone_pairs(dataset_files)
        if not clone_pairs:
            return None
        
        results = run_accuracy_test_with_files(
            dataset_files,
            clone_pairs,
            threshold=self.threshold
        )
        
        score = calculate_smart_score(
            results,
            weight_accuracy=self.weight_accuracy,
            weight_match_size=self.weight_match_size
        )
        
        return {
            'params': params,
            'score': score,
            'results_summary': results['summary'],
            'results_by_type': results['by_type'],
            'match_stats': {
                'total_weighted_score': results['summary']['total_weighted_score'],
                'avg_fragment_size': results['summary']['avg_match_size'],
                'avg_fragments_per_original': results['summary']['avg_fragments_per_original'],
                'total_large_fragments': results['summary']['total_large_fragments']
            }
        }
    
    def run(self, initial_configs: int = 200, round_factors: List[float] = [0.25, 0.5, 0.5, 1.0]):
        """
        Run successive halving.
        Round 1: initial_configs on subset 1 (smallest)
        Round 2: top initial_configs * factor1 on subset 2
        Round 3: top previous * factor2 on subset 3
        Round 4: top previous * factor3 on subset 4 (largest, full)
        """
        subsets = self.sample_file_subsets()
        print(f"\nFile subsets for rounds:")
        for i, subset in enumerate(subsets):
            print(f"  Round {i+1}: {len(subset)} files")
        
        # Generate initial configuration pool
        print(f"\nGenerating {initial_configs} random configurations...")
        configs = generate_parameter_combinations(initial_configs * 2)[:initial_configs]
        
        survivors = configs
        for round_num, subset in enumerate(subsets, 1):
            print(f"\n{'='*80}")
            print(f"ROUND {round_num} - {len(subset)} files, {len(survivors)} configurations")
            print(f"{'='*80}")
            
            round_results = []
            # Wrap survivors with tqdm for progress bar
            iterator = tqdm(survivors, total=len(survivors), desc=f"Round {round_num} configs")
            for i, params in enumerate(iterator, 1):
                print(f"\n[{i}/{len(survivors)}] Evaluating: {params}")
                result = self.evaluate_configuration(params, subset)
                
                if result:
                    round_results.append(result)
                    print(f"  Score: {result['score']:.4f}, "
                          f"Detection: {result['results_summary']['overall_detection_rate']:.1f}%, "
                          f"Avg fragment: {result['match_stats']['avg_fragment_size']:.1f} lines, "
                          f"Fragments/orig: {result['match_stats']['avg_fragments_per_original']:.1f}")
                else:
                    print(f"  Failed")
            
            # Sort by score
            round_results.sort(key=lambda x: x['score'], reverse=True)
            
            # Save round results
            self.all_results.extend(round_results)
            
            # Print round summary
            print(f"\nRound {round_num} complete. Top 3:")
            for j, res in enumerate(round_results[:3], 1):
                print(f"  {j}. Score={res['score']:.4f}, Params={res['params']}")
            
            # Determine survivors for next round (except last round)
            if round_num < len(subsets):
                factor = round_factors[round_num - 1]
                n_survivors = max(1, int(len(round_results) * factor))
                survivors = [res['params'] for res in round_results[:n_survivors]]
                print(f"Surviving {len(survivors)} configs for next round")
            else:
                # Last round: all results are final
                self.best_configs = round_results[:25]
                
                # Save all results
                if self.output_file:
                    with open(self.output_file, 'w') as f:
                        json.dump({
                            'all_results': self.all_results,
                            'best_configs': self.best_configs,
                            'metadata': {
                                'n_files_available': self.n_files_available,
                                'n_clones': self.n_clones,
                                'types': self.types,
                                'threshold': self.threshold,
                                'weight_accuracy': self.weight_accuracy,
                                'weight_match_size': self.weight_match_size,
                                'seed': self.seed
                            }
                        }, f, indent=2)
                    print(f"\nAll results saved to {self.output_file}")
                
                self.print_final_results()
        
        self.restore_analyzer()
    
    def print_final_results(self):
        """Print final top results."""
        print("\n" + "=" * 80)
        print("SUCCESSIVE HALVING COMPLETE - TOP 10 PARAMETER SETS")
        print("=" * 80)
        
        for idx, entry in enumerate(self.best_configs[:10], 1):
            print(f"\n#{idx} - Score: {entry['score']:.4f}")
            print(f"Parameters: {entry['params']}")
            summary = entry['results_summary']
            match_stats = entry['match_stats']
            print(f"Performance:")
            print(f"  Detection rate: {summary['overall_detection_rate']:.1f}%")
            print(f"  Exact rate: {summary['overall_exact_rate']:.1f}%")
            print(f"  Avg similarity: {summary['avg_similarity']:.1f}%")
            print(f"  Avg fragment size: {match_stats['avg_fragment_size']:.1f} lines")
            print(f"  Fragments/original: {match_stats['avg_fragments_per_original']:.1f}")
            print(f"  Large fragments: {summary['total_large_fragments']}")
        
        if self.best_configs:
            best = self.best_configs[0]
            print("\n" + "=" * 80)
            print("RECOMMENDED PARAMETERS:")
            print("=" * 80)
            for key, value in best['params'].items():
                print(f"{key}: {value}")

def main():
    parser = argparse.ArgumentParser(
        description="Sophisticated fine-tuning using successive halving (multi-fidelity)"
    )
    parser.add_argument("--n-files", type=int, default=100,
                        help="Number of files in pool (default: 100)")
    parser.add_argument("--n-clones", type=int, default=1,
                        help="Number of clones per type per file (default: 1)")
    parser.add_argument("--initial-configs", type=int, default=200,
                        help="Number of initial configurations (default: 200)")
    parser.add_argument("--start", type=int, default=0,
                        help="Starting file index (default: 0)")
    parser.add_argument("--end", type=int, default=100,
                        help="Ending file index (default: 100)")
    parser.add_argument("--types", type=int, nargs="+", default=[1, 2, 3, 4],
                        help="Clone types to test (default: 1 2 3 4)")
    parser.add_argument("--threshold", type=float, default=0.30,
                        help="Detection threshold (default: 0.30)")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")
    parser.add_argument("--output", type=str, default="fine_tune_smart_results.json",
                        help="Output JSON file (default: fine_tune_smart_results.json)")
    parser.add_argument("--weight-accuracy", type=float, default=0.6,
                        help="Weight for accuracy in score (default: 0.6)")
    parser.add_argument("--weight-match-size", type=float, default=0.4,
                        help="Weight for match quality in score (default: 0.4)")
    parser.add_argument("--keep-dataset", action="store_true",
                        help="Keep generated dataset")
    
    args = parser.parse_args()
    
    print("=" * 80)
    print("SUCCESSIVE HALVING FINE-TUNING FOR PLAGIARISM DETECTION")
    print("=" * 80)
    print(f"Initial configs: {args.initial_configs}")
    print(f"Dataset: {args.n_files} files, {args.n_clones} clones per type")
    print(f"File range: {args.start} - {args.end}")
    print(f"Clone types: {args.types}")
    print(f"Threshold: {args.threshold}")
    print(f"Weights: accuracy={args.weight_accuracy}, match_quality={args.weight_match_size}")
    print()
    
    # Generate dataset once
    print("Generating dataset (once for all rounds)...")
    generate_dataset(
        source_dir=str(DATASET_DIR),
        output_dir=str(PLAGIARISM_DIR),
        n=args.n_clones,
        file_range=(args.start, args.end),
        types=args.types
    )
    print(f"Dataset generated\n")
    
    # Create tuner and run
    tuner = SuccessiveHalvingTuner(
        dataset_dir=DATASET_DIR,
        n_files_available=args.n_files,
        n_clones=args.n_clones,
        types=args.types,
        threshold=args.threshold,
        weight_accuracy=args.weight_accuracy,
        weight_match_size=args.weight_match_size,
        output_file=args.output,
        seed=args.seed
    )
    
    try:
        tuner.run(initial_configs=args.initial_configs)
    except KeyboardInterrupt:
        print("\n\nInterrupted! Saving partial results...")
        if tuner.output_file:
            with open(tuner.output_file, 'w') as f:
                json.dump({
                    'all_results': tuner.all_results,
                    'best_configs': tuner.best_configs,
                }, f, indent=2)
            print(f"Partial results saved to {tuner.output_file}")
    finally:
        tuner.restore_analyzer()
        if not args.keep_dataset:
            for type_num in args.types:
                type_dir = PLAGIARISM_DIR / f"type{type_num}"
                if type_dir.exists():
                    shutil.rmtree(type_dir)
        else:
            print(f"Keeping dataset in {PLAGIARISM_DIR}")

if __name__ == "__main__":
    main()