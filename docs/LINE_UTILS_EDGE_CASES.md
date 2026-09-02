# Line Utils Service — Edge Case Reference

This document maps every known edge case in the line-number/code-snippet utility module to the exact code that handles it. It is intended for contributors extending bug detection, suggestions, or any feature that reports line numbers back to a user.

**Routes:** `POST /debugging/` (via `run_bug_detection`), `POST /suggestions/` (via `run_suggestions`), `POST /analyze/` (via both)
**Source:** [`backend/app/services/line_utils.py`](../backend/app/services/line_utils.py), consumed by [`backend/app/services/code_assistant.py`](../backend/app/services/code_assistant.py) (`run_bug_detection`, `run_suggestions`), rendered by [`vscode-extension/src/extension.ts`](../vscode-extension/src/extension.ts)

---

## Protocol

Every function in this module operates on `code: str` and reasons about "line numbers" purely via `str.splitlines()` or manual `\n`-counting — there is no shared line-index cache, and no function validates that its inputs actually describe a real position in the source. This has one consequence that touches almost the entire module (see below), plus several function-specific gaps documented per-function.

---

## Universal Gotcha: `code.splitlines()` Disagrees With `\n`-Counting

- **`str.splitlines()` treats far more characters as line breaks than any real tokenizer does — so line numbers silently drift out of sync with the source they claim to describe.**
  - *Behavior:* `get_line_content`, `get_lines_range`, `format_code_snippet`, and `find_lines_matching_pattern` (`line_utils.py:8,16,34,56`) all call `code.splitlines()`, while `find_function_lines` and `run_bug_detection`'s multi-line-pattern branch compute line numbers via `code[:pos].count("\n")` (`line_utils.py:105,109`; `code_assistant.py:879`). These are **not equivalent**: Python's `splitlines()` also breaks on `\v`, `\f`, `\x1c`–`\x1e`, `\x85`, `U+2028` (LINE SEPARATOR), and `U+2029` (PARAGRAPH SEPARATOR) — characters that are perfectly legal *inside a string literal* in JavaScript, TypeScript, and Java, and are not line terminators to those languages' own compilers.
  - *Demonstrated:* `const s = "before after";\nconst x = 1;` — a single, valid two-line JS file — is split by `splitlines()` into **three** entries: `['const s = "before', 'after";', 'const x = 1;']`. Every line number this module reports past that point (including for a completely unrelated bug three lines later) is off by one, while a real JS linter counting only `\n` would report the correct, unshifted numbers.
  - *Impact:* Because `get_line_content`/`get_lines_range`/`format_code_snippet` use `splitlines()` while `find_function_lines`'s end-of-file fallback and `run_bug_detection`'s multi-line-pattern path use `\n`-counting, a single file containing one of these rare separator characters can make two different parts of the *same* API response disagree about what line N actually is.

---

## `get_line_content` / `get_lines_range` Edge Cases

- **Out-of-range and legitimately-blank lines are indistinguishable.**
  - *Behavior:* `get_line_content` returns `""` both when `line_number` is out of `[1, len(lines)]` (`line_utils.py:9-10`) and when the requested line genuinely exists but is blank. A caller cannot tell "there is no line 500" from "line 500 is an empty line" from the return value alone.
  - *Behavior:* A trailing newline does **not** create a phantom final blank line — `"a\nb\n".splitlines()` is `['a', 'b']`, not `['a', 'b', '']`, so `get_line_content("a\nb\n", 3)` returns `""` via the out-of-range path, not because there's an empty third line.

- **`get_lines_range` silently clamps invalid input instead of raising or returning an explicit error signal.**
  - *Behavior:* `start` is floored via `max(0, start - 1)` (`line_utils.py:17`) — a negative or zero `start` is silently treated identically to `start=1`, with no indication the caller's value was out of range. `end` beyond the file is clamped by `min(len(lines), end)` the same way. This is a different failure mode than `get_line_content`'s explicit `""`-on-out-of-range: one function clamps, the other blanks, and neither raises.

---

## `format_code_snippet` Edge Cases

- **An empty `line_numbers` list silently returns the entire file with no highlights, instead of an empty or error result.**
  - *Behavior:* `min_line`/`max_line` fall back to `1`/`len(lines)` when `line_numbers` is falsy (`line_utils.py:35-36`), so `format_code_snippet(code, [])` dumps the whole file with every `marker` left as the non-highlighted `"    "` prefix (`line_utils.py:45`) — there is no way to distinguish "highlight nothing" from "I forgot to pass line numbers" in the output.

- **A negative `context_lines` can silently produce an empty snippet that omits the very lines it was asked to highlight.**
  - *Behavior:* `start = max(0, min_line - 1 - context_lines)` (`line_utils.py:39`). With `context_lines=-5` and a target line in the middle of the file, `start` overshoots past `end`, and the `for idx in range(start, end)` loop (`line_utils.py:43`) simply produces nothing — `format_code_snippet` returns `""` with no error, silently dropping the requested highlight instead of failing loudly.

- **`_escape_script_tags` only neutralizes `<script>`/`</script>`, and even that inconsistently — it is not a general HTML/XSS sanitizer.**
  - *Behavior:* The opening-tag regex replaces only the literal `<script` substring with `&lt;script`, leaving the tag's closing `>` as a raw, unescaped character (`line_utils.py:22`) — e.g. `<script>` becomes `&lt;script>`, not `&lt;script&gt;`. The closing-tag regex, by contrast, escapes the *entire* match to `&lt;/script&gt;` (`line_utils.py:23`). Both are harmless here only because the opening `<` (the character actually needed to start a real tag) is escaped either way.
  - *Impact:* Any other HTML injection vector — `<img onerror=...>`, `<svg onload=...>`, `<a href="javascript:...">` — passes through `format_code_snippet` completely unescaped, since the function's name and behavior are scoped to script tags specifically, not to code snippets in general. In this codebase the only known HTML renderer of `code_context` is the VS Code extension, which applies its own full `escapeHtml()` before inserting the string into a webview (`vscode-extension/src/extension.ts:154,462`) — so `_escape_script_tags` is redundant defense-in-depth there today, not the actual safeguard. A future consumer that renders `code_context` as raw HTML without its own escaping would inherit this gap.

---

## `find_lines_matching_pattern` Edge Cases

- **Matching is unconditionally case-insensitive, with no way to opt out.**
  - *Behavior:* `re.search(pattern, line, re.IGNORECASE)` is hardcoded (`line_utils.py:60`). A caller passing a pattern that intentionally distinguishes case (e.g. a specific class-name convention) will get false-positive matches on differently-cased text, with no parameter to request strict matching.

- **An invalid regex raises an uncaught `re.error` straight into the caller.**
  - *Behavior:* There is no `try/except` around `re.search` (`line_utils.py:52-63`). Every current call site in `code_assistant.py` passes a hardcoded, known-valid pattern, so this doesn't surface today — but the function is public and unguarded, so if it's ever wired to a user-supplied pattern (e.g. a future "search code by regex" feature), a malformed pattern crashes the request instead of returning a validation error.

---

## `find_function_lines` Edge Cases

- **On Java, a method's reported `name` is frequently the access modifier, not the method name — confirmed by direct testing.**
  - *Behavior:* `func_name = next((g for g in match.groups() if g), "anonymous")` (`line_utils.py:113`) returns the *first* non-`None` captured group. The Java pattern's groups are ordered `(modifier, static, type, name)` (`line_utils.py:95-97`), so whenever a modifier is present, group 1 wins over the real name in group 4.
  - *Demonstrated:* For `public void bar() { ... }`, the regex captures `('public', None, 'void', 'bar')` — `find_function_lines` reports this function's `name` as `"public"`, not `"bar"`. The same happens for constructors (`public Foo() { ... }` reports `name="public"`, not `"Foo"`, because the constructor's modifier is likewise captured before its name).

- **JS/TS arrow functions are only detected when they take zero parameters.**
  - *Behavior:* The arrow-function alternative in the pattern is `\(\s*\)\s*=>` (`line_utils.py:93`) — it matches only an empty parameter list. `const add = (a, b) => {...}` and `const square = x => x * x` are both invisible to `find_function_lines`; only `() => {...}` is ever detected. Demonstrated: scanning a two-function file where both arrow functions take parameters returns `[]` — zero functions found.
  - *Impact:* Since `run_suggestions`'s "Function Length" check (`code_assistant.py:1006-1024`) is driven entirely by `find_function_lines`, an arbitrarily long parameterized arrow function is never flagged for that suggestion, while a trivial one-line `() => {}` would be.

- **Function boundaries are inferred purely from "where the next match starts," so blank lines and unrelated trailing code get folded into a function's reported length.**
  - *Behavior:* `end_line` for a non-last match is `code[:matches[i+1].start()].count("\n")` (`line_utils.py:109`) — i.e. "the line right before the next detected function" — and for the *last* match, `end_line` is unconditionally `len(code.splitlines())`, the end of the file (`line_utils.py:111`), regardless of what that trailing content actually is.
  - *Demonstrated:* For a file with `def foo(): pass`, three blank lines, then `def bar(): pass`, followed by three unrelated module-level statements — `foo` is reported as 5 lines long (its own 2 lines plus the 3 blank lines before `bar`), and `bar` is reported as 5 lines long (its own 2 lines plus the 3 trailing statements that aren't part of any function). Both are real functions of length 2; the module reports both as length 5. A function landing just past the 40-line "too long" threshold in `run_suggestions` (`code_assistant.py:1008`) purely because of trailing blank lines or module-level code would trigger a misleading refactor suggestion.

- **`language` matching is an exact, case-sensitive string comparison with a silent empty-list fallback.**
  - *Behavior:* Only the literal strings `"Python"`, `"JavaScript"`, `"TypeScript"`, `"Java"` are recognized (`line_utils.py:90,92,94`); anything else — a different case, or any other language `detect_language` might return — falls through to `return []` (`line_utils.py:99`) with no error or warning. Downstream, `run_suggestions`'s "Function Length" suggestion silently never fires for any unrecognized language, indistinguishable from "this code genuinely has no long functions."

---

## `find_undocumented_lines` / `is_code_line` Edge Cases

- **An inline trailing comment does not count as documentation.**
  - *Behavior:* The "is there a comment nearby" check tests `check_line.startswith(("#", "//", "/*"))` (`line_utils.py:144`) against the *entire stripped line*, so it only recognizes a comment that is the first thing on a line. Demonstrated: `x = 5  # explains this` is still reported as an undocumented line, because `"x = 5  # explains this".strip()` does not start with `#` — the inline comment is invisible to this check even though the line is, in every practical sense, documented.

- **The `offset in range(-2, 1)` lookback includes `offset=0`, which re-checks the current line and can never fire.**
  - *Behavior:* For the current 1-indexed line `idx`, `offset=0` computes `check_idx = idx - 1` (`line_utils.py:140-141`), which is the **current line itself** in 0-indexed terms. But the function already `continue`d past any line starting with a comment marker earlier in the loop (`line_utils.py:135`), so by the time this check runs, the current line is guaranteed *not* to start with a comment marker — making the `offset=0` branch permanently dead code that never contributes a match. The effective lookback is only the previous two lines, not three.

- **Lines inside a multi-line docstring/comment body are misclassified as undocumented code.**
  - *Behavior:* Both `find_undocumented_lines`'s skip check (`line_utils.py:135`) and `is_code_line` (`line_utils.py:157`) only recognize a comment by what a *stripped line starts with* — `#`, `//`, `/*`, `*`, `"""`, `'''`. Neither tracks whether a line is already inside an open triple-quoted string or block comment. A prose line in the *middle* of a docstring (e.g. `"""` on one line, `Explains what this does.` on the next, `"""` closing it) doesn't start with any recognized marker, so it's treated as undocumented code — even though it *is* the documentation.

- **`is_code_line` returns `""` instead of `False` for blank lines, violating its own `-> bool` annotation.**
  - *Behavior:* `return stripped and not stripped.startswith(...)` (`line_utils.py:157`); when `stripped` is `""`, Python's `and` short-circuits and returns the falsy `stripped` value itself — the empty string — not the boolean `False`. Demonstrated: `is_code_line("")` returns `''`, and `is_code_line("   ")` also returns `''`. Any `if is_code_line(line):` check still behaves correctly since `""` is falsy, but serializing the return value directly (e.g. into a JSON API response) would emit `""` rather than `false` for blank lines.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| **Line numbering is not consistent across the module** | `splitlines()`-based functions and `\n`-count-based functions can disagree on the same file whenever it contains a Unicode line-separator character valid in string literals but not treated as a line break by the target language's own compiler. |
| **No function validates its own inputs** | Out-of-range line numbers are handled three different ways across the module: `get_line_content` returns `""`, `get_lines_range` silently clamps, and `find_lines_matching_pattern` would raise on an invalid pattern. There is no shared convention. |
| **Java function names are frequently wrong** | Any modifier-qualified Java method or constructor reports its access modifier as the function `name` instead of the real identifier — confirmed by direct testing, not just static reading. |
| **Parameterized JS/TS arrow functions are invisible** | Only the zero-parameter form `() => ...` is detected; the common `(a, b) => ...` and single-arg `x => ...` forms never appear in `find_function_lines`'s output. |
| **Reported function length includes non-function content** | Blank lines and trailing module-level code between/after detected functions are folded into the preceding function's `length`, which can trigger `run_suggestions`'s "function too long" suggestion for a function that isn't actually long. |
| **Documentation detection only recognizes comments at the start of a line** | Inline trailing comments and prose inside multi-line docstrings are both misclassified as undocumented code by `find_undocumented_lines` and `is_code_line`. |
| **`_escape_script_tags` is not a general sanitizer** | It only neutralizes `<script>`/`</script>`; every other HTML/JS injection vector passes through `format_code_snippet` unescaped. The only current HTML consumer (the VS Code extension) escapes independently, so this is currently redundant rather than load-bearing. |
