"""
Main analyzer orchestrating plagiarism detection.

Uses the multi-level plagiarism detector to classify matches by type
(Type 1-4) and produce enriched match data.
"""

import logging
from typing import List, Dict, Any, Tuple

from .ast_hash import extract_ast_hashes, ast_similarity as compute_ast_similarity, hash_ast_subtrees
from .canonicalizer import parse_file_once_from_string
from .plagiarism_detector import detect_plagiarism
from .models import (
    AnalysisResult,
    Match,
    PlagiarismType,
    SimilarityMetrics,
)

logger = logging.getLogger(__name__)


class Analyzer:
    """
    Main plagiarism analyzer.

    Uses the multi-level detector to find and classify matching code regions.
    Each match is annotated with a plagiarism type (1-4), similarity score,
    and optional details (renames, transformations).
    """

    def __init__(self):
        pass

    def analyze_sources(
        self,
        source1: str,
        source2: str,
        language: str = 'python',
        file1_path: str = None,
        file2_path: str = None,
    ) -> AnalysisResult:
        """
        Analyze plagiarism given source code strings.

        This method does not perform any file I/O - it operates purely on
        in-memory strings. This enables:
        - Unit testing without creating files
        - Analysis of code already in memory (from caches, databases, etc.)
        - Separation of concerns (I/O is handled by caller)

        Args:
            source1: First source code string
            source2: Second source code string
            language: Programming language
            file1_path: Optional path for metadata (not read)
            file2_path: Optional path for metadata (not read)

        Returns:
            AnalysisResult with similarity and typed matches
        """
        lines1 = source1.split('\n')
        lines2 = source2.split('\n')

        # Compute AST hashes directly from source strings
        try:
            from .canonicalizer import parse_file_once_from_string
            tree1, bytes1 = parse_file_once_from_string(source1, language)
            tree2, bytes2 = parse_file_once_from_string(source2, language)
            ast1 = hash_ast_subtrees(tree1.root_node)
            ast2 = hash_ast_subtrees(tree2.root_node)
        except Exception:
            logger.warning("Failed to parse sources for AST similarity, defaulting to 0", exc_info=True)
            ast1, ast2 = [], []

        ast_sim = compute_ast_similarity(ast1, ast2)

        # Multi-level matching using the full detector
        matches = detect_plagiarism(source1, source2, language)

        # Compute metrics
        total_lines_a = len([l for l in lines1 if l.strip()])
        total_lines_b = len([l for l in lines2 if l.strip()])
        matched_lines_a = sum(m.file1['end_line'] - m.file1['start_line'] + 1 for m in matches)
        matched_lines_b = sum(m.file2['end_line'] - m.file2['start_line'] + 1 for m in matches)

        metrics = SimilarityMetrics(
            left_covered=matched_lines_a,
            right_covered=matched_lines_b,
            left_total=max(total_lines_a, 1),
            right_total=max(total_lines_b, 1),
            similarity=max(matched_lines_a / max(total_lines_a, 1),
                          matched_lines_b / max(total_lines_b, 1)),
            longest_fragment=max((m.file1['end_line'] - m.file1['start_line'] + 1
                                 for m in matches), default=0),
        )

        return AnalysisResult(
            similarity_ratio=ast_sim,
            matches=matches,
            metrics=metrics,
            file1_path=file1_path or '',
            file2_path=file2_path or '',
            language=language
        )

    def analyze(
        self,
        file1: str,
        file2: str,
        language: str = 'python',
    ) -> AnalysisResult:
        """
        Complete plagiarism analysis between two files.

        This method reads the files from disk and calls analyze_sources().
        For in-memory analysis without file I/O, use analyze_sources() directly.

        Args:
            file1: Path to first file
            file2: Path to second file
            language: Programming language

        Returns:
            AnalysisResult with similarity and typed matches
        """
        with open(file1, 'r', encoding='utf-8', errors='ignore') as f:
            source1 = f.read()
        with open(file2, 'r', encoding='utf-8', errors='ignore') as f:
            source2 = f.read()

        return self.analyze_sources(
            source1, source2, language,
            file1_path=file1, file2_path=file2
        )

    def analyze_cached(
        self,
        file1_path: str,
        file2_path: str,
        file1_hash: str,
        file2_hash: str,
        get_fingerprints,  # Unused, kept for API compatibility
        get_ast_hashes,    # Callable[[str], List[int] | None]
        cache_fingerprints, # Unused, kept for API compatibility
        language: str = 'python',
    ) -> Tuple[float, List[Dict[str, Any]], Dict[str, Any]]:
        """
        Analyze with caching support (AST hashes only).

        Args:
            file1_path, file2_path: File paths
            file1_hash, file2_hash: File content hashes
            get_fingerprints: Unused (kept for API compat)
            get_ast_hashes: Function to get AST hashes from cache
            cache_fingerprints: Unused (kept for API compat)
            language: Programming language

        Returns:
            Tuple of (ast_similarity, matches_data, metrics)
        """
        # Read file contents
        with open(file1_path, 'r', encoding='utf-8', errors='ignore') as f:
            source1 = f.read()
        with open(file2_path, 'r', encoding='utf-8', errors='ignore') as f:
            source2 = f.read()

        lines1 = source1.split('\n')
        lines2 = source2.split('\n')

        # Get or compute AST hashes (for similarity score only)
        ast1 = get_ast_hashes(file1_hash)
        ast2 = get_ast_hashes(file2_hash)

        if ast1 is None:
            ast1 = extract_ast_hashes(file1_path, language)
        if ast2 is None:
            ast2 = extract_ast_hashes(file2_path, language)

        ast_sim = compute_ast_similarity(ast1, ast2)

        # Multi-level matching
        matches = detect_plagiarism(source1, source2, language)

        # Compute metrics (all match types contribute to coverage)
        total_lines_a = len([l for l in lines1 if l.strip()])
        total_lines_b = len([l for l in lines2 if l.strip()])
        matched_lines_a = sum(m.file1['end_line'] - m.file1['start_line'] + 1 for m in matches)
        matched_lines_b = sum(m.file2['end_line'] - m.file2['start_line'] + 1 for m in matches)

        # Transform matches to dict format (1-indexed line numbers)
        matches_data = []
        for match in matches:
            matches_data.append({
                'file1': {
                    'start_line': match.file1['start_line'] + 1,
                    'start_col': match.file1.get('start_col', 0),
                    'end_line': match.file1['end_line'] + 1,
                    'end_col': match.file1.get('end_col', 0),
                },
                'file2': {
                    'start_line': match.file2['start_line'] + 1,
                    'start_col': match.file2.get('start_col', 0),
                    'end_line': match.file2['end_line'] + 1,
                    'end_col': match.file2.get('end_col', 0),
                },
                'kgram_count': match.kgram_count,
                'plagiarism_type': match.plagiarism_type,
                'similarity': match.similarity,
                'details': match.details,
                'description': match.description,
            })

        return ast_sim, matches_data, {
            'left_covered': matched_lines_a,
            'right_covered': matched_lines_b,
            'left_total': total_lines_a,
            'right_total': total_lines_b,
            'similarity': max(matched_lines_a / max(total_lines_a, 1),
                            matched_lines_b / max(total_lines_b, 1)),
            'longest_fragment': max((m['file1']['end_line'] - m['file1']['start_line'] + 1
                                   for m in matches_data), default=0),
        }
