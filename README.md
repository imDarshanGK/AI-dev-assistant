<div align="center">

<img src="./assets/logo-dark.svg" alt="QyverixAI" width="300"/>

<br/>
<br/>

<h3>Debug. Understand. Ship faster.</h3>

<p>An open-source AI-powered developer assistant that detects bugs, explains code in plain English,<br/>and gives actionable improvement suggestions - instantly, no account needed.</p>

<br/>

[![CI](https://github.com/imDarshanGK/AI-dev-assistant/actions/workflows/ci.yml/badge.svg)](https://github.com/imDarshanGK/AI-dev-assistant/actions)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)](https://python.org)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![GSSoC 2026](https://img.shields.io/badge/GSSoC-2026-FF6B35?logoColor=white)](https://gssoc.girlscript.tech)

<br/>

**[Live Demo](https://qyverixai.onrender.com)** &nbsp;·&nbsp; **[API Docs](https://qyverixai.onrender.com/docs)** &nbsp;·&nbsp; **[Contributing Guide](CONTRIBUTING.md)** &nbsp;·&nbsp; **[Good First Issues](https://github.com/imDarshanGK/AI-dev-assistant/labels/good%20first%20issue)**

<br/>

> **GSSoC 2026 Contributors** -- Welcome! Read [CONTRIBUTING.md](CONTRIBUTING.md) for setup, then grab a [good first issue](https://github.com/imDarshanGK/AI-dev-assistant/labels/good%20first%20issue) to get started.

</div>

---

## What is QyverixAI?

QyverixAI is a code analysis workspace. Paste any code and get three things back instantly:

| | What you get |
|---|---|
| **Explain** | Language detection, plain-English summary, complexity estimate, function and class inventory |
| **Debug** | 40+ pattern checks across 5 languages with exact line numbers, code snippets, and fix suggestions |
| **Improve** | Documentation gaps, error handling, testing, type safety - plus a 0–100 quality score and letter grade A–F |

No account required. No API key needed. Works fully offline. Fully open source.

---

## Preview

<!-- Add a screenshot of the live site here -->
<!-- ![QyverixAI Preview](assets/preview.png) -->

---

## Features

| Feature | Detail |
|---|---|
| **40+ Bug Patterns** | ZeroDivisionError, bare except, hardcoded secrets, eval(), memory leaks, XSS, NullPointerException, and more |
| **5 Languages** | Python, JavaScript, TypeScript, Java, C++ |
| **Full Analysis Endpoint** | One call - explain + debug + improve combined, with timing metrics |
| **Quality Score** | 0–100 score with letter grade A–F and prioritised suggestions |
| **File Upload** | Drag-drop or upload `.py` `.js` `.ts` `.java` `.cpp` |
| **Dark / Light Mode** | Persisted across sessions |
| **Query History** | Last 50 analyses saved locally |
| **Saved Favorites** | Bookmark and reload any analysis |
| **Share Links** | Generate a short-lived URL for any analysis and send it to teammates |
| **Download Results** | Export full report as `.txt` |
| **LLM-Ready** | Plug in OpenAI, Groq, Ollama, or any OpenAI-compatible provider via env vars |
| **Rate Limiting** | 30 requests/minute per IP - configurable |
| **Swagger Docs** | Interactive API docs at `/docs` |
| **Gzip Compression** | Automatic response compression |

### Languages and patterns

| Language | Patterns detected |
|---|---|
| **Python** | ZeroDivisionError, bare except, eval/exec, mutable defaults, hardcoded secrets, wildcard imports, global variables, missing type hints, string concat in loops, assert in production, comparison to None |
| **JavaScript** | var usage, loose equality `==`, console.log, callback hell, innerHTML XSS, unhandled promises |
| **TypeScript** | `any` type, non-null assertion `!`, unhandled promises, missing env var validation |
| **Java** | NullPointerException risk, raw generics, broad catch, String `==` comparison, System.exit |
| **C++** | Memory leaks, unsafe gets/scanf, `using namespace std`, signed/unsigned mismatch |

---

## Quick Start

### Prerequisites

- Python 3.11 or 3.12
- pip
- A modern browser (Chrome, Firefox, Edge, Safari)

### 1 - Clone

```bash
git clone https://github.com/imDarshanGK/AI-dev-assistant.git
cd AI-dev-assistant
```

### 2 - Run the backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```
### Environment Setup

Copy `.env.example` to `.env`

```bash
cp .env.example .env
```

Update the environment variable values if needed before running the app.

Important variables:
- `JWT_SECRET`
- `DATABASE_URL`
- `RATE_LIMIT_PER_MINUTE`
- `LLM_API_KEY` (optional)

The app can still run without external AI providers when `LLM_ENABLED=false`.

| Endpoint | URL |
|---|---|
| API root | http://localhost:8000/ |
| Interactive docs | http://localhost:8000/docs |
| Health check | http://localhost:8000/health |
| Container health check | http://localhost:8000/healthz/live |
| Signup | http://localhost:8000/auth/signup |
| Login | http://localhost:8000/auth/login |
| Current user | http://localhost:8000/auth/me |

### 3 - Open the frontend

```bash
# No build step required - open directly in your browser
open frontend/index.html
```

Set the API URL field to `http://localhost:8000`, click **Ping** to confirm the green Connected status, then paste any code and click **Analyze Code**.

---

## API Reference

All endpoints accept `POST` with `Content-Type: application/json`.

**Request body**
```json
{ "code": "your code here", "language": "python" }
```

`language` is optional — the engine auto-detects it from the code.

---

### `POST /explanation/`

Returns a plain-English breakdown of the code.

```json
{
  "language": "Python",
  "summary": "A short Python snippet (5 lines) that performs a focused task.",
  "key_points": [
    "Written in Python — 5 non-blank lines of code.",
    "Defines 1 function: calculate.",
    "Contains conditional logic — branching control flow."
  ],
  "complexity": "Beginner",
  "line_count": 6,
  "function_count": 1,
  "class_count": 0
}
```

---

### `POST /debugging/`

Returns detected issues with line numbers, code snippets, and fix suggestions.

```json
{
  "issues": [
    {
      "type": "ZeroDivisionError",
      "line": 2,
      "description": "Potential division by zero — divisor may be 0 at runtime.",
      "suggestion": "Guard the divisor: if b == 0: return None",
      "severity": "error",
      "code_snippet": "result = a / b"
    }
  ],
  "summary": "Found 1 issue: 1 error, 0 warnings, 0 info.",
  "clean": false,
  "error_count": 1,
  "warning_count": 0,
  "info_count": 0
}
```

---

### `POST /suggestions/`

Returns improvement suggestion cards with a quality score.

```json
{
  "suggestions": [
    {
      "category": "Documentation",
      "description": "Less than 10% of lines are comments. Add docstrings.",
      "example": "\"\"\"Calculate the area of a circle given radius r.\"\"\"",
      "priority": "medium"
    }
  ],
  "overall_score": 72,
  "grade": "B",
  "next_step": "Good work. Address the medium-priority items next."
}
```

---

### `POST /analyze/`

All three analyses in one response with timing.

```json
{
  "provider": "rule-based",
  "model": "qyverix-engine-v3",
  "explanation": { "...": "..." },
  "debugging":   { "...": "..." },
  "suggestions": { "...": "..." },
  "analysis_time_ms": 1.84
}
```

---

### `POST /share/` and `GET /share/{id}`

Create a share link for a saved analysis, then load it back by ID for seven days after creation.

`POST /share/` accepts `{ "code": "...", "result": { ... } }` and returns `{ "id": "short_id" }`.

`GET /share/{id}` returns the saved `{ code, result, created_at }` payload or `404` if the share is missing or expired.

---

## Project Structure

```
AI-dev-assistant/
├── assets/                           # Logo and brand assets
│   ├── logo-dark.svg
│   ├── logo-light.svg
│   └── icon.svg
├── backend/
│   ├── app/
│   │   ├── main.py                   # FastAPI app, middleware, rate limiting
│   │   ├── schemas.py                # Pydantic v2 request/response models
│   │   ├── routers/
│   │   │   ├── analyze.py            # POST /analyze/
│   │   │   ├── debugging.py          # POST /debugging/
│   │   │   ├── explanation.py        # POST /explanation/
│   │   │   ├── suggestions.py        # POST /suggestions/
│   │   │   └── auth.py               # /auth/signup, /auth/login, /auth/me
│   │   └── services/
│   │       ├── code_assistant.py     # Rule-based engine — 40+ patterns, 5 languages
│   │       └── ai_provider.py        # Optional LLM abstraction layer
│   ├── requirements.txt
│   └── tests/
│       └── test_endpoints.py         # 52 tests across all endpoints and languages
├── frontend/
│   └── index.html                    # Complete UI — no build step, self-contained
├── .github/
│   └── workflows/
│       └── ci.yml                    # CI on Python 3.11 + 3.12, lint with Ruff
├── .env.example
├── Dockerfile
├── render.yaml
├── CONTRIBUTING.md
└── README.md
```

---

## Running Tests

```bash
cd backend
pytest -v
```

52 tests covering all endpoints, all 5 languages, 10+ individual bug patterns, suggestions scoring, full analysis, and edge cases including empty code, unicode, and single-line input.

Tests run automatically on every push and pull request via GitHub Actions across Python 3.11 and 3.12.

---

## Deployment

### Render - recommended, free tier

1. Fork this repository
2. Go to [render.com](https://render.com) → New Web Service
3. Connect your fork - `render.yaml` configures everything automatically
4. Add environment variable: `PYTHON_VERSION` = `3.12.0`
5. Click Deploy - your app goes live at `https://your-service.onrender.com`

> **Note:** The free tier sleeps after 15 minutes of inactivity. The first request after sleep takes 30–60 seconds to wake up. This is expected.

### Docker

```bash
docker build -t qyverixai .
docker run -p 8000:8000 qyverixai
```
### Docker Compose

Run the complete local development environment:

```bash
docker compose up --build
```

Available services:

- Frontend → http://localhost:3000
- Backend API → http://localhost:8000
- PostgreSQL → localhost:5432

Stop containers:

```bash
docker compose down
```

---

## Observability

QyverixAI exposes operational endpoints designed for container orchestration and Prometheus scraping.

### Health probes

| Endpoint | Purpose | Behaviour |
|---|---|---|
| `GET /healthz/live` | Liveness probe | Returns `200` while the process can answer HTTP. Does **not** check external dependencies — Kubernetes restarts the container on failure, so this must never depend on recoverable backends. |
| `GET /healthz/ready` | Readiness probe | Returns `200` only when every dependency check (currently: database) passes. Returns `503` with a per-check breakdown otherwise. Kubernetes removes the pod from service load balancers on failure but does **not** restart it. |
| `GET /health` | Legacy combined check | Retained for backward compatibility with anything already pointing at it. |

Example response from `/healthz/ready` when degraded:

```json
{
  "status": "degraded",
  "checks": {
    "database": {
      "ok": false,
      "elapsed_ms": 2003.41,
      "error": "OperationalError: connection refused"
    }
  }
}
```

A ready-to-copy Kubernetes manifest with probes wired up lives at [`deploy/k8s/deployment.example.yaml`](deploy/k8s/deployment.example.yaml).

### Prometheus metrics

`GET /metrics` exposes the Prometheus exposition format. Metric families:

| Metric | Type | Labels | Description |
|---|---|---|---|
| `qyverixai_http_requests_total` | Counter | `method`, `endpoint`, `status_code` | Total requests processed. |
| `qyverixai_http_request_duration_seconds` | Histogram | `method`, `endpoint` | Request latency. Buckets: 5ms → 30s. |
| `qyverixai_http_requests_in_progress` | Gauge | `method`, `endpoint` | Concurrent in-flight requests. |
| `qyverixai_http_request_exceptions_total` | Counter | `method`, `endpoint`, `exception_type` | Unhandled exceptions raised during request handling. |
| `qyverixai_app_info` | Gauge | `version`, `ai_provider` | Static identity, always `1`. |

The `endpoint` label is the matched **route template** (e.g. `/share/{share_id}`), not the raw URL — this keeps label cardinality bounded as IDs flow through the system. The `/metrics` endpoint itself is excluded from observation to prevent a scrape feedback loop.

A drop-in Prometheus scrape config is provided at [`deploy/prometheus/scrape-config.example.yaml`](deploy/prometheus/scrape-config.example.yaml).

#### Configuration

| Variable | Default | Description |
|---|---|---|
| `METRICS_ENABLED` | `true` | Set to `false` to disable `/metrics` and skip the middleware entirely. |
| `METRICS_AUTH_TOKEN` | — | Optional bearer token. When set, scrapers must send `Authorization: Bearer <token>`. |
| `PROMETHEUS_MULTIPROC_DIR` | — | Set when running `uvicorn --workers N > 1` so scrapes aggregate across workers. The directory must exist and be writable. |

---

## Optional LLM Integration

QyverixAI works fully offline with its built-in rule-based engine. To enable richer AI-powered analysis, add these environment variables:

```env
LLM_ENABLED=true
LLM_API_KEY=your-key-here
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
LLM_TIMEOUT_SECONDS=30
```

Compatible with **OpenAI**, **Groq** (free tier), **Together AI**, **Ollama** (local, free), and any OpenAI-compatible endpoint.

> Never commit API keys. Use environment variables or your host's secrets manager.

### Provider Reliability
The backend includes built-in resilience for LLM requests:
- **Exponential Backoff**: Automatic retries on timeouts and connection failures.
- **Rate Limit Handling**: Pauses and retries on HTTP 429 Rate Limit responses.
- **Graceful Fallback**: Preserves offline/rule-based features seamlessly if the LLM provider becomes fully unavailable.

---

## Configuration Reference

| Variable | Default | Description |
|---|---|---|
| `RATE_LIMIT_PER_MINUTE` | `30` | Max requests per IP per minute |
| `LLM_ENABLED` | `false` | Enable LLM provider |
| `LLM_API_KEY` | — | API key for your LLM provider |
| `LLM_BASE_URL` | `https://api.openai.com/v1` | LLM base URL |
| `LLM_MODEL` | `gpt-4o-mini` | Model name |
| `LLM_TIMEOUT_SECONDS` | `30` | Request timeout in seconds |

Copy `.env.example` to `.env` and fill in values as needed.

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI 0.115+, Pydantic v2, Python 3.12 |
| Frontend | HTML5, CSS3, Vanilla JS - no build step, zero dependencies |
| Testing | Pytest, FastAPI TestClient |
| Linting | Ruff |
| Deployment | Docker, Render |
| CI | GitHub Actions - Python 3.11 + 3.12 matrix |

---

## Contributing

QyverixAI is a **GSSoC 2026** open source project. Contributors of all levels are welcome.

```bash
# 1. Fork the repo on GitHub
# 2. Clone your fork
git clone https://github.com/YOUR_USERNAME/AI-dev-assistant.git

# 3. Create a branch
git checkout -b feat/your-feature-name

# 4. Install and test
cd backend && pip install -r requirements.txt
pytest -v   # all 22 tests must pass

# 5. Push and open a pull request
```

Read the full workflow, code standards, and pattern guide in [CONTRIBUTING.md](CONTRIBUTING.md).

### Good first issues for GSSoC contributors

| Task | Label |
|---|---|
| Add a new bug detection pattern for any language | `easy` |
| Add test cases for edge cases | `easy` |
| Improve explanation key points for a specific language | `easy` |
| Add ARIA labels and keyboard navigation to frontend | `medium` |
| Add support for a new file type in file upload | `medium` |
| Build AST-based deep analysis for Python | `hard` |
| Add VS Code extension | `hard` |

Browse all open issues: [github.com/imDarshanGK/AI-dev-assistant/issues](https://github.com/imDarshanGK/AI-dev-assistant/issues)

---

## Roadmap

- [x] Rule-based code explanation engine
- [x] Bug detection — 40+ patterns across 5 languages
- [x] Improvement suggestions with quality score and letter grade A–F
- [x] Full-analysis combined endpoint with timing metrics
- [x] Rate limiting per IP — configurable
- [x] Gzip compression middleware
- [x] Dark / light theme, file upload, drag-and-drop, history, favorites, download
- [x] LLM provider abstraction layer — OpenAI, Groq, Ollama compatible
- [x] CI matrix — Python 3.11 + 3.12
- [ ] AST-based deep analysis for Python
- [ ] Per-user history with database backend (SQLite → PostgreSQL)
- [ ] VS Code extension
- [ ] AI-powered explanations — LLM integration GA
- [ ] Multi-file analysis support
- [ ] Diff view — before/after code improvements

---

## License

MIT © [Darshan G K](https://github.com/imDarshanGK)

---

<div align="center">

<br/>

**[Star this repo](https://github.com/imDarshanGK/AI-dev-assistant)** &nbsp;·&nbsp;
**[Report a bug](https://github.com/imDarshanGK/AI-dev-assistant/issues/new?template=bug_report.md)** &nbsp;·&nbsp;
**[Request a feature](https://github.com/imDarshanGK/AI-dev-assistant/issues/new?template=feature_request.md)**

<br/>

Built for the open source community &nbsp;·&nbsp; GSSoC 2026

</div>
