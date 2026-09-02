"""
Duplicate code detection service for QyverixAI.

Algorithm
---------
1. Extract function/method blocks from the source using language-aware regex.
2. Normalize each block: strip comments, collapse whitespace, and replace
   identifier names with generic placeholders so that renamed copies are
   still caught.
3. Fingerprint each normalized block with a rolling-hash winnowing scheme
   (k-gram hashes, window size w).
4. Compare every pair of blocks using Jaccard similarity on their fingerprint
   sets.  Pairs whose similarity meets or exceeds the configurable threshold
   are reported as duplicates.

The detector is intentionally self-contained and has no external dependencies
beyond the Python standard library so it works in the offline / rule-based
mode without any extra packages.
"""

from __future__ import annotations

import ast
import hashlib
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

# ── Configuration ─────────────────────────────────────────────────────────────
_KGRAM_SIZE = 5  # token n-gram length for fingerprinting
_WINDOW_SIZE = 4  # winnowing window size
_DEFAULT_THRESHOLD = 0.75  # Jaccard similarity threshold (0–1)
_MIN_BLOCK_LINES = 2  # ignore trivially short blocks (< N non-blank lines)
_MAX_PAIRS = 50  # cap reported pairs to avoid response bloat


# ── Data structures ───────────────────────────────────────────────────────────
@dataclass
class CodeBlock:
    name: str
    start_line: int
    end_line: int
    raw: str
    filename: str = "<inline>"
    normalized: str = field(default="", repr=False)
    fingerprints: frozenset[int] = field(default_factory=frozenset, repr=False)


@dataclass
class DuplicatePair:
    block_id: str
    similarity: int  # 0–100
    locations: list[dict[str, Any]]
    snippet: str
    suggestion: str


# ── Normalization ─────────────────────────────────────────────────────────────
_COMMENT_PATTERNS = [
    re.compile(r"#[^\n]*"),  # Python / shell
    re.compile(r"//[^\n]*"),  # C-style single-line
    re.compile(r"/\*.*?\*/", re.DOTALL),  # C-style block
]

_IDENTIFIER_RE = re.compile(r"\b([a-zA-Z_]\w*)\b")

# Keywords that should NOT be replaced during identifier normalization
_KEYWORDS: frozenset[str] = frozenset(
    {
        # Python
        "def",
        "class",
        "return",
        "if",
        "elif",
        "else",
        "for",
        "while",
        "import",
        "from",
        "as",
        "with",
        "try",
        "except",
        "finally",
        "raise",
        "pass",
        "break",
        "continue",
        "lambda",
        "yield",
        "async",
        "await",
        "True",
        "False",
        "None",
        "and",
        "or",
        "not",
        "in",
        "is",
        # JS / TS / Java / C++
        "function",
        "var",
        "let",
        "const",
        "new",
        "this",
        "super",
        "public",
        "private",
        "protected",
        "static",
        "void",
        "return",
        "null",
        "undefined",
        "true",
        "false",
        "class",
        "extends",
        "implements",
        "interface",
        "import",
        "export",
        "default",
        "switch",
        "case",
        "break",
        "continue",
        "throw",
        "catch",
        "finally",
        "try",
        "do",
        "while",
        "for",
        "if",
        "else",
        # Rust / Kotlin / Swift
        "fn",
        "mut",
        "use",
        "pub",
        "impl",
        "struct",
        "enum",
        "match",
    }
)


def _strip_comments(code: str) -> str:
    for pat in _COMMENT_PATTERNS:
        code = pat.sub("", code)
    return code


def _normalize_identifiers(code: str) -> str:
    """Replace user-defined identifiers with a generic token VAR_N.

    Keywords and single-character names are left intact so structural
    patterns (loops, conditionals) are preserved.
    """
    mapping: dict[str, str] = {}
    counter = [0]

    def replace(m: re.Match) -> str:
        name = m.group(1)
        if name in _KEYWORDS:
            return name
        if name not in mapping:
            counter[0] += 1
            mapping[name] = f"VAR{counter[0]}"
        return mapping[name]

    return _IDENTIFIER_RE.sub(replace, code)


def normalize(code: str, *, rename_identifiers: bool = True) -> str:
    """Return a canonical form of *code* for similarity comparison."""
    code = _strip_comments(code)
    if rename_identifiers:
        code = _normalize_identifiers(code)
    # Collapse all whitespace runs to a single space and strip leading/trailing
    code = re.sub(r"\s+", " ", code).strip()
    return code


# ── Fingerprinting (winnowing) ────────────────────────────────────────────────
def _tokenize(text: str) -> list[str]:
    """Split normalized text into tokens (words + punctuation)."""
    return re.findall(r"\w+|[^\w\s]", text)


def _rolling_hash(tokens: list[str], k: int) -> list[int]:
    """Return a list of k-gram hashes over *tokens*."""
    if len(tokens) < k:
        h = int(hashlib.md5(" ".join(tokens).encode()).hexdigest(), 16)
        return [h]
    hashes = []
    for i in range(len(tokens) - k + 1):
        gram = " ".join(tokens[i : i + k])
        h = int(hashlib.md5(gram.encode()).hexdigest(), 16)
        hashes.append(h)
    return hashes


def _winnow(hashes: list[int], w: int) -> frozenset[int]:
    """Select the minimum hash in each sliding window (winnowing)."""
    if not hashes:
        return frozenset()
    selected: set[int] = set()
    for i in range(max(1, len(hashes) - w + 1)):
        window = hashes[i : i + w]
        selected.add(min(window))
    return frozenset(selected)


def fingerprint(
    normalized_code: str, kgram_size: int = _KGRAM_SIZE, window_size: int = _WINDOW_SIZE
) -> frozenset[int]:
    tokens = _tokenize(normalized_code)
    # For very short token streams use smaller k so we still get useful hashes
    k = min(kgram_size, max(2, len(tokens) // 2))
    w = min(window_size, max(1, k - 1))
    hashes = _rolling_hash(tokens, k)
    return _winnow(hashes, w)


# ── Block extraction ──────────────────────────────────────────────────────────
_BLOCK_PATTERNS: dict[str, re.Pattern] = {
    "Python": re.compile(r"^([ \t]*)def\s+(\w+)\s*\(", re.MULTILINE),
    "JavaScript": re.compile(
        r"^([ \t]*)(?:(?:async\s+)?function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\()",
        re.MULTILINE,
    ),
    "TypeScript": re.compile(
        r"^([ \t]*)(?:(?:async\s+)?function\s+(\w+)|(?:const|let|var)\s+(\w+)\s*=\s*(?:async\s*)?\()",
        re.MULTILINE,
    ),
    "Java": re.compile(
        r"^([ \t]*)(?:public|private|protected|static|\s)+[\w<>\[\]]+\s+(\w+)\s*\([^)]*\)\s*(?:throws\s+\w+\s*)?\{",
        re.MULTILINE,
    ),
    "C++": re.compile(
        r"^([ \t]*)(?:[\w:*&<>]+\s+)+(\w+)\s*\([^)]*\)\s*(?:const\s*)?\{",
        re.MULTILINE,
    ),
    "PHP": re.compile(r"^([ \t]*)function\s+(\w+)\s*\(", re.MULTILINE),
    "Rust": re.compile(r"^([ \t]*)(?:pub\s+)?fn\s+(\w+)\s*\(", re.MULTILINE),
    "Kotlin": re.compile(r"^([ \t]*)(?:fun\s+)(\w+)\s*\(", re.MULTILINE),
}


def _extract_python_blocks(code: str, filename: str) -> list[CodeBlock]:
    """Use the AST for accurate Python function extraction."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return _extract_regex_blocks(code, "Python", filename)

    lines = code.splitlines()
    blocks: list[CodeBlock] = []

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        start = node.lineno
        end = node.end_lineno or start
        non_blank = sum(1 for l in lines[start - 1 : end] if l.strip())
        if non_blank < _MIN_BLOCK_LINES:
            continue
        raw = "\n".join(lines[start - 1 : end])
        blocks.append(
            CodeBlock(
                name=node.name,
                start_line=start,
                end_line=end,
                raw=raw,
                filename=filename,
            )
        )

    return blocks


def _extract_regex_blocks(code: str, language: str, filename: str) -> list[CodeBlock]:
    """Regex-based block extraction for non-Python languages."""
    pattern = _BLOCK_PATTERNS.get(language)
    if pattern is None:
        return []

    lines = code.splitlines()
    matches = list(pattern.finditer(code))
    blocks: list[CodeBlock] = []

    for idx, match in enumerate(matches):
        start_line = code[: match.start()].count("\n") + 1
        # End = line before next function, or EOF
        if idx + 1 < len(matches):
            end_line = code[: matches[idx + 1].start()].count("\n")
        else:
            end_line = len(lines)

        non_blank = sum(1 for l in lines[start_line - 1 : end_line] if l.strip())
        if non_blank < _MIN_BLOCK_LINES:
            continue

        # Pick the last non-None capture group as the function name
        # (first group is usually indentation/modifier, last is the actual name)
        groups = [g for g in match.groups() if g and g.strip()]
        name = groups[-1] if groups else "anonymous"

        raw = "\n".join(lines[start_line - 1 : end_line])
        blocks.append(
            CodeBlock(
                name=name,
                start_line=start_line,
                end_line=end_line,
                raw=raw,
                filename=filename,
            )
        )

    return blocks


_LANG_MAP: dict[str, str] = {
    "python": "Python",
    "py": "Python",
    "javascript": "JavaScript",
    "js": "JavaScript",
    "typescript": "TypeScript",
    "ts": "TypeScript",
    "java": "Java",
    "c++": "C++",
    "cpp": "C++",
    "cxx": "C++",
    "c": "C++",
    "php": "PHP",
    "rust": "Rust",
    "rs": "Rust",
    "kotlin": "Kotlin",
    "kt": "Kotlin",
    "kts": "Kotlin",
}


def extract_blocks(
    code: str, language: str = "Unknown", filename: str = "<inline>"
) -> list[CodeBlock]:
    norm_lang = _LANG_MAP.get(str(language).strip().lower(), language)

    if norm_lang == "Python":
        blocks = _extract_python_blocks(code, filename)
    elif norm_lang in _BLOCK_PATTERNS:
        blocks = _extract_regex_blocks(code, norm_lang, filename)
    else:
        # Fallback: try Python AST first
        blocks = _extract_python_blocks(code, filename)
        if not blocks:
            # Try all other regex patterns
            for lang_name in _BLOCK_PATTERNS:
                cand = _extract_regex_blocks(code, lang_name, filename)
                if len(cand) > len(blocks):
                    blocks = cand

    # Attach normalized form and fingerprints
    for block in blocks:
        block.normalized = normalize(block.raw)
        block.fingerprints = fingerprint(block.normalized)

    return blocks


# ── Similarity ────────────────────────────────────────────────────────────────
def jaccard(a: frozenset[int], b: frozenset[int]) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    intersection = len(a & b)
    union = len(a | b)
    return intersection / union


# ── Detection ─────────────────────────────────────────────────────────────────
def _make_suggestion(name_a: str, name_b: str) -> str:
    if name_a == name_b:
        return (
            f"Two functions named '{name_a}' have nearly identical implementations. "
            "Keep one and remove or alias the other."
        )
    return (
        f"Functions '{name_a}' and '{name_b}' share highly similar logic. "
        "Extract the shared logic into a single reusable helper function."
    )


def detect_duplicates(
    blocks: list[CodeBlock],
    threshold: float = _DEFAULT_THRESHOLD,
) -> list[DuplicatePair]:
    """Compare all block pairs and return those above *threshold* similarity."""
    pairs: list[DuplicatePair] = []
    reported: set[tuple[int, int]] = set()

    for i in range(len(blocks)):
        for j in range(i + 1, len(blocks)):
            if len(pairs) >= _MAX_PAIRS:
                break

            a, b = blocks[i], blocks[j]
            sim = jaccard(a.fingerprints, b.fingerprints)
            if sim < threshold:
                continue

            key = (i, j)
            if key in reported:
                continue
            reported.add(key)

            similarity_pct = round(sim * 100)
            snippet_lines = a.raw.splitlines()[:6]
            snippet = "\n".join(snippet_lines)
            if len(a.raw.splitlines()) > 6:
                snippet += "\n..."

            pairs.append(
                DuplicatePair(
                    block_id=uuid.uuid4().hex[:12],
                    similarity=similarity_pct,
                    locations=[
                        {
                            "file": a.filename,
                            "function": a.name,
                            "start_line": a.start_line,
                            "end_line": a.end_line,
                        },
                        {
                            "file": b.filename,
                            "function": b.name,
                            "start_line": b.start_line,
                            "end_line": b.end_line,
                        },
                    ],
                    snippet=snippet,
                    suggestion=_make_suggestion(a.name, b.name),
                )
            )

    return pairs


# ── Public API ────────────────────────────────────────────────────────────────
def run_duplicate_detection(
    code: str,
    language: str,
    filename: str = "<inline>",
    other_files: list[dict[str, str]] | None = None,
    threshold: float = _DEFAULT_THRESHOLD,
) -> dict[str, Any]:
    """Detect duplicate code blocks in *code* and optionally across *other_files*.

    Args:
        code: Source code of the primary file.
        language: Programming language of *code*.
        filename: Display name for the primary file (used in location output).
        other_files: Optional list of ``{"filename": str, "code": str}`` dicts
            for cross-file duplicate detection (ZIP/project analysis).
        threshold: Jaccard similarity threshold (0–1). Default 0.75.

    Returns:
        A dict with keys ``duplicates`` (list), ``duplicate_count`` (int),
        and ``has_duplicates`` (bool).  Never raises — on any error it returns
        an empty result so the caller's analysis pipeline is not interrupted.
    """
    try:
        all_blocks: list[CodeBlock] = extract_blocks(code, language, filename)

        if other_files:
            for entry in other_files:
                other_code = entry.get("code", "")
                other_name = entry.get("filename", "<unknown>")
                if other_code.strip():
                    all_blocks.extend(extract_blocks(other_code, language, other_name))

        pairs = detect_duplicates(all_blocks, threshold=threshold)

        return {
            "duplicates": [
                {
                    "type": "DuplicateCode",
                    "block_id": p.block_id,
                    "similarity": p.similarity,
                    "locations": p.locations,
                    "snippet": p.snippet,
                    "suggestion": p.suggestion,
                }
                for p in pairs
            ],
            "duplicate_count": len(pairs),
            "has_duplicates": len(pairs) > 0,
        }
    except Exception:
        return {"duplicates": [], "duplicate_count": 0, "has_duplicates": False}
