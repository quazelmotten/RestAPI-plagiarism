import argparse
import json
import sys
import os

cli_dir = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(os.path.dirname(os.path.dirname(cli_dir)))
src_dir = os.path.join(project_dir, "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from cli.analyzer import Analyzer


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plagiarism Engine")
    parser.add_argument("--file1", type=str, required=True)
    parser.add_argument("--file2", type=str, required=True)
    parser.add_argument("--language", type=str, required=True)

    args = parser.parse_args()

    try:
        result = Analyzer().Start(args.file1, args.file2, args.language)
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"error": str(e)}))
        sys.exit(1)
