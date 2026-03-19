# Parameter Fine-Tuning Guide

## Overview

The project includes **two fine-tuning scripts** to optimize plagiarism detection parameters:

1. **`fine_tune.py`** - Grid search (brute force) - good for small parameter spaces
2. **`fine_tune_smart.py`** - Successive halving with multi-fidelity evaluation - efficient for large search spaces

Both aim to find the optimal balance between **accuracy** (detection rate, exact match rate) and **match quality** (large, representative matching regions).

## Quick Comparison

| Feature | fine_tune.py (Grid Search) | fine_tune_smart.py (Successive Halving) |
|---------|---------------------------|------------------------------------------|
| Search method | Brute force grid | Multi-fidelity with pruning |
| Efficiency | Low (tests all combos) | High (prunes poor configs early) |
| Configs per round | All at once | Progressive (200 → 100 → 50 → 25) |
| Files per round | Fixed for all | Increasing (5 → 10 → 15 → 20) |
| Best for | Small parameter spaces | Large parameter spaces |
| Runtime | Longer for many combos | Shorter (avoids full eval on poor configs) |

## Part 1: Grid Search Tuner (`fine_tune.py`)

### Usage

```bash
python3 tests/plagiarism/fine_tune.py [OPTIONS]
```

### Key Options

- `--n-files N` - Number of source files to use (default: 10)
- `--n-clones N` - Clones per file per type (default: 1)
- `--max-combinations N` - Maximum parameter combinations to test (default: 50)
- `--start N` - Starting file index from dataset (default: 0)
- `--end N` - Ending file index from dataset (default: 50)
- `--types 1 2 3 4` - Which clone types to test (default: all 4 types)
- `--output FILE` - Save results to JSON file (e.g., `tuning_results.json`)
- `--resume FILE` - Resume from previous results file
- `--weight-accuracy W` - Weight for accuracy in score (default: 0.6)
- `--weight-match-size W` - Weight for match size in score (default: 0.4)

### Example

```bash
# Quick test with 5 combinations, 5 files
python3 tests/plagiarism/fine_tune.py --n-files 5 --max-combinations 5 --output results.json

# Comprehensive test with 100 combinations
python3 tests/plagiarism/fine_tune.py --n-files 20 --max-combinations 100 --start 0 --end 80 --output comprehensive.json
```

### Parameters Tuned (Limited Grid)

1. **`k`** (k-gram size): [4, 5, 6, 7, 8]
2. **`window_size`** (winnowing): [3, 4, 5, 6, 7]
3. **`min_depth`** (AST depth): [2, 3, 4, 5]
4. **`ast_threshold`** (early exit threshold): [0.20, 0.25, 0.30, 0.35, 0.40]
5. **`minimum_occurrences`** (fragment filter): [1, 2, 3]

**Total combinations:** 5×5×4×5×3 = 1,500 (but limited by `--max-combinations`)

## Part 2: Successive Halving Tuner (`fine_tune_smart.py`)

### Concept

Successive halving is a **multi-fidelity optimization algorithm**:
- Evaluate many configurations on a **small** test set (cheap, noisy estimate)
- Keep only the top performers
- Re-evaluate survivors on a **larger** test set (more reliable)
- Repeat until full dataset used

This is much more efficient than evaluating all configurations on the full dataset.

### Algorithm Structure

```
Round 1: 200 configs × 5 files each  →  keep top 100 (or 50)
Round 2: 100 configs × 10 files each →  keep top 50
Round 3: 50 configs × 15 files each  →  keep top 25
Round 4: 25 configs × 20 files each  →  final best config
```

Files used in each round are **non-overlapping** to ensure progressive reliability.

### Usage

```bash
python3 tests/plagiarism/fine_tune_smart.py [OPTIONS]
```

### Key Options

- `--n-files N` - Total files in pool (default: 100, need ≥50 for non-overlapping)
- `--n-clones N` - Clones per file per type (default: 1)
- `--initial-configs N` - Number of random configurations in Round 1 (default: 200)
- `--start N` - Starting file index from dataset (default: 0)
- `--end N` - Ending file index from dataset (default: 100)
- `--types 1 2 3 4` - Clone types to test (default: all)
- `--threshold F` - Detection threshold (default: 0.30)
- `--output FILE` - Output JSON file (default: `fine_tune_smart_results.json`)
- `--seed N` - Random seed (default: 42)
- `--weight-accuracy W` - Accuracy weight (default: 0.6)
- `--weight-match-size W` - Match quality weight (default: 0.4)
- `--keep-dataset` - Don't cleanup generated clones

### Example

```bash
# Full successive halving with 200 initial configs, 100 files
python3 tests/plagiarism/fine_tune_smart.py --n-files 100 --initial-configs 200 --start 0 --end 100 --output smart_results.json
```

### Parameter Ranges (Full Exploration)

The smart tuner samples randomly from the full parameter ranges:

1. **`k`**: 2-12 (11 values)
2. **`window_size`**: 2-12 (11 values)
3. **`min_depth`**: 2-12 (11 values)
4. **`ast_threshold`**: 0.00-0.95 step 0.05 (20 values)
5. **`minimum_occurrences`**: 2-5 (4 values)

**Total space:** 11×11×11×20×4 = **106,480** possible combinations

The algorithm samples a random subset (default 200) and prunes progressively.

### Scoring Function (Smart Tuner)

The smart tuner uses a **different scoring function** optimized for match quality:

```
score = (accuracy_component × weight_accuracy) + (fragment_quality × weight_match_size)
```

**Accuracy component:**
- Detection rate (0-1 normalized)

**Fragment quality component** (prioritized order):
1. Average fragment size (larger is better, sigmoid normalized)
2. Detection rate (already included)
3. Fragment count (fewer is better, exponential decay: e^(-count/5))
4. Total matched lines (sigmoid normalized)

**Weighted bonuses:**
- Large fragments (≥80% of file) receive 2× weight
- File size weighting applied during snippet calculation

### Output

The smart tuner produces:
- **Per-round summaries** showing top configurations
- **Complete JSON results** with all metrics by round
- **Top 10 final recommendations** after Round 4

JSON structure:
```json
{
  "all_results": [...],      // All configurations tested in all rounds
  "best_configs": [...],     // Top 25 after final round (ranked by score)
  "metadata": {...}          // Run configuration
}
```

Each result entry includes:
```json
{
  "params": { "k": 8, "window_size": 3, ... },
  "score": 0.8167,
  "results_summary": { ... },  // Detection rates, etc.
  "match_stats": {            // Match quality metrics
    "avg_fragment_size": 480.2,
    "avg_fragments_per_original": 183.6,
    "total_large_fragments": 0
  }
}
```

## Important Notes (Both Tuners)

- Both scripts **modify `cli/analyzer.py` in-place** but create a backup (`.backup`) and restore it at the end.
- Tests use **synthetic clones** generated by `py_clone_generator.py`.
- Generated clones are **cleaned up** after each combination (unless `--keep-dataset`).
- Test your own dataset by placing Python files in the `dataset/` directory.
- The `base` hash parameter is fixed at 257 and is **not tuned**.

## Interrupted Runs

Both tuners support resuming:

```bash
# First run (may be interrupted)
python3 fine_tune_smart.py --output results.json

# Resume later
python3 fine_tune_smart.py --output results.json --resume results.json
```

The script skips already tested parameter combinations.

## Understanding Results

Look for high scores that balance:

1. **Detection rate** (≥90% is excellent)
2. **Average fragment size** (larger = more useful for visual comparison)
3. **Low fragment count per original** (fewer, larger fragments)
4. **Exact match rate** (≥50% is good for Type 1 clones)

The composite score automatically weights these based on your `--weight-accuracy` and `--weight-match-size` settings.

## Recommendations

- For **exploratory tuning** with many parameters: Use `fine_tune_smart.py`
- For **final validation** of specific parameters: Use `fine_tune.py` with a narrow grid
- Always test with a diverse dataset (≥50 files) covering all clone types
- The recommended parameters will be printed at the end; apply them manually to `analyzer.py`

## Parameters Tuned

1. **`k`** (k-gram size): [4, 5, 6, 7, 8]
2. **`window_size`** (winnowing): [3, 4, 5, 6, 7]
3. **`min_depth`** (AST depth): [2, 3, 4, 5]
4. **`ast_threshold`** (early exit threshold): [0.20, 0.25, 0.30, 0.35, 0.40]
5. **`minimum_occurrences`** (fragment filter): [1, 2, 3]

**Note:** The `base` parameter for the rolling hash is kept fixed at 257 (a prime number) and is not tuned.

## Output

The script prints detailed info for each parameter combination:

- Parameter values
- Detection rate (%)
- Exact match rate (>=95%)
- Average similarity
- Average match size (total matching region size)
- Per-type performance breakdown

At the end, it shows the **top 5 ranked combinations** and recommends the best one based on a composite score.

## Composite Score

```
score = (accuracy_score * weight_accuracy) + (normalized_match_size * weight_match_size)
```

Where:
- `accuracy_score = (detection_rate * 0.5 + exact_rate * 0.5)`
- `normalized_match_size` uses sigmoid normalization

## Results File

If `--output` is specified, all results are saved as JSON with:
- Parameters for each run
- Full summary statistics
- Per-type breakdowns

## Important Notes

- The script **modifies `cli/analyzer.py` in-place** but creates a backup (`.backup`) and restores it at the end.
- Tests are run on synthetic clones generated by `py_clone_generator.py`.
- Cleanup is automatic - generated clones are deleted after each combination.
- To test on your own dataset, place Python files in `dataset/` directory.

## Resuming Interrupted Runs

Use `--resume previous_results.json` to continue from where you left off. The script will skip already tested parameter combinations.
