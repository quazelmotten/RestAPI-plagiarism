#!/usr/bin/env python3
"""
Profile analyzer.py directly (not via CLI subprocess)
"""

import cProfile
import pstats
import io
import os
import sys
from itertools import combinations

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
src_dir = os.path.join(root_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from plagiarism.analyzer import (
    tokenize_with_tree_sitter,
    winnow_fingerprints,
    compute_fingerprints,
    extract_ast_hashes,
    analyze_plagiarism,
    parse_file,
)

DATASET_PATH = os.path.join(root_dir, "dataset")
PROFILE_OUTPUT = os.path.join(root_dir, "tests", "analyzer_profile.prof")

def get_files():
    files = []
    for i in range(1, 40):
        f = os.path.join(DATASET_PATH, f"file_{i}.py")
        if os.path.exists(f):
            files.append(f)
    return sorted(files)

def profile_fingerprints(files):
    """Profile fingerprint extraction"""
    results = []
    for f in files:
        _, tree = parse_file(f, 'python')
        tokens = tokenize_with_tree_sitter(f, 'python', tree=tree)
        fps = winnow_fingerprints(compute_fingerprints(tokens))
        ast = extract_ast_hashes(f, 'python', min_depth=3, tree=tree)
        results.append({'path': f, 'tokens': tokens, 'fingerprints': fps, 'ast': ast})
    return results

def profile_compare_all_pairs(results):
    """Profile all pair comparisons"""
    pairs = list(combinations(results, 2))
    for r1, r2 in pairs:
        analyze_plagiarism(r1['path'], r2['path'], language='python')

def main():
    files = get_files()
    print(f"Found {len(files)} files")
    
    profiler = cProfile.Profile()
    
    print("Phase 1: Profile fingerprint extraction...")
    profiler.enable()
    results = profile_fingerprints(files)
    profiler.disable()
    print(f"  Extracted fingerprints for {len(results)} files")
    
    print("Phase 2: Profile compare all pairs...")
    profiler.enable()
    profile_compare_all_pairs(results)
    profiler.disable()
    print(f"  Compared {len(list(combinations(results, 2)))} pairs")
    
    profiler.dump_stats(PROFILE_OUTPUT)
    print(f"\nProfile saved to: {PROFILE_OUTPUT}")
    
    # Print analyzer.py specific functions
    print("\n" + "="*80)
    print("PROFILING REPORT - analyzer.py functions")
    print("="*80)
    
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    stats.sort_stats('cumulative')
    stats.print_stats()
    print(stream.getvalue())

if __name__ == "__main__":
    main()
