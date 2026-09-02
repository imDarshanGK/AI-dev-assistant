# Upload Config Service — Edge Case Reference

This document maps every known edge case in file-upload validation to the exact code that handles it. It is intended for client implementors and contributors extending the upload feature.

**Routes:** `GET /upload/`, `POST /upload/validate`
**Source:** [`backend/app/utils/upload_config.py`](../backend/app/utils/upload_config.py), [`backend/app/utils/file_validator.py`](../backend/app/utils/file_validator.py), [`backend/app/routers/upload_file.py`](../backend/app/routers/upload_file.py)

---

## Protocol

Uploads are validated, not stored — `POST /upload/validate` reads the entire file into memory, checks its size, extension, and MIME type, and returns a JSON summary. Nothing is written to disk by this router.

Validation runs in a fixed order inside `upload_file()`:

1. **Size** — `len(filecontent) > max_file_size` (checked in the router, before anything in `file_validator` runs).
2. **Extension** — `validate_file_extension()` (missing extension, double extension, blocked extension, then allow-list).
3. **MIME type** — `validate_mime_type()`, using `python-magic` to sniff the actual bytes against `ALLOWED_MIME_TYPES[ext]`.

Because size is checked first, a file that is both oversized *and* has a blocked extension reports `413`, never `415` — the `try`/`except ValueError` in the router only wraps the extension/MIME checks, not the size check.

`GET /upload/` returns the live config (`max_file_size_MB`, `blocked_extensions`, `allowed_extensions`, `allowed_mime_types`) unauthenticated — it is a public reference endpoint, not something session-scoped.

---

## Edge Cases by Category

### File Size Edge Cases

- **Exactly `max_file_size` (5 MB)**
  - *Behavior:* The check is `filesize > max_file_size`, a strict greater-than. A file of exactly 5,242,880 bytes is accepted; only 5,242,881 bytes and above trigger `413`.

- **Whole file buffered before the size check**
  - *Behavior:* `filecontent = await file.read()` reads the complete upload into memory before `filesize` is ever computed. The 5 MB cap protects downstream validation, but it does not prevent a large request body from being fully buffered first — there is no streaming/early-abort based on `Content-Length`.

- **Zero-byte file**
  - *Behavior:* `0 > max_file_size` is `False`, so an empty file always clears the size check. It then reaches MIME sniffing, where `python-magic` identifies empty content as an empty-file MIME type (e.g. `application/x-empty` or `inode/x-empty`, depending on the installed libmagic version) — not present in any extension's `ALLOWED_MIME_TYPES` list — so empty files are rejected at the MIME stage with `"invalid_mime"`, not with a dedicated "empty file" message.

---

### Extension Edge Cases

- **No extension at all**
  - *Behavior:* `get_file_extension()` returns `Path(filename).suffix.lower()`, which is `""` for a filename with no dot (e.g. `"README"`). `validate_file_extension()` checks `if not extension` first and raises `"invalid_extension"` before any other check runs.

- **Extension casing is normalized inconsistently**
  - *Behavior:* The final single-extension checks (`extension in BLOCKED_EXTENSIONS`, `extension not in ALLOWED_EXTENSIONS`) use the **lower-cased** extension from `get_file_extension()`. But `has_double_extension()` re-derives suffixes directly from `Path(filename).suffixes` **without lower-casing them**. A filename like `"malware.EXE.py"` produces suffixes `[".EXE", ".py"]`; `.EXE` (uppercase) does not match any entry in `BLOCKED_EXTENSIONS` (all lowercase), so the double-extension guard silently misses it. The final extension check then sees only `.py`, which is allowed — so an uppercase-disguised blocked extension can bypass the double-extension defense (it would still need to pass MIME sniffing to fully succeed).

- **Double extension only checks against `BLOCKED_EXTENSIONS`, not against non-allowed extensions**
  - *Behavior:* `has_double_extension()` flags a filename only if an earlier suffix is in `BLOCKED_EXTENSIONS`. A name like `"archive.zip.py"` has suffixes `[".zip", ".py"]`; `.zip` is in neither `BLOCKED_EXTENSIONS` nor `ALLOWED_EXTENSIONS`, so it is not caught by the double-extension check, and the final extension (`.py`) passes the allow-list — the file is accepted (still subject to MIME sniffing on the `.py` allow-list).

- **Single-suffix filenames skip the double-extension check entirely**
  - *Behavior:* `has_double_extension()` returns `False` immediately when `len(suffixes) <= 1`, so a filename with a single extension (the common case) never evaluates the `BLOCKED_EXTENSIONS` membership inside that function — blocked single extensions are instead caught later by the direct `extension in BLOCKED_EXTENSIONS` check in `validate_file_extension()`.

- **Filename with no name, only an extension (`".py"`)**
  - *Behavior:* `Path(".py").suffix` is `""` (a leading dot with no stem is treated as a hidden file with no suffix, not as an extension), so this is treated the same as "no extension at all" and rejected with `"invalid_extension"`.

---

### MIME Type Edge Cases

- **`.txt`, `application/octet-stream`, and `text/plain` are accepted for almost every extension**
  - *Behavior:* `ALLOWED_MIME_TYPES` lists `"text/plain"` and/or `"application/octet-stream"` as acceptable for `.py`, `.java`, `.cpp`, and `.ts` (via `text/plain`) — these are exactly the generic fallbacks `python-magic` returns for plain-text or unrecognized binary content. In practice this means a file with, say, a `.py` extension but arbitrary plain-text content that isn't valid Python will still pass MIME validation, because libmagic can't distinguish "plain text" from "plain text that happens to be Python." The MIME check meaningfully rejects binary/structured formats (e.g. a PDF or PNG renamed to `.py`), not content mismatches within "looks like text."

- **`.cpp` MIME list has duplicate entries**
  - *Behavior:* `ALLOWED_MIME_TYPES[".cpp"]` repeats `"text/x-csrc"`, `"application/x-cplusplus"`, `"text/plain"`, and `"application/octet-stream"` twice. This has no functional effect (`in` membership is unaffected by duplicates) — noted here only so a future edit doesn't mistake it for two different intended values.

- **MIME allow-list is keyed by the already-validated extension**
  - *Behavior:* `validate_mime_type()` does `ALLOWED_MIME_TYPES[ext]` with a plain `KeyError`-able lookup — this is safe in practice only because `validate_file()` always calls `validate_file_extension()` first and passes its return value in, guaranteeing `ext` is a key that exists. Calling `validate_mime_type()` directly with an extension outside `ALLOWED_EXTENSIONS` would raise an unhandled `KeyError` instead of a `ValueError`.

---

### Filename Edge Cases

- **Empty filename (`filename=""`)**
  - *Behavior:* A multipart part with an explicit but empty `filename=""` is accepted by FastAPI as an `UploadFile` and reaches the handler. `get_file_extension("")` returns `""`, so this is treated the same as "no extension at all" and rejected with `"invalid_extension"` — a normal `415`, not a crash.

- **`filename=None` is a type-level possibility the router doesn't guard against**
  - *Behavior:* `UploadFile.filename` is typed as `str | None`, and `get_file_extension(None)` would call `Path(None)`, raising `TypeError` (not `ValueError`) — which would escape the router's `try/except ValueError` as an unhandled `500`. In practice this isn't reachable through a normal HTTP request: a multipart part with no `filename=` attribute at all is parsed by Starlette as a plain string form field rather than a file, and since the endpoint parameter is typed `UploadFile`, FastAPI itself rejects it with `422` before `filename` could ever be `None` in the handler. The gap only matters for code that calls `validate_file()`/`get_file_extension()` directly (e.g. from another internal caller or a test) without going through the HTTP layer.

- **Path-like or traversal filenames are not sanitized**
  - *Behavior:* Only `Path(filename).suffix`/`.suffixes` are inspected; the rest of the filename (directories, `..` segments, null bytes) is never validated or stripped. This is safe today because this router never writes the file to disk or otherwise uses the filename as a path — but the filename is echoed back verbatim in the JSON response, and any future code path that persists uploads using this filename would need its own sanitization.

---

## Known Limitations

| Limitation | Detail |
|---|---|
| **Error message omits `.txt`** | `UPLOAD_ERROR_MESSAGES["invalid_extension"]` reads `"Unsupported file type. Allowed types: .py, .js, .ts, .java, .cpp"` — `.txt` is a fully allowed extension (`ALLOWED_EXTENSIONS`) but is missing from this user-facing message, so a client that only reads the error text would think it's unsupported. |
| **Content-mismatch detection is weak by design** | Because `text/plain` and `application/octet-stream` are accepted for most code extensions, MIME validation catches wrong *formats* (binary/structured files misnamed as code) but not wrong *languages* (e.g. a `.txt` renamed to `.py`, or vice versa, when the content is plain ASCII either way). |
| **No content-based malware/static-analysis scanning** | Validation is limited to extension allow/block lists and libmagic MIME sniffing — there is no signature-based or heuristic scan of file contents beyond what `python-magic` infers from headers/magic bytes. |
| **Double-extension defense is case-sensitive** | See "Extension casing is normalized inconsistently" above — `BLOCKED_EXTENSIONS` membership in `has_double_extension()` will not match a differently-cased earlier suffix. |
| **Config is process-wide and unauthenticated to read** | `GET /upload/` exposes the full validation config to any caller. This is intended as a discovery endpoint for clients, but it also hands an attacker the exact allow/block lists and MIME map being enforced. |
