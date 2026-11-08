# LLM Analysis Service — Edge Case Reference

This document maps every known edge case in the LLM-backed analysis client to the exact code that handles it. It is intended for contributors extending `/analyze/`, `/chat`, and `/chat/message`.

**Routes:** `POST /analyze/` (via `hybrid_analysis`), `POST /chat`, `POST /chat/message`
**Source:** [`backend/app/services/llm_analysis.py`](../backend/app/services/llm_analysis.py), [`backend/app/services/code_assistant.py`](../backend/app/services/code_assistant.py) (`hybrid_analysis`, `_merge_explanation`, `_merge_suggestions`), [`backend/app/routers/chat.py`](../backend/app/routers/chat.py)

---

## Protocol

`LLMAnalysisClient` is a thin wrapper around an OpenAI-compatible `/chat/completions` endpoint. It is only usable when `enabled` is `True` — `settings.llm_enabled` is truthy **and** `LLM_API_KEY` is set (`llm_analysis.py:39-41`). Every public method that talks to the LLM checks this first and raises `LLMAnalysisError("llm_disabled")` if not.

Three call sites consume it, each with a different failure contract:

1. **`hybrid_analysis()`** (`code_assistant.py:1576-1617`) — calls `analyze_code_structured()`. Rule-based analysis always runs first and is always returned; the LLM only *enriches* `explanation` and `suggestions`, and may attach `optimized_version`. Any `LLMAnalysisError` or unexpected exception degrades the response to `mode="degraded"` — `/analyze/` never returns a 500 because the LLM failed.
2. **`/chat`** and **`/chat/message`** (`chat.py`) — call `chat_reply()` directly inside a bare `try/except Exception: pass`, falling back to the deterministic `chat_fallback_reply()` on *any* failure.
3. **`summarize_code()`** — implemented and unit-tested, but not called from any router or service. It is dead code as of this writing.

---

## Edge Cases by Category

### Availability / `enabled` Edge Cases

- **`enabled` is re-evaluated on every access, not cached at construction.**
  - *Behavior:* `enabled` is a property that reads `settings.llm_enabled` and `self.api_key` live (`llm_analysis.py:39-41`). Because `analyze_code_structured()`'s retry loop calls `_chat_completion()` again on every attempt, and `_chat_completion()` re-checks `self.enabled`, toggling the flag mid-retry (e.g. in tests, or a future hot-reload of settings) causes the very next attempt to fail fast with `"llm_disabled"` instead of continuing to retry against the network.

- **A configured but invalid API key still reports `enabled=True`.**
  - *Behavior:* `enabled` only checks *presence* of `self.api_key` (`bool(settings.llm_enabled and self.api_key)`), not validity. An invalid or revoked key surfaces only after the HTTP round-trip, as a `401`/`403` wrapped into `LLMAnalysisError` by the generic exception handler in `_chat_completion` — there is no fast-path distinguishing "misconfigured" from "provider rejected the request."

---

### `_chat_completion` Edge Cases

- **Any failure — network, HTTP status, or malformed response shape — collapses into the same generic `LLMAnalysisError(str(exc))`.**
  - *Behavior:* `response.raise_for_status()`, `response.json()`, and `data["choices"][0]["message"]["content"]` are all inside one `try` block with a single catch-all `except Exception` (`llm_analysis.py:66-78`). A timeout, a non-2xx status, an HTML error page instead of JSON, or a `choices: []` response from the provider all produce the same kind of opaque message (e.g. `"list index out of range"` for an empty `choices` array) — callers cannot distinguish transient network errors from a malformed provider response without string-matching.

- **An empty (but syntactically valid) completion is treated as an error.**
  - *Behavior:* `message = data["choices"][0]["message"]["content"].strip()`; if this is empty, `_chat_completion` raises `LLMAnalysisError("empty_llm_response")` (`llm_analysis.py:72-73`) rather than returning `""`. This is the *only* case in the file where a syntactically successful HTTP response is still treated as a client-level error.

---

### `_extract_json` / Structured-Response Parsing Edge Cases

- **JSON extraction is a naive first-`{` to last-`}` slice, not a real parser boundary.**
  - *Behavior:* `_extract_json` does `candidate.find("{")` and `candidate.rfind("}")` and slices between them (`llm_analysis.py:102-108`). If the model prepends conversational text containing a stray `{` (e.g. *"Here's the analysis: {...} let me know if you need more."*) or appends trailing prose containing a stray `}` after the real JSON object, the slice captures the wrong span and `json.loads` fails with `"invalid_json_payload"` — even though a fully valid JSON object exists in the response. Braces that are part of *quoted string values inside* the real JSON object are fine, since they stay nested within the correctly-matched outer pair.

- **Markdown-fence stripping only fires if the fence is the very first characters.**
  - *Behavior:* `_strip_markdown_fences` only strips ` ```json ` / ` ``` ` markers when `candidate.startswith("```")` (`llm_analysis.py:84`). A response like `"Sure, here you go:\n\`\`\`json\n{...}\n\`\`\`"` never enters that branch, so the fence markers remain in the string. This is usually harmless in practice because the fence backticks don't overlap with the `{`/`}` boundary search above, but it means fence-stripping is best-effort, not guaranteed.

- **Schema validation checks only top-level key *presence*, never value types.**
  - *Behavior:* `_validate_structured_payload` requires all five keys in `_STRUCTURED_REQUIRED_KEYS` to exist (`llm_analysis.py:90-96`) but never checks that, say, `explanation` is actually a dict rather than a string or `null`. A structurally-present-but-wrong-shaped payload passes this validation and is only neutralized downstream by `isinstance` guards in `_merge_explanation`/`_merge_suggestions`, which silently drop anything that isn't the expected shape rather than raising.

- **The required `complexity` key is validated but then discarded.**
  - *Behavior:* `complexity` is one of the five keys `_validate_structured_payload` requires the model to return — a response missing it is rejected and retried (`llm_analysis.py:12-20`). But `hybrid_analysis()` never reads `llm_result["complexity"]` anywhere (`code_assistant.py:1606-1617`) — it only merges `explanation` and `suggestions`, and reads `optimized_version` separately. The model is forced to spend output tokens producing a field the API response never surfaces.

- **The required `debugging` key is intentionally discarded — but silently, with no code comment explaining it beyond the function docstring.**
  - *Behavior:* Same mechanism as `complexity` above: required for schema validation, but `hybrid_analysis()`'s docstring states rule-based `debugging.issues` are always kept in favor of the LLM's version (`code_assistant.py:1577-1582`), so `llm_result["debugging"]` is read from the parsed payload but never merged in.

---

### Retry Edge Cases (`analyze_code_structured`)

- **Retries apply to parse failures identically to network failures, including repeated non-JSON refusals.**
  - *Behavior:* Both the `LLMAnalysisError` branch and the generic `Exception` branch inside the retry loop (`llm_analysis.py:184-209`) retry with the same exponential backoff. If the model consistently returns prose instead of JSON (e.g. a safety refusal), every attempt costs a full LLM API call before finally exhausting retries — there's no fast-path that distinguishes "the provider is unreachable" from "the provider responded but the content is unparseable," even though only the former benefits from retrying.

- **Worst-case latency is retries × timeout, plus cumulative backoff sleep.**
  - *Behavior:* With defaults (`LLM_MAX_RETRIES=3`, `LLM_TIMEOUT_SECONDS=30`, `LLM_RETRY_BACKOFF=1.0`), `max_attempts = max_retries + 1 = 4`, and `sleep_time = retry_backoff * 2**attempt` sleeps `1s, 2s, 4s` between attempts (`llm_analysis.py:177-196`). A provider that hangs until timeout on every attempt makes `/analyze/` take up to `4 × 30s + (1+2+4)s = 127s` before degrading to `mode="degraded"` — there is no overall deadline shorter than this compounding worst case.

---

### `hybrid_analysis` Merge Edge Cases

- **A degraded result is cached under the same namespace a successful hybrid result would use.**
  - *Behavior:* `/analyze/`'s `mode_key` is computed from `llm_analysis_client.enabled` *before* calling `hybrid_analysis()` (`analyze.py:200-203`) — it is `"hybrid"` whenever the LLM is configured, regardless of whether the call actually succeeds. If the LLM call then fails and `hybrid_analysis()` returns `mode="degraded"`, that degraded payload is still stored under the `analyze:v2:hybrid` cache namespace (`analyze.py:206-209`). Identical follow-up requests replay the cached degraded result for the cache TTL, even if the LLM would now succeed — there's no cache-bypass on `mode="degraded"`.

- **Duplicate LLM key points are suppressed only by exact string match.**
  - *Behavior:* `_merge_explanation` checks `insight not in key_points` before appending (`code_assistant.py:1503-1516`). Any difference in wording, punctuation, or whitespace between two LLM calls (e.g. across a retry) produces a "duplicate" entry that isn't caught, since the check is a literal substring-list membership test, not semantic dedup.

- **A missing `title` falls back to a fixed placeholder that then collides with the "title == reason" check.**
  - *Behavior:* In `_merge_suggestions`, `title = item.get("title") or "AI Suggestion"` (`code_assistant.py:1534`). If the model also omits `reason`, `reason` falls back to that same placeholder value via `reason = item.get("reason") or title`, so `title == reason` is `True` and the description collapses to just `"AI Suggestion"` (`code_assistant.py:1544`) — a suggestion with no actual content is still appended to the list rather than being skipped.

---

### Chat Endpoint Edge Cases (`/chat`, `/chat/message`)

- **Failures are swallowed with no logging at all.**
  - *Behavior:* Unlike `analyze_code_structured`, which logs a `warning` on every failed attempt, `chat_reply()` has no internal error handling, and both `chat()` and `chat_message()` wrap the call in a bare `except Exception: pass` (`chat.py:22-23`, `chat.py:50-51`) with no `logger` call. A misconfigured provider, an expired key, or a provider outage on the chat path produces zero server-side log evidence — only the `/analyze/` path is observable when the LLM is failing.

- **`except Exception` also swallows programming errors, not just provider failures.**
  - *Behavior:* The same bare `except Exception: pass` will catch a `TypeError`/`AttributeError` from a bug in `chat_reply()` just as silently as a genuine network failure, masking regressions behind the "graceful" rule-based fallback instead of surfacing them.

- **`/chat` and `/chat/message` expose inconsistent mode metadata for the same underlying behavior.**
  - *Behavior:* `/chat/message`'s response includes `mode` (`"live-llm"` vs `"ready+chat_fallback"`) so a client can tell which path served the reply (`chat.py:44-64`). `/chat`'s `ChatResponse` has no `mode`/`provider` field at all (`schemas.py:947-954`) — a client calling the simpler endpoint has no way to detect whether a reply came from the LLM or the deterministic fallback.

- **The `provider` string is hardcoded per call site instead of reusing `provider_name`.**
  - *Behavior:* `llm_analysis_client.provider_name` exists specifically to keep provider labels consistent "with chat endpoints" (its own docstring, `llm_analysis.py:44-46`), but `chat_message()` hardcodes the literal `"openai-compatible"` (`chat.py:45`) rather than referencing the property. The two are consistent today only because both happen to be the same string; a change to one is not guaranteed to be reflected in the other.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| **`summarize_code()` is unreachable in production** | Fully implemented and unit-tested, but no router or service calls it — the injection-hardened prompt and its behavior are exercised only by tests. |
| **No structured error taxonomy** | Every failure mode (timeout, bad status, malformed JSON, missing schema keys, empty response) surfaces as a plain string inside `LLMAnalysisError`; callers that want to react differently to different failure types must parse the message text. |
| **`complexity` and `debugging` are required from the model but never returned to the API caller** | Both cost output tokens on every successful structured call and are discarded — `complexity` with no comment explaining why, `debugging` per the documented rule-engine-wins policy. |
| **Retry budget is spent equally on retryable and non-retryable failures** | A model that deterministically refuses to produce JSON exhausts the full retry budget (and its backoff delays) before `hybrid_analysis()` degrades, identically to a transient network blip. |
| **Cache can pin a degraded result** | See "A degraded result is cached..." above — `mode_key` reflects configuration, not actual outcome, so a transient LLM failure can serve stale `mode="degraded"` results to identical requests until the cache entry expires. |
| **Chat-path failures are invisible in logs** | Only the `/analyze/` path logs LLM failures; `/chat` and `/chat/message` fail silently by design, making provider outages on the chat endpoints undetectable from logs alone. |
