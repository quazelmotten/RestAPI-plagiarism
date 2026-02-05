# plagiarism.py
from tree_sitter import Language, Parser
import tree_sitter_python as tspython
import tree_sitter_cpp as tscpp
from collections import defaultdict

# Мапа языков для tree-sitter
LANGUAGE_MAP = {
    'python': Language(tspython.language()),
    'cpp': Language(tscpp.language())
}

def get_language(lang_code):
    if lang_code not in LANGUAGE_MAP:
        raise ValueError(f"Unsupported language: {lang_code}")
    return LANGUAGE_MAP[lang_code]

def tokenize_with_tree_sitter(file_path, lang_code='python'):
    """
    Парсинг файла с помощью фреймворка tree-sitter, который также парсит начало и конец фрагмента (start_point, end_point)
    Возвращает массив кортежей из (token_type, start_point, end_point)
    """
    language = get_language(lang_code)
    parser = Parser(language)

    with open(file_path, 'r', encoding='utf-8') as f:
        code = f.read()

    tree = parser.parse(bytes(code, 'utf-8'))
    tokens = []

    def extract_tokens(node):
        if len(node.children) == 0:
            tokens.append((node.type, node.start_point, node.end_point))
        else:
            for child in node.children:
                extract_tokens(child)

    extract_tokens(tree.root_node)
    return tokens

def generate_k_grams(tokens, k=6):
    """
    Каждая к-грамма содержит информацию о начале и конце фрагмента
    """
    k_grams = []
    for i in range(len(tokens) - k + 1):
        kgram_tokens = tokens[i:i + k]
        token_types = tuple(tok[0] for tok in kgram_tokens)
        start_point = kgram_tokens[0][1]
        end_point = kgram_tokens[-1][2]
        k_grams.append((token_types, start_point, end_point))
    return k_grams

def compute_fingerprints(tokens, k=6, base=257, mod=10**9 + 7):
    """
    Высчитываем скользящие хэши для всех токенов (быстрее чем SHA256)
    """
    if len(tokens) < k:
        return []

    hashes = []
    power = pow(base, k-1, mod)
    h = 0

    for i in range(k):
        h = (h * base + hash(tokens[i][0])) % mod

    hashes.append({
        'hash': h,
        'start': tokens[0][1],
        'end': tokens[k-1][2]
    })

    for i in range(k, len(tokens)):
        h = (h - hash(tokens[i - k][0]) * power) % mod
        h = (h * base + hash(tokens[i][0])) % mod
        hashes.append({
            'hash': h,
            'start': tokens[i - k + 1][1],
            'end': tokens[i][2]
        })

    return hashes


def winnow_fingerprints(fingerprints, window_size=5):
    """
    Сокращаем количество хэшей с помощью алгоритма Winnowing, при этом сохраняя начальные/конечные позиции
    """
    winnowed = []
    for i in range(len(fingerprints) - window_size + 1):
        window = fingerprints[i:i + window_size]
        min_fp = min(window, key=lambda x: x['hash'])
        if not winnowed or min_fp['hash'] != winnowed[-1]['hash']:
            winnowed.append(min_fp)
    return winnowed

def index_fingerprints(fingerprints, file_id):
    index = defaultdict(list)
    for fp in fingerprints:
        index[fp['hash']].append({
            'file_id': file_id,
            'start': fp['start'],
            'end': fp['end']
        })
    return index

def compute_similarity(index_a, index_b):
    """
    Высчитываем процент заимствований по формуле (Sa+Sb)/(Ta+Tb), 
    где S количество заимствований в файле из общего набора хэшей, Т - общее количество хэшей в файле
    """
    common = set(index_a.keys()) & set(index_b.keys())
    if not common:
        return 0
    Sa = sum(len(index_a[h]) for h in common)
    Sb = sum(len(index_b[h]) for h in common)
    Ta = sum(len(index_a[h]) for h in index_a)
    Tb = sum(len(index_b[h]) for h in index_b)
    return (Sa + Sb) / (Ta + Tb)

def find_matching_regions(index_a, index_b):
    """
    Match fingerprints one-to-one to avoid duplicate or misaligned matches.
    """
    matches = []
    for hash_val in set(index_a.keys()) & set(index_b.keys()):
        list_a = sorted(index_a[hash_val], key=lambda x: (x['start'], x['end']))
        list_b = sorted(index_b[hash_val], key=lambda x: (x['start'], x['end']))
        for loc_a, loc_b in zip(list_a, list_b):
            matches.append({
                'file1': {
                    'start_line': loc_a['start'][0],
                    'start_col': loc_a['start'][1],
                    'end_line': loc_a['end'][0],
                    'end_col': loc_a['end'][1],
                },
                'file2': {
                    'start_line': loc_b['start'][0],
                    'start_col': loc_b['start'][1],
                    'end_line': loc_b['end'][0],
                    'end_col': loc_b['end'][1],
                }
            })
    return matches

def merge_adjacent_matches(matches, max_line_gap=1, max_col_gap=5):
    """
    Merge adjacent or overlapping match regions for cleaner visualization.
    """
    merged = []
    matches.sort(key=lambda m: (
        m['file1']['start_line'],
        m['file1']['start_col']
    ))

    for m in matches:
        if not merged:
            merged.append(m)
            continue

        last = merged[-1]

        same_side = (
            m['file1']['start_line'] <= last['file1']['end_line'] + max_line_gap and
            m['file1']['start_col'] - last['file1']['end_col'] <= max_col_gap
        )

        if same_side:
            # extend both sides
            last['file1']['end_line'] = max(last['file1']['end_line'], m['file1']['end_line'])
            last['file1']['end_col'] = max(last['file1']['end_col'], m['file1']['end_col'])
            last['file2']['end_line'] = max(last['file2']['end_line'], m['file2']['end_line'])
            last['file2']['end_col'] = max(last['file2']['end_col'], m['file2']['end_col'])
        else:
            merged.append(m)

    return merged




def analyze_plagiarism(file1, file2, language='python'):
    tokens1 = tokenize_with_tree_sitter(file1, language)
    tokens2 = tokenize_with_tree_sitter(file2, language)

    k_grams1 = generate_k_grams(tokens1)
    k_grams2 = generate_k_grams(tokens2)

    fingerprints1 = compute_fingerprints(k_grams1)
    fingerprints2 = compute_fingerprints(k_grams2)

    winnowed1 = winnow_fingerprints(fingerprints1)
    winnowed2 = winnow_fingerprints(fingerprints2)

    index1 = index_fingerprints(winnowed1, 1)
    index2 = index_fingerprints(winnowed2, 2)

    similarity = compute_similarity(index1, index2)
    matches = find_matching_regions(index1, index2)
    matches = merge_adjacent_matches(matches, max_line_gap=1, max_col_gap=5)
    return similarity, matches
