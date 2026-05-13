#!/usr/bin/env python3
"""
Ultimate accuracy measurement tool for plagiarism detection.
...
"""

import argparse
import json
import multiprocessing
import sys
import time
from pathlib import Path
from typing import Any

# Ensure project root is on sys.path for both main process and workers
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Compute-intensive: import heavy modules inside worker to avoid fork issues

# ─── Worker function (must be top-level for pickle) ────────────────────────────

def _worker_analyze(task):
    """
    Worker process: analyze one (original, clone) pair.

    Returns dict with keys: orig, clone, similarity, detected, error, type
    """
    orig_path, clone_path, threshold, type_num = task
    try:
        # Import inside worker to avoid issues with fork + global state
        from plagiarism_core.analyzer import Analyzer
        analyzer = Analyzer()
        result = analyzer.analyze(orig_path, clone_path, language='python')
        similarity = result.similarity_ratio  # Already 0-1 float
        detected = similarity >= threshold
        return {
            'orig': str(orig_path),
            'clone': str(clone_path),
            'type': type_num,
            'similarity': similarity,
            'detected': detected,
            'error': None,
            'matches': len(result.matches),
        }
    except Exception as e:
        return {
            'orig': str(orig_path),
            'clone': str(clone_path),
            'type': type_num,
            'similarity': 0.0,
            'detected': False,
            'error': str(e),
            'matches': 0,
        }

# ─── Main measurement logic ────────────────────────────────────────────────────

def measure_accuracy(
    dataset_dir: Path,
    clones_dir: Path,
    types: list[int],
    threshold: float = 0.30,
    workers: int = 1,
    progress: bool = True,
) -> dict[str, Any]:
    """
    Run accuracy measurement on generated clones using parallel workers.

    Args:
        dataset_dir: Directory containing original source files (*.py)
        clones_dir: Directory containing generated clones organized by typeN subdirs
        types: List of clone types to evaluate (e.g., [1,2,3,4])
        threshold: Detection threshold (0-1) for binary classification
        workers: Number of parallel worker processes
        progress: Whether to print progress

    Returns:
        Results dictionary with summary, by_type, and details.
    """
    if progress:
        print("=" * 60)
        print("ACCURACY MEASUREMENT")
        print("=" * 60)
        print(f"Dataset: {dataset_dir}")
        print(f"Clones:  {clones_dir}")
        print(f"Types:   {types}")
        print(f"Threshold: {threshold:.1%}")
        print(f"Workers: {workers}")
        print()

    # Build task list
    tasks = []
    for type_num in types:
        type_dir = clones_dir / f"type{type_num}"
        if not type_dir.exists():
            print(f"Warning: {type_dir} does not exist, skipping type {type_num}")
            continue

        clone_files = sorted(type_dir.glob("*.py"))
        for clone_file in clone_files:
            # Extract original stem: {stem}_type{t}_{j}.py
            # Files are like: constants_type1_1.py (original), constants_type1_2.py (clone)
            parts = clone_file.stem.rsplit("_type", 1)
            if len(parts) != 2:
                continue
            original_stem = parts[0]
            original_file = dataset_dir / f"{original_stem}.py"
            if not original_file.exists():
                continue
            # Check if this is clone (ending with _1 for full dataset)
            if clone_file.stem.endswith("_1"):
                tasks.append((original_file, clone_file, threshold, type_num))

    total_tasks = len(tasks)
    if progress:
        print(f"Total test pairs: {total_tasks}")

    if total_tasks == 0:
        print("Error: No valid pairs found. Check dataset/clones directories.")
        return {"summary": {}, "by_type": {}, "details": []}

    # Use multiprocessing Pool
    results = {"summary": {}, "by_type": {}, "details": []}
    by_type_data = {t: {"total": 0, "detected": 0, "similarities": [], "errors": 0} for t in types}

    start_time = time.time()
    completed = 0

    # Chunk tasks for progress reporting
    chunk_size = max(1, total_tasks // 100)

    with multiprocessing.Pool(processes=workers) as pool:
        # Use imap_unordered for better load balancing
        for result in pool.imap_unordered(_worker_analyze, tasks, chunksize=chunk_size):
            results["details"].append(result)
            t = result["type"]
            by_type_data[t]["total"] += 1
            if result["error"]:
                by_type_data[t]["errors"] += 1
            else:
                sim = result["similarity"]
                by_type_data[t]["similarities"].append(sim)
                if result["detected"]:
                    by_type_data[t]["detected"] += 1
            completed += 1
            if progress and completed % 100 == 0:
                elapsed = time.time() - start_time
                rate = completed / elapsed if elapsed > 0 else 0
                eta = (total_tasks - completed) / rate if rate > 0 else 0
                print(f"  Processed {completed}/{total_tasks}  ({rate:.1f} pairs/s, ETA {eta/60:.1f}m)")

    # Compute per-type metrics
    results["by_type"] = {}
    all_similarities = []
    total_detected = 0
    total_tests = 0
    total_errors = 0
    total_exact = 0

    for type_num in types:
        data = by_type_data[type_num]
        total = data["total"]
        if total == 0:
            continue
        detected = data["detected"]
        similarities = data["similarities"]
        errors = data["errors"]

        avg_sim = sum(similarities) / len(similarities) if similarities else 0.0
        exact = sum(1 for s in similarities if s >= 0.95)
        detection_rate = detected / total if total else 0.0
        exact_rate = exact / total if total else 0.0

        results["by_type"][f"type{type_num}"] = {
            "total": total,
            "detected": detected,
            "detection_rate": detection_rate,
            "exact": exact,
            "exact_rate": exact_rate,
            "avg_similarity": avg_sim,
            "errors": errors,
            "similarities": similarities,  # Keep for distribution/ROC
        }

        all_similarities.extend(similarities)
        total_tests += total
        total_detected += detected
        total_errors += errors
        total_exact += exact

    # Overall summary
    overall_detection = total_detected / total_tests if total_tests else 0.0
    overall_exact = total_exact / total_tests if total_tests else 0.0
    overall_avg_sim = sum(all_similarities) / len(all_similarities) if all_similarities else 0.0

    results["summary"] = {
        "total_tests": total_tests,
        "total_detected": total_detected,
        "total_exact": total_exact,
        "total_errors": total_errors,
        "overall_detection_rate": overall_detection,
        "overall_exact_rate": overall_exact,
        "avg_similarity": overall_avg_sim,
    }

    elapsed_total = time.time() - start_time
    if progress:
        print(f"\nCompleted in {elapsed_total/60:.1f} minutes")
        print(f"Rate: {total_tasks/elapsed_total:.1f} pairs/sec")

    return results

# ─── Report generation ─────────────────────────────────────────────────────────

def generate_report(results: dict[str, Any], format: str = "json", output_path: Path | None = None) -> str:
    """
    Generate human-readable report in JSON or HTML format.
    Returns report string or writes to file if output_path provided.
    """
    if format == "json":
        report = json.dumps(results, indent=2)
        if output_path:
            output_path.write_text(report)
        return report

    elif format == "html":
        html = _generate_html_report(results)
        if output_path:
            output_path.write_text(html)
        return html

    else:
        raise ValueError(f"Unsupported format: {format}")

def _generate_html_report(results: dict[str, Any]) -> str:
    """Create an HTML report with charts (using pure HTML/CSS, no external libs)."""

    def rate_class(r: float) -> str:
        return "rate-good" if r >= 0.9 else "rate-medium" if r >= 0.7 else "rate-poor"

    summary = results["summary"]
    by_type = results["by_type"]

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Plagiarism Detection Accuracy Report</title>
    <style>
        body {{ font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; border-bottom: 1px solid #bdc3c7; padding-bottom: 5px; margin-top: 30px; }}
        .summary-card {{
            display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px; margin: 20px 0;
        }}
        .card {{
            background: #f8f9fa; border-radius: 8px; padding: 15px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .card h3 {{ margin: 0 0 10px 0; color: #2c3e50; font-size: 14px; text-transform: uppercase; }}
        .card .value {{ font-size: 28px; font-weight: bold; color: #3498db; }}
        .card .label {{ font-size: 12px; color: #7f8c8d; }}
        .rate-good {{ color: #27ae60; font-weight: bold; }}
        .rate-medium {{ color: #f39c12; font-weight: bold; }}
        .rate-poor {{ color: #e74c3c; font-weight: bold; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #3498db; color: white; }}
        tr:hover {{ background-color: #f5f6fa; }}
        .bar-container {{ width: 100%; background: #ecf0f1; border-radius: 4px; height: 20px; overflow: hidden; }}
        .bar {{ height: 100%; background: linear-gradient(90deg, #3498db, #2ecc71); transition: width 0.3s; }}
        pre {{ background: #2c3e50; color: #ecf0f1; padding: 15px; border-radius: 5px; overflow-x: auto; }}
    </style>
</head>
<body>
    <h1>🎯 Plagiarism Detection Accuracy Report</h1>

    <h2>📊 Overall Summary</h2>
    <div class="summary-card">
        <div class="card">
            <h3>Total Tests</h3>
            <div class="value">{summary['total_tests']:,}</div>
        </div>
        <div class="card">
            <h3>Detection Rate</h3>
            <div class="value {rate_class(summary['overall_detection_rate'])}">{summary['overall_detection_rate']:.1%}</div>
            <div class="label">(≥ threshold: {0.30:.0%})</div>
        </div>
        <div class="card">
            <h3>Exact Match Rate</h3>
            <div class="value {rate_class(summary['overall_exact_rate'])}">{summary['overall_exact_rate']:.1%}</div>
            <div class="label">(≥ 95% similarity)</div>
        </div>
        <div class="card">
            <h3>Avg Similarity</h3>
            <div class="value">{summary['avg_similarity']:.1%}</div>
        </div>
        <div class="card">
            <h3>Errors</h3>
            <div class="value" style="color: {'#e74c3c' if summary['total_errors']>0 else '#27ae60'}">{summary['total_errors']}</div>
        </div>
    </div>

    <h2>📈 Per-Type Breakdown</h2>
    <table>
        <thead>
            <tr>
                <th>Type</th>
                <th>Tests</th>
                <th>Detected</th>
                <th>Detection Rate</th>
                <th>Exact</th>
                <th>Exact Rate</th>
                <th>Avg Similarity</th>
                <th>Errors</th>
                <th>Sim Distribution</th>
            </tr>
        </thead>
        <tbody>
"""

    for type_name in sorted(by_type.keys()):
        d = by_type[type_name]
        if d["total"] == 0:
            continue
        detection_pct = d["detection_rate"] * 100
        exact_pct = d["exact_rate"] * 100
        avg_sim_pct = d["avg_similarity"] * 100

        # Bar widths
        det_width = detection_pct
        exact_width = exact_pct

        # Compute simple stats
        sims = d["similarities"]
        if sims:
            min_s = min(sims)
            max_s = max(sims)
            med_s = sorted(sims)[len(sims)//2]
            stats = f"min={min_s:.2f}, med={med_s:.2f}, max={max_s:.2f}"
        else:
            stats = "N/A"

        html += f"""
            <tr>
                <td><strong>{type_name.upper()}</strong></td>
                <td>{d['total']}</td>
                <td>{d['detected']}</td>
                <td>
                    <div class="bar-container"><div class="bar" style="width:{det_width:.0f}%"></div></div>
                    {detection_pct:.1f}%
                </td>
                <td>{d['exact']}</td>
                <td>
                    <div class="bar-container"><div class="bar" style="width:{exact_width:.0f}%"></div></div>
                    {exact_pct:.1f}%
                </td>
                <td>{avg_sim_pct:.1f}%</td>
                <td>{d['errors']}</td>
                <td><pre>{stats}</pre></td>
            </tr>
"""

    html += """
        </tbody>
    </table>

    <h2>📝 Detailed Results (Sample)</h2>
    <p>Showing first 100 results. Full data in JSON output.</p>
    <table>
        <thead>
            <tr><th>Type</th><th>Original</th><th>Clone</th><th>Similarity</th><th>Detected</th><th>Error</th></tr>
        </thead>
        <tbody>
"""

    for detail in results["details"][:100]:
        css_class = "rate-good" if detail.get("detected") else "rate-poor"
        orig_name = Path(detail['orig']).name
        clone_name = Path(detail['clone']).name
        html += f"""
            <tr>
                <td>{detail['type']}</td>
                <td><code>{orig_name}</code></td>
                <td><code>{clone_name}</code></td>
                <td class="{css_class}">{detail['similarity']:.1%}</td>
                <td>{'✔' if detail['detected'] else '✘'}</td>
                <td>{detail.get('error') or '-'}</td>
            </tr>
"""

    html += """
        </tbody>
    </table>

    <footer style="margin-top: 50px; color: #7f8c8d; text-align: center; font-size: 12px;">
        Report generated by accuracy_measure.py | """ + time.strftime("%Y-%m-%d %H:%M:%S") + """
    </footer>
</body>
</html>"""

    return html

# ─── CLI ────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Accuracy measurement for plagiarism detection")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Measure command
    meas_parser = subparsers.add_parser("measure", help="Measure accuracy on pre-generated clones")
    meas_parser.add_argument("--dataset", required=True, type=Path, help="Directory with original .py files")
    meas_parser.add_argument("--clones", required=True, type=Path, help="Directory with clone typeN subdirectories")
    meas_parser.add_argument("--types", type=int, nargs="+", default=[1,2,3,4], help="Clone types to test")
    meas_parser.add_argument("--threshold", type=float, default=0.30, help="Detection threshold (0-1)")
    meas_parser.add_argument("--workers", type=int, default=multiprocessing.cpu_count(), help="Parallel workers")
    meas_parser.add_argument("--output", type=Path, required=True, help="Output JSON file for results")
    meas_parser.add_argument("--report", type=Path, help="Optional HTML report path")

    # Run command (generate + measure)
    run_parser = subparsers.add_parser("run", help="Generate clones and measure accuracy in one step")
    run_parser.add_argument("--dataset", required=True, type=Path, help="Directory with original .py files")
    run_parser.add_argument("--output-dir", type=Path, required=True, help="Output directory for clones and results")
    run_parser.add_argument("--types", type=int, nargs="+", default=[1,2,3,4], help="Clone types to generate")
    run_parser.add_argument("--clones-per-file", type=int, default=1, help="Number of clones per file per type")
    run_parser.add_argument("--file-start", type=int, default=0, help="Start file index")
    run_parser.add_argument("--file-end", type=int, default=None, help="End file index (default: all)")
    run_parser.add_argument("--seed", type=int, default=42, help="Random seed")
    run_parser.add_argument("--threshold", type=float, default=0.30, help="Detection threshold")
    run_parser.add_argument("--workers", type=int, default=multiprocessing.cpu_count(), help="Parallel workers for measurement")
    run_parser.add_argument("--skip-generation", action="store_true", help="Skip clone generation if already done")

    args = parser.parse_args()

    if args.command == "measure":
        results = measure_accuracy(
            dataset_dir=args.dataset,
            clones_dir=args.clones,
            types=args.types,
            threshold=args.threshold,
            workers=args.workers,
        )
        # Save JSON
        args.output.write_text(json.dumps(results, indent=2))
        print(f"\nResults saved to {args.output}")

        # Optionally generate HTML report
        if args.report:
            html = generate_report(results, format="html")
            args.report.write_text(html)
            print(f"HTML report saved to {args.report}")

    elif args.command == "run":
        clones_dir = args.output_dir / "clones"
        results_json = args.output_dir / "results.json"
        results_html = args.output_dir / "report.html"

        # Step 1: Generate clones (unless skipped)
        if not args.skip_generation:
            print("=" * 60)
            print("STEP 1: Generating clones")
            print("=" * 60)
            from tests.plagiarism.py_clone_generator import generate_dataset

            end_idx = args.file_end
            if end_idx is None:
                # Count files in dataset
                all_files = list(args.dataset.glob("*.py"))
                end_idx = len(all_files)

            generate_dataset(
                source_dir=str(args.dataset),
                output_dir=str(clones_dir),
                n=args.clones_per_file,
                file_range=(args.file_start, args.file_end),
                types=args.types,
                seed=args.seed,
            )
            print()

        # Step 2: Measure accuracy
        print("=" * 60)
        print("STEP 2: Measuring accuracy")
        print("=" * 60)
        results = measure_accuracy(
            dataset_dir=args.dataset,
            clones_dir=clones_dir,
            types=args.types,
            threshold=args.threshold,
            workers=args.workers,
        )

        # Save results
        results_json.parent.mkdir(parents=True, exist_ok=True)
        results_json.write_text(json.dumps(results, indent=2))
        print(f"\nResults saved to {results_json}")

        # Generate HTML report
        html = generate_report(results, format="html")
        results_html.write_text(html)
        print(f"HTML report saved to {results_html}")

if __name__ == "__main__":
    main()
