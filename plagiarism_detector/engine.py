"""
Main engine that implements plagiarism detection using the new modular architecture.

This module provides the `detect_plagiarism` function, which serves as the
primary entry point for the entire system. It orchestrates parsing, pipeline
execution, and result conversion.
"""

from typing import List

from .config import DetectionConfig
from .languages import get_language_profile
from .parsing.parser import ParserWrapper
from .detection.pipeline import DetectionPipeline
from .detection.exact_matcher import ExactLineMatcher
from .detection.renamed_matcher import RenamedLineMatcher
from .detection.structural_matcher import StructuralFunctionMatcher
from .detection.semantic_matcher import SemanticFunctionMatcher
from .detection.semantic_line_matcher import SemanticLineMatcher

# Import the legacy Match model for backward compatibility
# This comes from the existing plagiarism_core.models
try:
    from plagiarism_core.models import Match as LegacyMatch, PlagiarismType as LegacyPlagiarismType
except ImportError:
    # Fallback if moved
    from ..models import Match as LegacyMatch, PlagiarismType as LegacyPlagiarismType


def detect_plagiarism(
    source_a: str, source_b: str, lang_code: str = "python", min_match_lines: int = 2, **kwargs
) -> List[LegacyMatch]:
    """
    Detect plagiarism between two source code strings.

    This function replaces the monolithic original with a pipeline-based
    implementation that is modular, extensible, and easier to test.

    Args:
        source_a: First source code string
        source_b: Second source code string
        lang_code: Language identifier (e.g., "python", "java")
        min_match_lines: Minimum number of lines for a valid match
        **kwargs: Additional configuration options (forwarded to DetectionConfig)

    Returns:
        List of Match objects (legacy format) describing detected similarities.
    """
    # Build configuration
    config_dict = {
        "k": 3,
        "window_size": 4,
        "min_match_lines": min_match_lines,
        "merge_gap": 2,
        "semantic_threshold": 0.85,
        "hash_base": 257,
        "hash_mod": 10**9 + 7,
        "enable_type1": True,
        "enable_type2": True,
        "enable_type3": True,
        "enable_type4": True,
    }
    config_dict.update(kwargs)
    config = DetectionConfig(**config_dict)

    # Parse both sources
    parsed_a = ParserWrapper.parse(source_a, lang_code)
    parsed_b = ParserWrapper.parse(source_b, lang_code)

    # Build the detection pipeline
    matchers = [
        StructuralFunctionMatcher(config),
        SemanticFunctionMatcher(config),
        ExactLineMatcher(config),
        RenamedLineMatcher(config),
        SemanticLineMatcher(config),
    ]

    pipeline = DetectionPipeline(matchers, config)
    new_matches = pipeline.run(parsed_a, parsed_b)

    # Convert to legacy Match format (dict-based regions)
    legacy_matches = []
    for m in new_matches:
        legacy_matches.append(
            LegacyMatch(
                file1={
                    "start_line": m.file1_region.start.line,
                    "start_col": m.file1_region.start.col,
                    "end_line": m.file1_region.end.line,
                    "end_col": m.file1_region.end.col,
                },
                file2={
                    "start_line": m.file2_region.start.line,
                    "start_col": m.file2_region.start.col,
                    "end_line": m.file2_region.end.line,
                    "end_col": m.file2_region.end.col,
                },
                kgram_count=m.kgram_count,
                plagiarism_type=m.plagiarism_type.value
                if isinstance(m.plagiarism_type, LegacyPlagiarismType)
                else int(m.plagiarism_type),
                similarity=m.similarity,
                details=m.details,
                description=m.description,
            )
        )

    return legacy_matches
