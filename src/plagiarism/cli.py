#!/usr/bin/env python3
"""
Plagiarism detection CLI tool.
Usage: 
  python cli.py analyze file1 file2 [--language LANG] [--threshold THRESHOLD]
  python cli.py fingerprint file1 [--language LANG]
Outputs JSON to stdout.
"""

import argparse
import json
import sys
import os

cli_dir = os.path.dirname(os.path.abspath(__file__))
src_dir = os.path.dirname(cli_dir)
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from plagiarism.analyzer import (
    analyze_plagiarism,
    tokenize_with_tree_sitter,
    winnow_fingerprints,
    compute_fingerprints,
    extract_ast_hashes,
)


def cmd_analyze(args):
    if not os.path.exists(args.file1):
        print(json.dumps({"error": f"File not found: {args.file1}"}))
        sys.exit(1)
    
    if not os.path.exists(args.file2):
        print(json.dumps({"error": f"File not found: {args.file2}"}))
        sys.exit(1)
    
    try:
        ast_similarity, matches = analyze_plagiarism(
            args.file1,
            args.file2,
            language=args.language,
            ast_threshold=args.threshold
        )
        
        matches_serializable = []
        for match in matches:
            matches_serializable.append({
                "file1": {
                    "start_line": match["file1"]["start_line"],
                    "start_col": match["file1"]["start_col"],
                    "end_line": match["file1"]["end_line"],
                    "end_col": match["file1"]["end_col"],
                },
                "file2": {
                    "start_line": match["file2"]["start_line"],
                    "start_col": match["file2"]["start_col"],
                    "end_line": match["file2"]["end_line"],
                    "end_col": match["file2"]["end_col"],
                }
            })
        
        result = {
            "similarity": round(ast_similarity * 100, 2),
            "similarity_ratio": ast_similarity,
            "matches": matches_serializable,
            "file1": args.file1,
            "file2": args.file2,
            "language": args.language
        }
        
        print(json.dumps(result))
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


def cmd_fingerprint(args):
    if not os.path.exists(args.file):
        print(json.dumps({"error": f"File not found: {args.file}"}))
        sys.exit(1)
    
    try:
        tokens = tokenize_with_tree_sitter(args.file, args.language)
        fingerprints = winnow_fingerprints(compute_fingerprints(tokens))
        ast_hashes = extract_ast_hashes(args.file, args.language, min_depth=3)
        
        fingerprints_serializable = []
        for fp in fingerprints:
            fingerprints_serializable.append({
                "hash": fp["hash"],
                "start": list(fp["start"]),
                "end": list(fp["end"]),
            })
        
        tokens_serializable = [
            {"type": t[0], "start": list(t[1]), "end": list(t[2])}
            for t in tokens
        ]
        
        result = {
            "file": args.file,
            "language": args.language,
            "fingerprints": fingerprints_serializable,
            "ast_hashes": ast_hashes,
            "tokens": tokens_serializable,
            "token_count": len(tokens),
            "fingerprint_count": len(fingerprints),
        }
        
        print(json.dumps(result))
        
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="Plagiarism detection tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    analyze_parser = subparsers.add_parser("analyze", help="Compare two files for similarity")
    analyze_parser.add_argument("file1", help="Path to the first file")
    analyze_parser.add_argument("file2", help="Path to the second file")
    analyze_parser.add_argument("--language", "-l", default="python", choices=["python", "cpp"],
                                help="Programming language (default: python)")
    analyze_parser.add_argument("--threshold", "-t", type=float, default=0.30,
                                help="AST similarity threshold (default: 0.30)")
    
    fingerprint_parser = subparsers.add_parser("fingerprint", help="Extract fingerprints from a file")
    fingerprint_parser.add_argument("file", help="Path to the file")
    fingerprint_parser.add_argument("--language", "-l", default="python", choices=["python", "cpp"],
                                    help="Programming language (default: python)")
    
    args = parser.parse_args()
    
    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "fingerprint":
        cmd_fingerprint(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()