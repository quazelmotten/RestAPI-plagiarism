from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_cpp as tscpp

from collections import defaultdict, Counter
import hashlib

# -------------------------------
# Tree-sitter language setup
# -------------------------------

LANGUAGE_MAP = {
    'python': Language(tspython.language()),
    'cpp': Language(tscpp.language()),
}

def get_language(lang_code):
    if lang_code not in LANGUAGE_MAP:
        raise ValueError(f"Unsupported language: {lang_code}")
    return LANGUAGE_MAP[lang_code]

# -------------------------------
# Utilities
# -------------------------------

def stable_hash(s: str) -> int:
    """Deterministic hash for cross-run stability."""
    return int(hashlib.sha1(s.encode()).hexdigest()[:16], 16)

# -------------------------------
# Tokenization (for winnowing)
# -------------------------------

def tokenize_with_tree_sitter(file_path, lang_code='python'):
    language = get_language(lang_code)
    parser = Parser(language)

    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    tree = parser.parse(code.encode('utf-8'))
    tokens = []

    def visit(node):
        if not node.children:
            tokens.append((node.type, node.start_point, node.end_point))
        else:
            for child in node.children:
                visit(child)

    visit(tree.root_node)
    return tokens

# -------------------------------
# Token Winnowing (filter stage)
# -------------------------------

def compute_fingerprints(tokens, k=6, base=257, mod=10**9 + 7):
    if len(tokens) < k:
        return []

    hashes = []
    power = pow(base, k - 1, mod)
    h = 0

    for i in range(k):
        h = (h * base + stable_hash(tokens[i][0])) % mod

    hashes.append({
        'hash': h,
        'start': tokens[0][1],
        'end': tokens[k - 1][2]
    })

    for i in range(k, len(tokens)):
        h = (h - stable_hash(tokens[i - k][0]) * power) % mod
        h = (h * base + stable_hash(tokens[i][0])) % mod
        hashes.append({
            'hash': h,
            'start': tokens[i - k + 1][1],
            'end': tokens[i][2]
        })

    return hashes

def winnow_fingerprints(fingerprints, window_size=5):
    winnowed = []
    for i in range(len(fingerprints) - window_size + 1):
        window = fingerprints[i:i + window_size]
        min_fp = min(window, key=lambda x: x['hash'])
        if not winnowed or min_fp['hash'] != winnowed[-1]['hash']:
            winnowed.append(min_fp)
    return winnowed

def index_fingerprints(fingerprints):
    index = defaultdict(list)
    for fp in fingerprints:
        index[fp['hash']].append(fp)
    return index

def token_similarity(index_a, index_b):
    common = set(index_a) & set(index_b)
    if not common:
        return 0.0

    Sa = sum(len(index_a[h]) for h in common)
    Sb = sum(len(index_b[h]) for h in common)
    Ta = sum(len(v) for v in index_a.values())
    Tb = sum(len(v) for v in index_b.values())

    return (Sa + Sb) / (Ta + Tb)

# -------------------------------
# AST Subtree Hashing (decision stage)
# -------------------------------

def hash_ast_subtrees(root, min_depth=3):
    """
    Hash AST subtrees with depth >= min_depth.
    Depth is measured as max distance to a leaf.
    """
    hashes = []

    def visit(node):
        if not node.children:
            return 1, ""

        child_results = [visit(c) for c in node.children]
        child_depths, child_hashes = zip(*child_results)

        depth = 1 + max(child_depths)
        rep = node.type + "(" + ",".join(child_hashes) + ")"

        h = stable_hash(rep)
        if depth >= min_depth:
            hashes.append(h)

        return depth, str(h)

    visit(root)
    return hashes


def extract_ast_hashes(file_path, lang_code, min_depth=3):
    language = get_language(lang_code)
    parser = Parser(language)

    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    tree = parser.parse(code.encode('utf-8'))
    return hash_ast_subtrees(tree.root_node, min_depth)

def ast_similarity(hashes_a, hashes_b):
    ca, cb = Counter(hashes_a), Counter(hashes_b)
    intersection = sum((ca & cb).values())
    union = sum((ca | cb).values())
    return intersection / union if union else 0.0

# -------------------------------
# Match visualization (token-based)
# -------------------------------

def find_matching_regions(index_a, index_b):
    matches = []
    for h in set(index_a) & set(index_b):
        for a, b in zip(index_a[h], index_b[h]):
            matches.append({
                'file1': {
                    'start_line': a['start'][0],
                    'start_col': a['start'][1],
                    'end_line': a['end'][0],
                    'end_col': a['end'][1],
                },
                'file2': {
                    'start_line': b['start'][0],
                    'start_col': b['start'][1],
                    'end_line': b['end'][0],
                    'end_col': b['end'][1],
                }
            })
    return matches

def merge_adjacent_matches(matches, max_line_gap=1, max_col_gap=5):
    if not matches:
        return []

    matches.sort(key=lambda m: (
        m['file1']['start_line'],
        m['file1']['start_col']
    ))

    merged = [matches[0]]

    for m in matches[1:]:
        last = merged[-1]
        if (
            m['file1']['start_line'] <= last['file1']['end_line'] + max_line_gap and
            m['file1']['start_col'] - last['file1']['end_col'] <= max_col_gap
        ):
            for side in ('file1', 'file2'):
                last[side]['end_line'] = max(last[side]['end_line'], m[side]['end_line'])
                last[side]['end_col'] = max(last[side]['end_col'], m[side]['end_col'])
        else:
            merged.append(m)

    return merged


def analyze_plagiarism(
    file1,
    file2,
    language='python',
    token_threshold=0.15,
    ast_threshold=0.30,
):
    # --- token filter ---
    tokens1 = tokenize_with_tree_sitter(file1, language)
    tokens2 = tokenize_with_tree_sitter(file2, language)

    fps1 = winnow_fingerprints(compute_fingerprints(tokens1))
    fps2 = winnow_fingerprints(compute_fingerprints(tokens2))

    index1 = index_fingerprints(fps1)
    index2 = index_fingerprints(fps2)

    tok_sim = token_similarity(index1, index2)
    if tok_sim < token_threshold:
        return 0.0, []

    # --- AST decision ---
    ast1 = extract_ast_hashes(file1, language, min_depth=3)
    ast2 = extract_ast_hashes(file2, language, min_depth=3)

    ast_sim = ast_similarity(ast1, ast2)
    if ast_sim < ast_threshold:
        return ast_sim, []

    matches = merge_adjacent_matches(
        find_matching_regions(index1, index2)
    )

    return ast_sim, matches
