"""
Redis-based plagiarism analyzer.
Uses Redis for all fingerprint storage and similarity calculations.
"""

from typing import List, Dict, Tuple, Optional
from plagiarism.analyzer import (
    tokenize_with_tree_sitter,
    compute_fingerprints,
    winnow_fingerprints,
    extract_ast_hashes,
    merge_adjacent_matches
)

# Default thresholds
DEFAULT_TOKEN_THRESHOLD = 0.15
DEFAULT_AST_THRESHOLD = 0.30
from plagiarism.redis_store import fingerprint_store


def analyze_plagiarism_redis(
    file1_path: str,
    file2_path: str,
    file1_hash: str,
    file2_hash: str,
    language: str = 'python',
    token_threshold: float = DEFAULT_TOKEN_THRESHOLD,
    ast_threshold: float = DEFAULT_AST_THRESHOLD,
) -> Tuple[float, float, List[Dict]]:
    """
    Analyze plagiarism between two files using Redis for fingerprints.
    
    This is the main entry point for Redis-based similarity calculation.
    
    Args:
        file1_path: Path to first file (for computing fingerprints if not cached)
        file2_path: Path to second file (for computing fingerprints if not cached)
        file1_hash: SHA256 hash of first file content
        file2_hash: SHA256 hash of second file content
        language: Programming language ('python' or 'cpp')
        token_threshold: Minimum token similarity to proceed to AST analysis
        ast_threshold: Minimum AST similarity to return matches
    
    Returns:
        Tuple of (token_similarity, ast_similarity, matches)
        - token_similarity: Token-based similarity score (0.0-1.0)
        - ast_similarity: AST-based similarity score (0.0-1.0)
        - matches: List of matching regions with line/column positions
    """
    
    # Step 1: Check cache first
    cached = fingerprint_store.get_cached_similarity(file1_hash, file2_hash)
    if cached:
        return (
            cached['token_similarity'],
            cached['ast_similarity'],
            cached['matches']
        )
    
    # Step 2: Ensure fingerprints are computed and stored in Redis
    _ensure_fingerprints_in_redis(file1_path, file1_hash, language)
    _ensure_fingerprints_in_redis(file2_path, file2_hash, language)
    
    # Step 3: Calculate token similarity using Redis
    token_sim, matches = fingerprint_store.calculate_token_similarity(
        file1_hash, file2_hash
    )
    
    # Early exit if token similarity is too low
    if token_sim < token_threshold:
        # Cache the result
        fingerprint_store.cache_similarity_result(
            file1_hash, file2_hash, token_sim, 0.0, []
        )
        return token_sim, 0.0, []
    
    # Step 4: Calculate AST similarity using Redis
    ast_sim = fingerprint_store.calculate_ast_similarity(file1_hash, file2_hash)
    
    # Step 5: Merge adjacent matches if AST similarity is high enough
    if ast_sim >= ast_threshold and matches:
        merged_matches = merge_adjacent_matches(matches)
    else:
        merged_matches = []
    
    # Step 6: Cache the result
    fingerprint_store.cache_similarity_result(
        file1_hash, file2_hash, token_sim, ast_sim, merged_matches
    )
    
    return token_sim, ast_sim, merged_matches


def _ensure_fingerprints_in_redis(file_path: str, file_hash: str, language: str) -> None:
    """
    Ensure fingerprints for a file are stored in Redis.
    Computes and stores them if not already cached.
    """
    # Check if already in Redis
    has_token = fingerprint_store.has_token_fingerprints(file_hash)
    has_ast = fingerprint_store.has_ast_fingerprints(file_hash)
    
    if has_token and has_ast:
        return  # Already cached
    
    # Compute token fingerprints if needed
    if not has_token:
        tokens = tokenize_with_tree_sitter(file_path, language)
        fingerprints = compute_fingerprints(tokens)
        winnowed = winnow_fingerprints(fingerprints)
        fingerprint_store.store_token_fingerprints(file_hash, winnowed)
    
    # Compute AST fingerprints if needed
    if not has_ast:
        ast_hashes = extract_ast_hashes(file_path, language, min_depth=3)
        fingerprint_store.store_ast_fingerprints(file_hash, ast_hashes)


def get_file_fingerprints_status(file_hash: str) -> Dict[str, bool]:
    """
    Check if fingerprints exist in Redis for a file.
    
    Returns:
        Dict with 'token' and 'ast' boolean flags
    """
    return {
        'token': fingerprint_store.has_token_fingerprints(file_hash),
        'ast': fingerprint_store.has_ast_fingerprints(file_hash)
    }


def clear_file_fingerprints(file_hash: str) -> None:
    """Remove all fingerprints for a file from Redis."""
    fingerprint_store.delete_file_fingerprints(file_hash)


def clear_all_fingerprints() -> None:
    """Clear all fingerprints from Redis. USE WITH CAUTION."""
    fingerprint_store.clear_all_fingerprints()
