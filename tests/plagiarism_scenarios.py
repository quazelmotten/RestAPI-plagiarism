"""
Comprehensive plagiarism detection test scenarios.

Tests all combinations of software plagiarism a professor might encounter.
Each scenario has:
  - Original student's code
  - Submitted code (potentially plagiarized)
  - Expected match types
  - Description of what changed
"""

from plagiarism_core.models import PlagiarismType
from plagiarism_core.plagiarism_detector import detect_plagiarism

# ─── TYPE 1: EXACT COPY ────────────────────────────────────────────────

SCENARIOS = []

# 1a: Identical code
SCENARIOS.append(
    {
        "id": "1a",
        "name": "Exact copy",
        "desc": "Identical code submitted by two students",
        "a": """def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(fibonacci(10))
""",
        "b": """def fibonacci(n):
    if n <= 1:
        return n
    return fibonacci(n-1) + fibonacci(n-2)

print(fibonacci(10))
""",
        "expected": {"EXACT"},
    }
)

# 1b: Whitespace-only changes
SCENARIOS.append(
    {
        "id": "1b",
        "name": "Whitespace changes",
        "desc": "Copied with extra blank lines and reindentation",
        "a": """def add(a, b):
    return a + b

def multiply(a, b):
    return a * b
""",
        "b": """def add(a, b):
        return a + b


def multiply(a, b):
        return a * b
""",
        "expected": {"EXACT"},
    }
)

# 1c: Comment additions (still exact match on code lines)
SCENARIOS.append(
    {
        "id": "1c",
        "name": "Comment additions",
        "desc": "Copied and added comments",
        "a": """def binary_search(arr, target):
    low = 0
    high = len(arr) - 1
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1
""",
        "b": """# Binary search implementation
def binary_search(arr, target):
    low = 0           # Start of range
    high = len(arr) - 1  # End of range
    while low <= high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
    return -1  # Not found
""",
        "expected": {"EXACT", "RENAMED"},
    }
)


# ─── TYPE 2: IDENTIFIER RENAMING ───────────────────────────────────────

# 2a: Variable renaming
SCENARIOS.append(
    {
        "id": "2a",
        "name": "Variable renaming",
        "desc": "All variable names changed",
        "a": """def calculate_average(numbers):
    total = 0
    count = 0
    for num in numbers:
        total += num
        count += 1
    return total / count
""",
        "b": """def compute_mean(values):
    sum_val = 0
    n = 0
    for v in values:
        sum_val += v
        n += 1
    return sum_val / n
""",
        "expected": {"RENAMED"},
    }
)

# 2b: Function and parameter renaming
SCENARIOS.append(
    {
        "id": "2b",
        "name": "Function+parameter renaming",
        "desc": "Function name and all parameters renamed",
        "a": """def find_max_value(arr):
    max_val = arr[0]
    for item in arr:
        if item > max_val:
            max_val = item
    return max_val
""",
        "b": """def get_largest(data):
    result = data[0]
    for element in data:
        if element > result:
            result = element
    return result
""",
        "expected": {"RENAMED"},
    }
)

# 2c: Class name renaming
SCENARIOS.append(
    {
        "id": "2c",
        "name": "Class renaming",
        "desc": "Class name changed",
        "a": """class Stack:
    def __init__(self):
        self.items = []

    def push(self, item):
        self.items.append(item)

    def pop(self):
        return self.items.pop()
""",
        "b": """class LIFOCollection:
    def __init__(self):
        self.data = []

    def push(self, element):
        self.data.append(element)

    def pop(self):
        return self.data.pop()
""",
        "expected": {"RENAMED"},
    }
)

# 2d: Mixed rename (some names kept, some changed)
SCENARIOS.append(
    {
        "id": "2d",
        "name": "Partial renaming",
        "desc": "Some identifiers kept, some changed",
        "a": """def sort_list(items):
    n = len(items)
    for i in range(n):
        for j in range(0, n-i-1):
            if items[j] > items[j+1]:
                items[j], items[j+1] = items[j+1], items[j]
    return items
""",
        "b": """def sort_list(data):
    n = len(data)
    for i in range(n):
        for j in range(0, n-i-1):
            if data[j] > data[j+1]:
                data[j], data[j+1] = data[j+1], data[j]
    return data
""",
        "expected": {"RENAMED"},
    }
)


# ─── TYPE 3: CODE REORDERING ──────────────────────────────────────────

# 3a: Function order swapped
SCENARIOS.append(
    {
        "id": "3a",
        "name": "Function reordering",
        "desc": "Functions defined in different order",
        "a": """def add(a, b):
    return a + b

def multiply(a, b):
    return a * b

def subtract(a, b):
    return a - b
""",
        "b": """def subtract(a, b):
    return a - b

def multiply(a, b):
    return a * b

def add(a, b):
    return a + b
""",
        "expected": {"EXACT", "REORDERED"},
    }
)

# 3b: Class methods reordered
SCENARIOS.append(
    {
        "id": "3b",
        "name": "Method reordering",
        "desc": "Class methods in different order",
        "a": """class Calculator:
    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b
""",
        "b": """class Calculator:
    def multiply(self, a, b):
        return a * b

    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b
""",
        "expected": {"EXACT", "REORDERED"},
    }
)

# 3c: Functions reordered AND renamed
SCENARIOS.append(
    {
        "id": "3c",
        "name": "Reordering + renaming",
        "desc": "Functions reordered with names changed",
        "a": """def process_data(data):
    cleaned = [x.strip() for x in data]
    return cleaned

def analyze_data(data):
    return sum(data) / len(data)
""",
        "b": """def compute_average(values):
    return sum(values) / len(values)

def clean_input(raw):
    cleaned = [x.strip() for x in raw]
    return cleaned
""",
        "expected": {"RENAMED", "REORDERED"},
    }
)


# ─── TYPE 4: SEMANTIC / STRUCTURAL CHANGES ─────────────────────────────

# 4a: For loop to while loop
SCENARIOS.append(
    {
        "id": "4a",
        "name": "For → While loop",
        "desc": "Loop type changed",
        "a": """def sum_list(numbers):
    total = 0
    for n in numbers:
        total += n
    return total
""",
        "b": """def sum_list(numbers):
    total = 0
    i = 0
    while i < len(numbers):
        total += numbers[i]
        i += 1
    return total
""",
        "expected": {"SEMANTIC"},
    }
)

# 4b: List comprehension to explicit loop
SCENARIOS.append(
    {
        "id": "4b",
        "name": "Comprehension → Explicit loop",
        "desc": "List comprehension expanded to for loop",
        "a": """def get_squares(n):
    return [x * x for x in range(n)]
""",
        "b": """def get_squares(n):
    result = []
    for x in range(n):
        result.append(x * x)
    return result
""",
        "expected": {"SEMANTIC"},
    }
)

# 4c: If/else restructured
SCENARIOS.append(
    {
        "id": "4c",
        "name": "Conditional restructuring",
        "desc": "If/elif chain inverted",
        "a": """def classify(score):
    if score >= 90:
        return "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C"
    else:
        return "F"
""",
        "b": """def classify(score):
    if score < 70:
        return "F"
    elif score < 80:
        return "C"
    elif score < 90:
        return "B"
    else:
        return "A"
""",
        "expected": {"SEMANTIC"},
    }
)

# 4d: String formatting changed
SCENARIOS.append(
    {
        "id": "4d",
        "name": "String formatting",
        "desc": "f-string to format()",
        "a": """def greet(name, age):
    return f"Hello {name}, you are {age} years old"
""",
        "b": """def greet(name, age):
    return "Hello {}, you are {} years old".format(name, age)
""",
        "expected": {"SEMANTIC", "RENAMED"},
    }
)

# 4e: Augmented assignment to explicit assignment
SCENARIOS.append(
    {
        "id": "4e",
        "name": "Assignment style change",
        "desc": "+= to explicit addition",
        "a": """def process(items):
    total = 0
    for x in items:
        total += x
        total *= 2
    return total
""",
        "b": """def process(items):
    total = 0
    for x in items:
        total = total + x
        total = total * 2
    return total
""",
        "expected": {"SEMANTIC"},
    }
)


# ─── MIXED TYPES ───────────────────────────────────────────────────────

# 5a: Some functions exact, some renamed
SCENARIOS.append(
    {
        "id": "5a",
        "name": "Mixed: exact + renamed",
        "desc": "Some functions copied exactly, others renamed",
        "a": """import os

def read_file(path):
    with open(path) as f:
        return f.read()

def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)

def get_extension(path):
    return os.path.splitext(path)[1]
""",
        "b": """import os

def read_file(fp):
    with open(fp) as fh:
        return fh.read()

def write_file(fp, data):
    with open(fp, 'w') as fh:
        fh.write(data)

def get_extension(path):
    return os.path.splitext(path)[1]
""",
        "expected": {"EXACT", "RENAMED"},
    }
)

# 5b: Renamed + reordered
SCENARIOS.append(
    {
        "id": "5b",
        "name": "Renamed + reordered",
        "desc": "Functions renamed and order changed",
        "a": """def validate_input(data):
    if not data:
        raise ValueError("Empty")
    return True

def transform_data(data):
    return [x.upper() for x in data]
""",
        "b": """def convert(items):
    return [x.upper() for x in items]

def check(items):
    if not items:
        raise ValueError("Empty")
    return True
""",
        "expected": {"RENAMED"},
    }
)


# ─── NOT PLAGIARISM (should NOT match strongly) ────────────────────────

# 6a: Common boilerplate (import statements, class skeletons)
SCENARIOS.append(
    {
        "id": "6a",
        "name": "Common boilerplate",
        "desc": "Standard imports and class skeleton — NOT plagiarism",
        "a": """import os
import sys

class Solution:
    def __init__(self):
        self.data = []

    def solve(self):
        pass
""",
        "b": """import os
import sys

class Solution:
    def __init__(self):
        self.data = []

    def solve(self):
        pass
""",
        "expected": {"EXACT"},  # will match as exact but should be small
        "note": "Common boilerplate — expect small match regions",
    }
)

# 6b: Completely different implementations
SCENARIOS.append(
    {
        "id": "6b",
        "name": "Different implementations",
        "desc": "Two different sorting algorithms — NOT plagiarism",
        "a": """def sort(data):
    # Bubble sort
    n = len(data)
    for i in range(n):
        for j in range(0, n-i-1):
            if data[j] > data[j+1]:
                data[j], data[j+1] = data[j+1], data[j]
    return data
""",
        "b": """def sort(data):
    # Merge sort
    if len(data) <= 1:
        return data
    mid = len(data) // 2
    left = sort(data[:mid])
    right = sort(data[mid:])
    return merge(left, right)

def merge(left, right):
    result = []
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i] <= right[j]:
            result.append(left[i])
            i += 1
        else:
            result.append(right[j])
            j += 1
    result.extend(left[i:])
    result.extend(right[j:])
    return result
""",
        "expected": set(),  # Should have no significant matches
    }
)

# 6c: Same problem, different approach (gcd)
SCENARIOS.append(
    {
        "id": "6c",
        "name": "Same problem different approach",
        "desc": "GCD: recursive vs iterative — NOT plagiarism",
        "a": """def gcd(a, b):
    if b == 0:
        return a
    return gcd(b, a % b)
""",
        "b": """def gcd(a, b):
    while b:
        a, b = b, a % b
    return a
""",
        "expected": {"SEMANTIC"},  # These ARE semantically equivalent
    }
)

# 6d: Student added substantial original code around a copied snippet
SCENARIOS.append(
    {
        "id": "6d",
        "name": "Copied snippet in original work",
        "desc": "A small copied function embedded in original work",
        "a": """def helper(x):
    return x * 2 + 1
""",
        "b": """import json

class DataProcessor:
    def __init__(self, config_path):
        with open(config_path) as f:
            self.config = json.load(f)

    def process(self, data):
        results = []
        for item in data:
            results.append(self.transform(item))
        return results

    def transform(self, x):
        return x * 2 + 1

    def save(self, data, output_path):
        with open(output_path, 'w') as f:
            json.dump(data, f)
""",
        "expected": {"EXACT", "RENAMED"},
    }
)


# ─── REALISTIC STUDENT SCENARIOS ───────────────────────────────────────

# 7a: Two students solve "find primes" — one copies and renames
SCENARIOS.append(
    {
        "id": "7a",
        "name": "Prime finder (copied + renamed)",
        "desc": "Classic assignment: find primes up to n",
        "a": """def sieve_of_eratosthenes(n):
    is_prime = [True] * (n + 1)
    is_prime[0] = is_prime[1] = False
    for i in range(2, int(n**0.5) + 1):
        if is_prime[i]:
            for j in range(i*i, n + 1, i):
                is_prime[j] = False
    return [i for i in range(n + 1) if is_prime[i]]
""",
        "b": """def find_primes(limit):
    prime = [True] * (limit + 1)
    prime[0] = prime[1] = False
    for p in range(2, int(limit**0.5) + 1):
        if prime[p]:
            for k in range(p*p, limit + 1, p):
                prime[k] = False
    return [i for i in range(limit + 1) if prime[i]]
""",
        "expected": {"RENAMED"},
    }
)

# 7b: Student rewrites the loop style
SCENARIOS.append(
    {
        "id": "7b",
        "name": "Loop style change",
        "desc": "range-based loop to enumerate",
        "a": """def find_index(lst, target):
    for i in range(len(lst)):
        if lst[i] == target:
            return i
    return -1
""",
        "b": """def find_index(lst, target):
    for i, val in enumerate(lst):
        if val == target:
            return i
    return -1
""",
        "expected": {"SEMANTIC"},
    }
)

# 7c: Student copies class structure, changes implementations
SCENARIOS.append(
    {
        "id": "7c",
        "name": "Copied class skeleton, different methods",
        "desc": "Class structure copied, methods differ",
        "a": """class Student:
    def __init__(self, name, grades):
        self.name = name
        self.grades = grades

    def average(self):
        return sum(self.grades) / len(self.grades)

    def is_passing(self):
        return self.average() >= 60
""",
        "b": """class Student:
    def __init__(self, name, scores):
        self.name = name
        self.scores = scores

    def highest(self):
        return max(self.scores)

    def lowest(self):
        return min(self.scores)
""",
        "expected": {"RENAMED"},
    }
)

# 7d: Student copies and adds more logic
SCENARIOS.append(
    {
        "id": "7d",
        "name": "Copied + extended",
        "desc": "Student copied code and added more on top",
        "a": """def read_data(path):
    with open(path) as f:
        return f.readlines()
""",
        "b": """def read_data(filepath):
    with open(filepath) as fh:
        lines = fh.readlines()

    # Clean up the data
    cleaned = []
    for line in lines:
        stripped = line.strip()
        if stripped:
            cleaned.append(stripped)

    return cleaned
""",
        "expected": {"RENAMED"},
    }
)


# ─── TYPE 8: ADVANCED SEMANTIC PATTERNS ─────────────────────────────────

# 8a: Ternary expression (inline conditional vs if/else block)
SCENARIOS.append(
    {
        "id": "8a",
        "name": "Ternary expression",
        "desc": "If/else block converted to ternary expression",
        "a": """def classify(x):
    if x > 0:
        result = "positive"
    else:
        result = "non-positive"
    return result
""",
        "b": """def classify(x):
    result = "positive" if x > 0 else "non-positive"
    return result
""",
        "expected": {"SEMANTIC"},
    }
)

# 8b: Lambda-to-def conversion
SCENARIOS.append(
    {
        "id": "8b",
        "name": "Lambda to def",
        "desc": "Lambda assigned to variable vs named function",
        "a": """square = lambda x: x * x
""",
        "b": """def square(x):
    return x * x
""",
        "expected": {"SEMANTIC"},
    }
)

# 8c: Generator expression vs list comprehension
SCENARIOS.append(
    {
        "id": "8c",
        "name": "Generator vs list comprehension",
        "desc": "list(generator) vs list comprehension",
        "a": """def get_evens(n):
    return [x for x in range(n) if x % 2 == 0]
""",
        "b": """def get_evens(n):
    return list(x for x in range(n) if x % 2 == 0)
""",
        "expected": {"SEMANTIC"},
    }
)

# 8d: Dict comprehension vs explicit loop
SCENARIOS.append(
    {
        "id": "8d",
        "name": "Dict comprehension vs loop",
        "desc": "Dict comprehension expanded to explicit loop",
        "a": """def build_index(words):
    return {w: i for i, w in enumerate(words)}
""",
        "b": """def build_index(words):
    result = {}
    for i, w in enumerate(words):
        result[w] = i
    return result
""",
        "expected": {"SEMANTIC"},
    }
)

# 8e: Map/filter vs comprehension
SCENARIOS.append(
    {
        "id": "8e",
        "name": "Map vs comprehension",
        "desc": "list(map(lambda)) vs list comprehension",
        "a": """def process(data):
    return list(map(lambda x: x.strip().upper(), data))
""",
        "b": """def process(data):
    return [x.strip().upper() for x in data]
""",
        "expected": {"SEMANTIC"},
    }
)

# 8f: Try/except vs pre-check (EAFP vs LBYL)
SCENARIOS.append(
    {
        "id": "8f",
        "name": "Try/except vs pre-check",
        "desc": "Exception handling vs conditional check",
        "a": """def safe_divide(a, b):
    try:
        return a / b
    except ZeroDivisionError:
        return None
""",
        "b": """def safe_divide(a, b):
    if b == 0:
        return None
    return a / b
""",
        "expected": {"SEMANTIC"},
    }
)

# 8g: Boolean short-circuit vs nested if
SCENARIOS.append(
    {
        "id": "8g",
        "name": "Boolean short-circuit vs nested if",
        "desc": "and operator vs nested conditionals",
        "a": """def validate(data):
    if data and len(data) > 0:
        return True
    return False
""",
        "b": """def validate(data):
    if data:
        if len(data) > 0:
            return True
    return False
""",
        "expected": {"SEMANTIC"},
    }
)

# 8h: Truthy/falsy vs explicit comparison
SCENARIOS.append(
    {
        "id": "8h",
        "name": "Truthy vs explicit comparison",
        "desc": "if data vs if data is not None",
        "a": """def process(data):
    if data:
        return data[0]
    return None
""",
        "b": """def process(data):
    if data is not None and len(data) > 0:
        return data[0]
    return None
""",
        "expected": {"SEMANTIC"},
    }
)

# 8i: Builtin usage (any/all) vs explicit loop
SCENARIOS.append(
    {
        "id": "8i",
        "name": "Builtin vs loop",
        "desc": "all() builtin vs explicit loop",
        "a": """def all_positive(nums):
    for n in nums:
        if n <= 0:
            return False
    return True
""",
        "b": """def all_positive(nums):
    return all(n > 0 for n in nums)
""",
        "expected": {"SEMANTIC"},
    }
)

# 8j: Tuple return vs separate variables
SCENARIOS.append(
    {
        "id": "8j",
        "name": "Tuple return vs separate vars",
        "desc": "Inline tuple return vs intermediate variables",
        "a": """def get_bounds(data):
    return min(data), max(data)
""",
        "b": """def get_bounds(data):
    lo = min(data)
    hi = max(data)
    return lo, hi
""",
        "expected": {"RENAMED", "SEMANTIC"},
    }
)

# 8k: Decorator wrapping
SCENARIOS.append(
    {
        "id": "8k",
        "name": "Decorator wrapping",
        "desc": "Copied function with added decorator",
        "a": """def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
""",
        "b": """import functools

@functools.lru_cache(maxsize=None)
def factorial(n):
    if n <= 1:
        return 1
    return n * factorial(n - 1)
""",
        "expected": {"EXACT", "RENAMED"},
    }
)

# 8l: Nested function extraction
SCENARIOS.append(
    {
        "id": "8l",
        "name": "Nested function extraction",
        "desc": "Closure extracted to module-level function",
        "a": """def make_adder(n):
    def add(x):
        return x + n
    return add
""",
        "b": """def add(x, n):
    return x + n

def make_adder(n):
    return lambda x: add(x, n)
""",
        "expected": {"SEMANTIC"},
    }
)

# 8m: Type annotation differences
SCENARIOS.append(
    {
        "id": "8m",
        "name": "Type annotation differences",
        "desc": "Annotated vs unannotated function",
        "a": """def calculate_average(numbers: list[float]) -> float:
    total: float = 0.0
    for n in numbers:
        total += n
    return total / len(numbers)
""",
        "b": """def calculate_average(numbers):
    total = 0.0
    for n in numbers:
        total += n
    return total / len(numbers)
""",
        "expected": {"EXACT", "RENAMED"},
    }
)

# 8n: String join vs concatenation loop
SCENARIOS.append(
    {
        "id": "8n",
        "name": "Join vs concatenation",
        "desc": "str.join() vs loop with +=",
        "a": """def format_names(names):
    return ", ".join(names)
""",
        "b": """def format_names(names):
    result = ""
    for i, name in enumerate(names):
        if i > 0:
            result += ", "
        result += name
    return result
""",
        "expected": {"SEMANTIC"},
    }
)

# 8o: Different algorithms — negative test
SCENARIOS.append(
    {
        "id": "8o",
        "name": "Different algorithms (negative)",
        "desc": "Iterative vs recursive power — NOT plagiarism",
        "a": """def power(base, exp):
    result = 1
    for _ in range(exp):
        result *= base
    return result
""",
        "b": """def power(base, exp):
    if exp == 0:
        return 1
    return base * power(base, exp - 1)
""",
        "expected": set(),
    }
)

# 8p: Same name, different logic — negative test
SCENARIOS.append(
    {
        "id": "8p",
        "name": "Same name different logic (negative)",
        "desc": "Common function name, completely different logic — NOT plagiarism",
        "a": """def process(data):
    return sorted(data, reverse=True)
""",
        "b": """def process(data):
    seen = set()
    result = []
    for item in data:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result
""",
        "expected": set(),
    }
)

# 8q: Filtered comprehension vs loop with if-guard
SCENARIOS.append(
    {
        "id": "8q",
        "name": "Filtered comprehension vs loop",
        "desc": "List comprehension with if clause vs explicit loop with guard",
        "a": """def get_evens(numbers):
    return [n for n in numbers if n % 2 == 0]
""",
        "b": """def get_evens(numbers):
    result = []
    for n in numbers:
        if n % 2 == 0:
            result.append(n)
    return result
""",
        "expected": {"SEMANTIC"},
    }
)

# 8s: Renamed + semantically transformed (triple combination)
SCENARIOS.append(
    {
        "id": "8s",
        "name": "Renamed + semantic transform",
        "desc": "Variable renaming combined with conditional restructuring",
        "a": """def calculate_grade(scores):
    total = sum(scores)
    count = len(scores)
    average = total / count
    if average >= 90:
        return "A"
    elif average >= 80:
        return "B"
    else:
        return "C"
""",
        "b": """def compute_result(marks):
    n = len(marks)
    s = sum(marks)
    avg = s / n
    if avg < 80:
        return "C"
    elif avg < 90:
        return "B"
    return "A"
""",
        "expected": {"SEMANTIC", "RENAMED"},
    }
)


def run_all_scenarios():
    """Run all test scenarios and report results."""
    passed = 0
    failed = 0
    issues = []

    for scenario in SCENARIOS:
        sid = scenario["id"]
        name = scenario["name"]
        expected = scenario["expected"]
        a = scenario["a"]
        b = scenario["b"]

        try:
            matches = detect_plagiarism(a, b, "python")
        except Exception as e:
            issues.append(f"  [{sid}] {name}: EXCEPTION: {e}")
            failed += 1
            continue

        actual_types = {PlagiarismType(m.plagiarism_type).name for m in matches}

        # For "should not match" scenarios (empty expected), check for no matches
        if not expected:
            if not actual_types:
                print(f"  [{sid}] {name}: OK (no matches as expected)")
                passed += 1
            else:
                issues.append(f"  [{sid}] {name}: FAIL — expected no matches, got {actual_types}")
                failed += 1
            continue

        # Check if any expected type is present
        found_expected = expected & actual_types
        if found_expected:
            print(f"  [{sid}] {name}: OK (found {found_expected}, all types: {actual_types})")
            passed += 1
        else:
            detail = (
                "; ".join(
                    f"T{m.plagiarism_type}({PlagiarismType(m.plagiarism_type).name}): "
                    f"A[{m.file1['start_line']}-{m.file1['end_line']}]→B[{m.file2['start_line']}-{m.file2['end_line']}]"
                    f"{' ' + m.description if m.description else ''}"
                    for m in matches
                )
                or "no matches"
            )
            issues.append(
                f"  [{sid}] {name}: FAIL — expected {expected}, got {actual_types}\n"
                f"    Matches: {detail}"
            )
            failed += 1

    print(f"\n{'=' * 60}")
    print(f"Results: {passed} passed, {failed} failed out of {len(SCENARIOS)} scenarios")
    if issues:
        print("\n--- ISSUES ---")
        for issue in issues:
            print(issue)

    return passed, failed, issues


if __name__ == "__main__":
    run_all_scenarios()
