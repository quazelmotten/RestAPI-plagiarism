#!/usr/bin/env python3
"""
Test script to demonstrate the inverted index functionality.
Shows how the system filters out non-viable candidates for plagiarism detection.
"""

import sys
import os

import logging
from collections import defaultdict
from worker.infrastructure.inverted_index import RedisInvertedIndex

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FakeRedisPipeline:
    """In-memory mock of a Redis pipeline."""

    def __init__(self, store):
        self._store = store
        self._commands = []

    def sadd(self, key, *values):
        self._commands.append(('sadd', key, set(values)))

    def srem(self, key, *values):
        self._commands.append(('srem', key, set(values)))

    def smembers(self, key):
        self._commands.append(('smembers', key))

    def scard(self, key):
        self._commands.append(('scard', key))

    def delete(self, key):
        self._commands.append(('delete', key))

    def execute(self):
        results = []
        for op, key, *args in self._commands:
            if op == 'sadd':
                self._store.setdefault(key, set()).update(args[0])
                results.append(len(args[0]))
            elif op == 'srem':
                self._store.setdefault(key, set()).difference_update(args[0])
                results.append(len(args[0]))
            elif op == 'smembers':
                results.append(set(self._store.get(key, set())))
            elif op == 'scard':
                results.append(len(self._store.get(key, set())))
            elif op == 'delete':
                self._store.pop(key, None)
                results.append(1)
        self._commands.clear()
        return results


class FakeRedis:
    """In-memory mock of a Redis client using sets."""

    def __init__(self):
        self._store = defaultdict(set)

    def pipeline(self):
        return FakeRedisPipeline(self._store)

    def sadd(self, key, *values):
        self._store[key].update(values)

    def smembers(self, key):
        return set(self._store.get(key, set()))

    def scard(self, key):
        return len(self._store.get(key, set()))

    def srem(self, key, *values):
        self._store[key].difference_update(values)

    def delete(self, key):
        self._store.pop(key, None)


def create_test_fingerprints(base_hash: int, count: int) -> list:
    """Create test fingerprints with varying hashes."""
    return [
        {'hash': base_hash + i, 'start': (i, 0), 'end': (i, 10)}
        for i in range(count)
    ]


def test_inverted_index():
    """Test the inverted index functionality."""
    logger.info("=" * 70)
    logger.info("Testing Inverted Index for Plagiarism Detection")
    logger.info("=" * 70)
    
    # Create inverted index instance
    index = RedisInvertedIndex(FakeRedis())
    
    # Simulate adding files to the database
    logger.info("\n1. Indexing files in the database...")
    
    # File 1: 100 unique fingerprints
    file1_hash = "file1_abc123"
    file1_fps = create_test_fingerprints(1000, 100)
    index.add_file_fingerprints(file1_hash, file1_fps, "python")
    logger.info(f"   Indexed file1: 100 fingerprints")
    
    # File 2: 100 fingerprints, 50% overlap with file1
    file2_hash = "file2_def456"
    file2_fps = create_test_fingerprints(1000, 50) + create_test_fingerprints(2000, 50)
    index.add_file_fingerprints(file2_hash, file2_fps, "python")
    logger.info(f"   Indexed file2: 100 fingerprints (50% overlap with file1)")
    
    # File 3: 100 fingerprints, 15% overlap with file1
    file3_hash = "file3_ghi789"
    file3_fps = create_test_fingerprints(1000, 15) + create_test_fingerprints(3000, 85)
    index.add_file_fingerprints(file3_hash, file3_fps, "python")
    logger.info(f"   Indexed file3: 100 fingerprints (15% overlap with file1)")
    
    # File 4: 100 fingerprints, 5% overlap with file1
    file4_hash = "file4_jkl012"
    file4_fps = create_test_fingerprints(1000, 5) + create_test_fingerprints(4000, 95)
    index.add_file_fingerprints(file4_hash, file4_fps, "python")
    logger.info(f"   Indexed file4: 100 fingerprints (5% overlap with file1)")
    
    # Test candidate search with 15% threshold
    logger.info(f"\n3. Searching for candidates (new file with 100 fingerprints)...")
    
    # New file: 100 fingerprints, overlaps with all existing files
    new_file_fps = create_test_fingerprints(1000, 100)
    new_file_hashes = [str(fp['hash']) for fp in new_file_fps]
    
    candidates = index.find_candidates(new_file_hashes, "python")
    
    logger.info(f"   Query file has {len(new_file_fps)} fingerprints")
    logger.info(f"   Minimum overlap required: {int(len(new_file_fps) * 0.15)} fingerprints")
    logger.info(f"   Candidates found: {len(candidates)}")
    
    # Show which files were selected
    expected = {
        file1_hash: "100% overlap (all 100 fingerprints)",
        file2_hash: "50% overlap (50 fingerprints)",
        file3_hash: "15% overlap (15 fingerprints)",
        file4_hash: "5% overlap (5 fingerprints) - BELOW THRESHOLD",
    }
    
    logger.info(f"\n4. Candidate Analysis:")
    for file_hash, description in expected.items():
        is_candidate = file_hash in candidates
        status = "✓ SELECTED" if is_candidate else "✗ FILTERED OUT"
        logger.info(f"   {file_hash}: {description} -> {status}")
    
    # Calculate efficiency gain
    total_files = 4
    files_analyzed = len(candidates)
    files_skipped = total_files - files_analyzed
    efficiency = (files_skipped / total_files) * 100
    
    logger.info(f"\n5. Efficiency Gain:")
    logger.info(f"   Total files in database: {total_files}")
    logger.info(f"   Files requiring detailed analysis: {files_analyzed}")
    logger.info(f"   Files filtered out (below 15% threshold): {files_skipped}")
    logger.info(f"   Efficiency improvement: {efficiency:.0f}% fewer comparisons!")
    
    # Test with different threshold
    logger.info(f"\n6. Testing with 50% threshold...")
    index.min_overlap_threshold = 0.50
    candidates_strict = index.find_candidates(new_file_hashes, "python")
    logger.info(f"   Candidates with 50% threshold: {len(candidates_strict)}")
    logger.info(f"   Expected: file1 (100%), file2 (50%)")
    
    logger.info("\n" + "=" * 70)
    logger.info("Test completed successfully!")
    logger.info("=" * 70)


if __name__ == "__main__":
    try:
        test_inverted_index()
    except Exception as e:
        logger.error(f"Test failed: {e}")
        import traceback
        logger.error(traceback.format_exc())
        sys.exit(1)
