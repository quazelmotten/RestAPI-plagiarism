#!/usr/bin/env python3
"""
Verify similarity results with xxhash are the same as with SHA1
"""

import os
import sys
from itertools import combinations

script_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(script_dir)
src_dir = os.path.join(root_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from plagiarism.analyzer import analyze_plagiarism, extract_ast_hashes, ast_similarity

DATASET_PATH = os.path.join(root_dir, "dataset")

def get_files():
    files = []
    for i in range(1, 40):
        f = os.path.join(DATASET_PATH, f"file_{i}.py")
        if os.path.exists(f):
            files.append(f)
    return sorted(files)

def main():
    files = get_files()
    print(f"Testing with {len(files)} files")
    
    # Extract AST hashes for all files
    print("Extracting AST hashes...")
    ast_hashes = {}
    for f in files:
        ast_hashes[f] = extract_ast_hashes(f, 'python', min_depth=3)
    
    # Compare all pairs and collect similarities
    pairs = list(combinations(files, 2))
    print(f"Comparing {len(pairs)} pairs...")
    
    similarities = []
    for f1, f2 in pairs:
        sim = ast_similarity(ast_hashes[f1], ast_hashes[f2])
        similarities.append((os.path.basename(f1), os.path.basename(f2), sim))
    
    # Sort by similarity
    similarities.sort(key=lambda x: x[2], reverse=True)
    
    print("\nTop 20 most similar pairs:")
    print("-" * 50)
    for f1, f2, sim in similarities[:20]:
        print(f"{f1} vs {f2}: {sim:.4f} ({sim*100:.1f}%)")
    
    # Count pairs above threshold
    for threshold in [0.3, 0.5, 0.7, 0.9]:
        count = sum(1 for _, _, s in similarities if s >= threshold)
        print(f"\nPairs with >={threshold*100:.0f}% similarity: {count}")
    
    return similarities

if __name__ == "__main__":
    main()
