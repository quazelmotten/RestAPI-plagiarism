#!/usr/bin/env python3
"""
Compare similarity percentages: old method (AST) vs new method (fingerprint overlap).

Old: ast_similarity = Jaccard(AST subtree hashes) using Counter
New: overlap_similarity = Jaccard(winnowed token fingerprints) using sets
"""

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "worker")

import os
import tempfile

from cli.analyzer import (
    ast_similarity,
    compute_fingerprints,
    extract_ast_hashes,
    tokenize_with_tree_sitter,
    winnow_fingerprints,
)


def fingerprint_similarity(fps_a, fps_b):
    """New method: Jaccard on unique fingerprint hashes (same as inverted index)."""
    hashes_a = {str(fp["hash"]) for fp in fps_a}
    hashes_b = {str(fp["hash"]) for fp in fps_b}
    intersection = len(hashes_a & hashes_b)
    union = len(hashes_a | hashes_b)
    return intersection / union if union else 0.0


def prepare_file(path, language="python"):
    """Extract both AST hashes and fingerprints for a file."""
    tokens = tokenize_with_tree_sitter(path, language)
    fps = winnow_fingerprints(compute_fingerprints(tokens))
    ast_hashes = extract_ast_hashes(path, language, min_depth=3)
    return fps, ast_hashes


def compare(name_a, code_a, name_b, code_b):
    """Compare two code snippets with both metrics."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path_a = os.path.join(tmpdir, name_a)
        path_b = os.path.join(tmpdir, name_b)
        with open(path_a, "w") as f:
            f.write(code_a)
        with open(path_b, "w") as f:
            f.write(code_b)

        fps_a, ast_a = prepare_file(path_a)
        fps_b, ast_b = prepare_file(path_b)

        old_sim = ast_similarity(ast_a, ast_b)
        new_sim = fingerprint_similarity(fps_a, fps_b)

        print(f"  AST sim (old):   {old_sim:.1%}  ({len(ast_a)} vs {len(ast_b)} hashes)")
        print(f"  FP overlap (new): {new_sim:.1%}  ({len(fps_a)} vs {len(fps_b)} fingerprints)")
        return old_sim, new_sim


print("=" * 65)
print("Similarity Comparison: AST (old) vs Fingerprint Overlap (new)")
print("=" * 65)

# Test 1: Identical files
print("\n1. IDENTICAL FILES")
print("-" * 40)
compare(
    "a.py",
    """
def process(data):
    result = []
    for x in data:
        if x > 0:
            result.append(x * 2)
    return result
""",
    "b.py",
    """
def process(data):
    result = []
    for x in data:
        if x > 0:
            result.append(x * 2)
    return result
""",
)

# Test 2: Same structure, different variable names
print("\n2. SAME STRUCTURE, DIFFERENT NAMES")
print("-" * 40)
compare(
    "a.py",
    """
def process(data):
    result = []
    for x in data:
        if x > 0:
            result.append(x * 2)
    return result
""",
    "b.py",
    """
def process(items):
    output = []
    for item in items:
        if item > 0:
            output.append(item * 2)
    return output
""",
)

# Test 3: Same structure, slightly different logic
print("\n3. SIMILAR STRUCTURE, MINOR LOGIC CHANGE")
print("-" * 40)
compare(
    "a.py",
    """
def process(data):
    result = []
    for x in data:
        if x > 0:
            result.append(x * 2)
    return result
""",
    "b.py",
    """
def process(data):
    result = []
    for x in data:
        if x >= 0:
            result.append(x * 3)
    return result
""",
)

# Test 4: Completely different files
print("\n4. COMPLETELY DIFFERENT FILES")
print("-" * 40)
compare(
    "a.py",
    """
def process(data):
    result = []
    for x in data:
        if x > 0:
            result.append(x * 2)
    return result
""",
    "b.py",
    """
import json

class Config:
    def __init__(self, path):
        with open(path) as f:
            self.data = json.load(f)

    def get(self, key, default=None):
        return self.data.get(key, default)
""",
)

# Test 5: Partial copy (function partially reused)
print("\n5. PARTIAL COPY (one function shared)")
print("-" * 40)
compare(
    "a.py",
    """
def validate(x):
    return x is not None and x > 0

def process(data):
    result = []
    for x in data:
        if validate(x):
            result.append(x * 2)
    return result
""",
    "b.py",
    """
def validate(x):
    return x is not None and x > 0

def transform(data):
    return [x * 3 for x in data if x > 0]
""",
)

# Test 6: Boilerplate heavy (many shared imports/defs)
print("\n6. BOILERPLATE HEAVY (shared imports)")
print("-" * 40)
compare(
    "a.py",
    """
import os
import sys
import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def main():
    logger.info("Starting")
    data = load_data()
    process(data)

def load_data():
    with open("data.json") as f:
        return json.load(f)

def process(data):
    for item in data:
        print(item)
""",
    "b.py",
    """
import os
import sys
import json
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def main():
    logger.info("Starting")
    config = load_config()
    run(config)

def load_config():
    with open("config.json") as f:
        return json.load(f)

def run(config):
    for key, val in config.items():
        print(f"{key}: {val}")
""",
)

# Test 7: Copy-paste with reordering
print("\n7. COPY-PASTE WITH REORDERING")
print("-" * 40)
compare(
    "a.py",
    """
def helper(x):
    return x + 1

def main(data):
    results = []
    for item in data:
        results.append(helper(item))
    return results

def validate(data):
    return all(x > 0 for x in data)
""",
    "b.py",
    """
def validate(data):
    return all(x > 0 for x in data)

def helper(x):
    return x + 1

def main(data):
    results = []
    for item in data:
        results.append(helper(item))
    return results
""",
)

print("\n" + "=" * 65)
print("Summary:")
print("  AST (old) = structural similarity (tree shapes)")
print("  FP (new)  = token pattern similarity (keyword/operator sequences)")
print("=" * 65)
