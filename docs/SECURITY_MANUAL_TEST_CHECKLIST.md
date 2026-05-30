# Security manual testing checklist — sanitization & XSS

Use this checklist after code changes to sanitization or rendering.  
**Goal:** payloads display as plain text only; no dialogs; normal code still works.

## Prerequisites

- Backend running: `cd backend && uvicorn app.main:app --reload`
- Frontend open: `frontend/index.html` (or your static server)
- Browser DevTools open → **Console** (watch for errors) and disable breakpoints on `alert` if debugging

Optional: install a DOM sink monitor extension, or paste in console before testing:

```javascript
window.__xssAlerts = [];
const _alert = window.alert;
window.alert = (...args) => { window.__xssAlerts.push(args); _alert(...args); };
```

After each test section, run: `window.__xssAlerts` — must stay `[]` (no popups).

---

## 1. Live API — reflected payloads

For each payload below, paste into the code editor → **Analyze** (full analysis mode).

| # | Payload | Pass criteria |
|---|---------|---------------|
| 1 | `<script>alert('xss')</script>` | No alert; results show escaped text or literal in panels |
| 2 | `<img src=x onerror="alert(1)">` | No alert; no image execution |
| 3 | `<svg/onload=alert(1)>` | No alert |
| 4 | `${alert(1)}` | Shown as literal `${...}` text |
| 5 | `{{constructor.constructor('alert(1)')()}}` | Shown as plain text |
| 6 | `&lt;script&gt;alert(1)&lt;/script&gt;` | Displays encoded entities as text, not decoded HTML |
| 7 | `&#60;script&#62;alert(1)&#60;/script&#62;` | Same as above |

**Verify in DevTools → Elements:** search for `<script` inside `#explainResult`, `#debugResult`, `#suggestResult` — must find **none** (only `&lt;script` if visible).

---

## 2. Stored history / favorites (localStorage)

1. DevTools → **Application** → **Local Storage** → your origin.
2. Set `qyx_history` to:

```json
[{
  "id": "1');alert(1);//",
  "code": "<script>alert('stored')</script>",
  "preview": "<img src=x onerror=alert(1)>",
  "lang": "<svg/onload=alert(1)>",
  "ts": "${alert(1)}",
  "result": {
    "explanation": {
      "summary": "<script>alert('stored')</script>",
      "complexity": "Beginner",
      "language": "Python",
      "key_points": ["<img onerror=alert(1)>"],
      "line_count": 1,
      "function_count": 0,
      "class_count": 0
    }
  }
}]
```

3. Reload the page.

| Check | Pass |
|-------|------|
| No alert on load | ☐ |
| Poisoned string `id` entry **not** clickable or absent | ☐ |
| History row HTML has **no** `onclick=` / `onkeydown=` | ☐ |
| Clicking a **valid** history row loads code without alert | ☐ |

Repeat with `qyx_favorites` and the favorites panel.

---

## 3. File upload & drag-drop

| Step | Pass |
|------|------|
| Create `.py` file containing payload #1 | ☐ |
| Upload via file picker | No alert; editor shows literal text |
| Drag same file onto page | No alert |

---

## 4. Normal code still works

| Sample | Pass |
|--------|------|
| `def add(a, b):\n    return a + b` | Analysis returns explanation + score |
| `if x < 10 and y > 0: print('ok')` | `<` `>` preserved in editor after analyze |
| `#include <iostream>\nint main() { return 0; }` (C++) | Language detected; no corruption |

---

## 5. Backend API (curl / Swagger)

```bash
curl -s -X POST http://127.0.0.1:8000/analyze/ \
  -H "Content-Type: application/json" \
  -d "{\"code\": \"<script>alert(1)</script>\"}"
```

| Check | Pass |
|-------|------|
| HTTP 200 | ☐ |
| Valid JSON response | ☐ |
| No server crash | ☐ |

Automated coverage: `pytest tests/test_sanitization.py tests/test_sanitization_payloads.py`

---

## 6. VS Code extension webview (if applicable)

1. Open extension; run **Analyze** on file containing payload #1.
2. Webview opens.

| Check | Pass |
|-------|------|
| No alert in VS Code | ☐ |
| Issue type / summary show escaped text | ☐ |
| View webview source: no raw `<script>` in dynamic sections | ☐ |

---

## 7. Automated test commands

```bash
# Backend
cd backend
pip install -r requirements.txt
pytest tests/test_sanitization.py tests/test_sanitization_payloads.py -v

# Frontend (Node 18+)
cd frontend/tests
npm test
```

---

## Sign-off

| Role | Name | Date | All sections pass |
|------|------|------|-------------------|
| Developer | | | ☐ |
| Reviewer | | | ☐ |
