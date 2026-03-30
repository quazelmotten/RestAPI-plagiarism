#!/usr/bin/env python3
"""
Command-line interface for plagiarism detection.

Usage:
    python -m plagiarism_detector.cli <file_a> <file_b> [--lang <language>] [--min-lines <n>]

Example:
    python -m plagiarism_detector.cli student1.py student2.py --lang python
"""

import argparse
import sys
from pathlib import Path

from .engine import detect_plagiarism
from .config import DetectionConfig


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect plagiarism between two source files.")
    parser.add_argument("file_a", type=Path, help="First source file")
    parser.add_argument("file_b", type=Path, help="Second source file")
    parser.add_argument("--lang", type=str, default="python", help="Language (default: python)")
    parser.add_argument("--min-lines", type=int, default=2, help="Minimum match lines (default: 2)")
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.0,
        help="Minimum similarity threshold to report (default: 0.0)",
    )

    args = parser.parse_args(argv)

    # Read files
    try:
        source_a = args.file_a.read_text(encoding="utf-8")
        source_b = args.file_b.read_text(encoding="utf-8")
    except Exception as e:
        print(f"Error reading files: {e}", file=sys.stderr)
        return 1

    # Run detection
    try:
        matches = detect_plagiarism(
            source_a, source_b, lang_code=args.lang, min_match_lines=args.min_lines
        )
    except Exception as e:
        print(f"Detection failed: {e}", file=sys.stderr)
        return 1

    # Filter by similarity if threshold given
    if args.threshold > 0:
        matches = [m for m in matches if m.similarity >= args.threshold]

    # Print results
    if not matches:
        print("No plagiarism detected.")
        return 0

    print(f"Found {len(matches)} similar region(s):")
    for i, m in enumerate(matches, 1):
        print(f"\nMatch {i}:")
        print(f"  Type: {m.plagiarism_type}")
        print(f"  File A: lines {m.file1['start_line'] + 1}-{m.file1['end_line'] + 1}")
        print(f"  File B: lines {m.file2['start_line'] + 1}-{m.file2['end_line'] + 1}")
        print(f"  Similarity: {m.similarity:.2%}")
        if m.description:
            print(f"  Details: {m.description}")
        if m.details and "renames" in m.details:
            rename_strs = [f"{r['original']}->{r['renamed']}" for r in m.details["renames"]]
            print(f"  Renames: {', '.join(rename_strs)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
