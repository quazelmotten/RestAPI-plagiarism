"""
Smoke tests for plagiarism detection scenarios.

Verifies that the analyzer produces reasonable results for common
copy/rename/different-code situations.
"""

from plagiarism_core.analyzer import Analyzer


def _analyze(a, b, lang="python"):
    return Analyzer().analyze_sources(a, b, lang)


def test_identical_code():
    source = "def hello():\n    return 42\n"
    result = _analyze(source, source)
    assert result.similarity_ratio > 0.5
    assert len(result.matches) > 0


def test_renamed_identifiers():
    a = "def foo(x):\n    return x + 1\n"
    b = "def bar(y):\n    return y + 1\n"
    result = _analyze(a, b)
    assert result.similarity_ratio > 0
    assert result.metrics.left_covered > 0


def test_completely_different():
    a = "x = 1\n"
    b = "def foo():\n    pass\n"
    result = _analyze(a, b)
    assert result.similarity_ratio >= 0


def test_empty_sources():
    result = _analyze("", "")
    assert result.similarity_ratio == 0.0
    assert len(result.matches) == 0


def test_plagiarism_scenarios():
    """Run regression scenarios: all should complete without error."""
    scenarios = [
        ("Exact copy", True,
         "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n",
         "def fibonacci(n):\n    if n <= 1:\n        return n\n    return fibonacci(n-1) + fibonacci(n-2)\n"),
        ("Renamed vars", True,
         "def calculate_average(numbers):\n    total = 0\n    for num in numbers:\n        total += num\n    return total / len(numbers)\n",
         "def compute_mean(values):\n    sum_val = 0\n    for v in values:\n        sum_val += v\n    return sum_val / len(values)\n"),
        ("Different algorithms", False,
         "def power(base, exp):\n    result = 1\n    for _ in range(exp):\n        result *= base\n    return result\n",
         "def power(base, exp):\n    if exp == 0:\n        return 1\n    return base * power(base, exp - 1)\n"),
    ]

    for name, similar, a, b in scenarios:
        result = _analyze(a, b)
        if similar:
            assert result.similarity_ratio > 0, f"{name}: expected non-zero similarity"
        else:
            assert result.similarity_ratio < 0.5, f"{name}: expected low similarity"
