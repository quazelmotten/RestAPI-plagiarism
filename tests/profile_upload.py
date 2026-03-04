#!/usr/bin/env python3
"""
Profiling script to analyze performance of uploading 39 files.

Usage:
    python profile_upload.py

This script:
1. Uses cProfile to profile the worker processing
2. Saves profile data to profile_output.prof (viewable with snakeviz)
3. Prints a detailed text report
"""

import cProfile
import pstats
import os
import sys
import io
from pathlib import Path
from itertools import combinations
from datetime import datetime

# Add src to path
script_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.join(script_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)
if script_dir not in sys.path:
    sys.path.insert(0, script_dir)

from plagiarism.analyzer import (
    tokenize_with_tree_sitter,
    winnow_fingerprints,
    compute_fingerprints,
    extract_ast_hashes,
    ast_similarity,
    index_fingerprints,
)

DATASET_PATH = Path("/home/bobbybrown/RestAPI-plagiarism/dataset")
PROFILE_OUTPUT = "/home/bobbybrown/RestAPI-plagiarism/profile_output.prof"


def get_all_files():
    """Get all Python files from the dataset."""
    files = sorted(DATASET_PATH.glob("*.py"))
    return files


def process_single_file(file_path, language='python'):
    """Process a single file - tokenize and extract fingerprints."""
    tokens = tokenize_with_tree_sitter(str(file_path), language)
    fingerprints = winnow_fingerprints(compute_fingerprints(tokens))
    ast_hashes = extract_ast_hashes(str(file_path), language, min_depth=3)
    return {
        'tokens': tokens,
        'fingerprints': fingerprints,
        'ast_hashes': ast_hashes,
    }


def process_all_files(file_paths, language='python'):
    """Process all files - tokenize and extract fingerprints for each."""
    results = []
    for file_path in file_paths:
        print(f"Processing: {file_path.name}")
        result = process_single_file(file_path, language)
        results.append({
            'path': str(file_path),
            'filename': file_path.name,
            **result
        })
    return results


def compare_all_pairs(results, language='python'):
    """Compare all pairs of files."""
    pairs = list(combinations(results, 2))
    print(f"Comparing {len(pairs)} pairs...")
    
    comparison_results = []
    for i, (file_a, file_b) in enumerate(pairs):
        if (i + 1) % 50 == 0:
            print(f"  Progress: {i + 1}/{len(pairs)}")
        
        # Compute AST similarity
        sim = ast_similarity(file_a['ast_hashes'], file_b['ast_hashes'])
        comparison_results.append({
            'file_a': file_a['filename'],
            'file_b': file_b['filename'],
            'similarity': sim,
        })
    
    return comparison_results


def run_full_analysis():
    """Run the full analysis workflow."""
    print("=" * 60)
    print("Plagiarism Detection Profiling - 39 Files")
    print("=" * 60)
    print(f"Started at: {datetime.now()}")
    print()
    
    # Get all files from dataset
    files = get_all_files()
    print(f"Found {len(files)} files in dataset")
    
    if len(files) != 39:
        print(f"WARNING: Expected 39 files, found {len(files)}")
    
    print()
    print("Phase 1: Processing all files (tokenization + fingerprints)")
    print("-" * 60)
    
    # Phase 1: Process all files
    results = process_all_files(files)
    
    print(f"\nProcessed {len(results)} files")
    total_tokens = sum(len(r['tokens']) for r in results)
    total_fingerprints = sum(len(r['fingerprints']) for r in results)
    total_ast_hashes = sum(len(r['ast_hashes']) for r in results)
    print(f"  Total tokens: {total_tokens}")
    print(f"  Total fingerprints: {total_fingerprints}")
    print(f"  Total AST hashes: {total_ast_hashes}")
    
    print()
    print("Phase 2: Comparing all file pairs")
    print("-" * 60)
    
    # Phase 2: Compare all pairs
    comparison_results = compare_all_pairs(results)
    
    print(f"\nCompared {len(comparison_results)} pairs")
    similar_pairs = [r for r in comparison_results if r['similarity'] > 0.3]
    print(f"  Pairs with >30% similarity: {len(similar_pairs)}")
    
    print()
    print("=" * 60)
    print(f"Completed at: {datetime.now()}")
    print("=" * 60)
    
    return results, comparison_results


def main():
    """Main entry point with profiling."""
    print("Starting profiling with cProfile...")
    print(f"Output will be saved to: {PROFILE_OUTPUT}")
    print()
    
    # Create profiler
    profiler = cProfile.Profile()
    
    # Run the analysis with profiling
    profiler.enable()
    results, comparison_results = run_full_analysis()
    profiler.disable()
    
    # Save profile data for snakeviz
    profiler.dump_stats(PROFILE_OUTPUT)
    print(f"\nProfile data saved to: {PROFILE_OUTPUT}")
    print("View with: snakeviz profile_output.prof")
    
    # Print text report
    print()
    print("=" * 80)
    print("PROFILING REPORT - Sorted by cumulative time")
    print("=" * 80)
    
    # Get stats
    stream = io.StringIO()
    stats = pstats.Stats(profiler, stream=stream)
    
    # Sort by cumulative time (functions that take the most time including subcalls)
    stats.sort_stats('cumulative')
    
    # Print top 50 functions
    stats.print_stats(50)
    
    print(stream.getvalue())
    
    # Additional report: sorted by total time
    print()
    print("=" * 80)
    print("PROFILING REPORT - Sorted by total time (excluding subcalls)")
    print("=" * 80)
    
    stream2 = io.StringIO()
    stats2 = pstats.Stats(profiler, stream=stream2)
    stats2.sort_stats('tottime')
    stats2.print_stats(50)
    
    print(stream2.getvalue())
    
    # Print statistics summary
    print()
    print("=" * 80)
    print("SUMMARY STATISTICS")
    print("=" * 80)
    stats.sort_stats('cumulative')
    stats.print_stats(0.5)  # Show functions taking >0.5% of time
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
