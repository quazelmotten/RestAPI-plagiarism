#!/usr/bin/env python3
"""
Test script for Redis-based fingerprint storage and similarity calculation.
Run this to verify Redis integration is working correctly.
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from plagiarism.redis_store import RedisFingerprintStore, fingerprint_store
from plagiarism.redis_analyzer import (
    analyze_plagiarism_redis,
    get_file_fingerprints_status,
    clear_file_fingerprints
)


def test_redis_connection():
    """Test basic Redis connectivity."""
    print("Testing Redis connection...")
    try:
        fingerprint_store.redis.ping()
        print("✅ Redis connection successful")
        return True
    except Exception as e:
        print(f"❌ Redis connection failed: {e}")
        return False


def test_fingerprint_storage():
    """Test storing and retrieving fingerprints."""
    print("\nTesting fingerprint storage...")
    
    test_hash = "test_file_abc123"
    
    # Test token fingerprints
    test_fingerprints = [
        {'hash': 12345, 'start': (1, 0), 'end': (1, 10)},
        {'hash': 67890, 'start': (2, 0), 'end': (2, 15)},
        {'hash': 11111, 'start': (3, 0), 'end': (3, 20)},
    ]
    
    try:
        fingerprint_store.store_token_fingerprints(test_hash, test_fingerprints)
        
        # Verify storage
        stored = fingerprint_store.get_token_fingerprints(test_hash)
        if stored and stored['count'] == 3:
            print(f"✅ Token fingerprints stored and retrieved successfully")
        else:
            print(f"❌ Token fingerprint retrieval failed")
            return False
        
        # Test AST fingerprints
        ast_hashes = [98765, 43210, 56789]
        fingerprint_store.store_ast_fingerprints(test_hash, ast_hashes)
        
        ast_stored = fingerprint_store.get_ast_fingerprints(test_hash)
        if ast_stored and len(ast_stored) == 3:
            print(f"✅ AST fingerprints stored and retrieved successfully")
        else:
            print(f"❌ AST fingerprint retrieval failed")
            return False
        
        # Cleanup
        clear_file_fingerprints(test_hash)
        print("✅ Cleanup successful")
        
        return True
        
    except Exception as e:
        print(f"❌ Fingerprint storage test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_similarity_calculation():
    """Test similarity calculation with Redis."""
    print("\nTesting similarity calculation...")
    
    hash_a = "test_file_a_123"
    hash_b = "test_file_b_456"
    
    # Create overlapping fingerprints
    fps_a = [
        {'hash': 100, 'start': (1, 0), 'end': (1, 10)},
        {'hash': 200, 'start': (2, 0), 'end': (2, 15)},
        {'hash': 300, 'start': (3, 0), 'end': (3, 20)},
    ]
    
    fps_b = [
        {'hash': 100, 'start': (5, 0), 'end': (5, 10)},  # Common
        {'hash': 200, 'start': (6, 0), 'end': (6, 15)},  # Common
        {'hash': 400, 'start': (7, 0), 'end': (7, 20)},  # Different
    ]
    
    try:
        # Store fingerprints
        fingerprint_store.store_token_fingerprints(hash_a, fps_a)
        fingerprint_store.store_token_fingerprints(hash_b, fps_b)
        
        # Calculate similarity
        token_sim, matches = fingerprint_store.calculate_token_similarity(hash_a, hash_b)
        
        print(f"Token similarity: {token_sim:.2%}")
        print(f"Matching regions: {len(matches)}")
        
        # Expected: 2 common / (3 + 3) total = 4/6 = 0.666...
        if 0.6 <= token_sim <= 0.7 and len(matches) == 2:
            print("✅ Similarity calculation correct")
        else:
            print(f"❌ Unexpected similarity result")
            return False
        
        # Cleanup
        clear_file_fingerprints(hash_a)
        clear_file_fingerprints(hash_b)
        
        return True
        
    except Exception as e:
        print(f"❌ Similarity calculation test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_caching():
    """Test similarity result caching."""
    print("\nTesting result caching...")
    
    hash_a = "cache_test_a"
    hash_b = "cache_test_b"
    
    try:
        # Store a cached result
        fingerprint_store.cache_similarity_result(
            hash_a, hash_b,
            token_sim=0.75,
            ast_sim=0.60,
            matches=[{'file1': {'start_line': 1}, 'file2': {'start_line': 5}}]
        )
        
        # Retrieve cached result
        cached = fingerprint_store.get_cached_similarity(hash_a, hash_b)
        
        if cached:
            print(f"✅ Result cached successfully")
            print(f"   Token similarity: {cached['token_similarity']}")
            print(f"   AST similarity: {cached['ast_similarity']}")
            
            # Verify values
            if (cached['token_similarity'] == 0.75 and 
                cached['ast_similarity'] == 0.60 and
                len(cached['matches']) == 1):
                print("✅ Cached values correct")
                return True
            else:
                print("❌ Cached values incorrect")
                return False
        else:
            print("❌ Failed to retrieve cached result")
            return False
            
    except Exception as e:
        print(f"❌ Caching test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("Redis Plagiarism Detection - Integration Tests")
    print("=" * 60)
    
    tests = [
        ("Redis Connection", test_redis_connection),
        ("Fingerprint Storage", test_fingerprint_storage),
        ("Similarity Calculation", test_similarity_calculation),
        ("Result Caching", test_caching),
    ]
    
    results = []
    for name, test_func in tests:
        try:
            result = test_func()
            results.append((name, result))
        except Exception as e:
            print(f"\n❌ {name} test crashed: {e}")
            results.append((name, False))
    
    # Summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Redis integration is working correctly.")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed. Please check the errors above.")
        return 1


if __name__ == "__main__":
    exit(main())
