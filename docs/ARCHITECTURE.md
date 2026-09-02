# Architecture — AI Developer Assistant

## Overview

AI Developer Assistant is an open-source tool that helps developers
understand code, detect bugs, and get plain-English explanations.
It uses a rule-based engine for fast analysis and optionally connects
to an LLM (like OpenAI or Groq) for deeper insights.

> **New since v1:** AI Chat, Live Collaboration, ZIP Analysis, Streaming Analysis, expanded multi-language rule engine.

---

## System Architecture

```mermaid
flowchart TD
    A[User - Browser] -->|Pastes code + clicks Analyze| B[Vanilla JS Frontend\nindex.html]
    B -->|HTTP POST /analyze/| C[FastAPI Backend\nPort 8000]
    C --> D{Analysis Mode}
    D -->|Rule-based| E[Rule Engine\ncode_assistant.py\n65+ patterns · 7 languages]
    D -->|LLM mode| F[AI Provider Layer\nai_provider.py]
    F --> G[OpenAI / Groq / Ollama]
    E --> H[Response JSON]
    G --> H
    H -->|Returns results| B
    C <--> I[PostgreSQL Database\nAuth · Share links · History]
    C --> J[Docker / Render\nDeployment]
```

---

## Request Flow

1. User pastes code into the editor in the browser
2. Frontend sends a `POST` request to `/analyze/` on the FastAPI backend
3. Backend decides: use rule-based engine or LLM based on config
4. Result is returned as JSON and rendered in the UI

---

## Layers Explained

### 1. Frontend
- **File:** `frontend/index.html`
- Plain HTML + Vanilla JavaScript (no framework)
- Sends code to backend via `fetch()` API
- Renders results: Plain-English breakdown, suggestions, code fixes

### 2. FastAPI Backend
- **File:** `main.py`
- Runs on port `8000`
- Handles routing, auth middleware, and API responses
- Connects frontend to the analysis engine and database

### 3. Rule-Based Engine
- **File:** `code_assistant.py`
- 65+ pattern rules across 7 languages (Python, JavaScript, TypeScript, Java, C++, PHP, Rust)
- Fast, offline, no API key needed
- Detects common bugs, anti-patterns, and style issues

### 4. LLM Abstraction Layer
- **File:** `ai_provider.py`
- Optional — only used when an API key is configured
- Supports OpenAI, Groq, and Ollama
- Provides deeper analysis and natural language explanations

### 5. Database
- **Technology:** PostgreSQL
- Stores user auth, share links, and analysis history
- Used only when auth/sharing features are enabled

### 6. Deployment
- Supports **Docker** (via `Dockerfile`)
- Also deployable on **Render** (cloud hosting)

### 7. AST Analyzer
- **File:** `ast_analyzer.py`
- Provides deeper Python code analysis using the AST
- Helps detect syntax, flow, and pattern issues beyond surface-level matching

### 8. Authentication / Security
- **Files:** `security.py`, `token_denylist.py`
- Handles JWT creation, verification, and route authorization
- `token_denylist.py` revokes logged-out tokens by storing JWT `jti` values until expiry

### 9. Live Collaboration
- **File:** `collaboration.py`
- Manages WebSocket rooms, session state, live code sync, cursor presence, and comments
- Enables real-time multi-user collaboration over `/ws/{session_id}`

### 10. Duplicate Code Detector
- **File:** `duplicate_detector.py`
- Token normalization, k-gram winnowing fingerprinting, and Jaccard similarity
- Detects repeated functions/blocks across single files and multi-file project ZIPs

---

## Key Files for New Contributors

| File | Purpose |
|------|---------|
| `main.py` | FastAPI app entry point |
| `code_assistant.py` | Rule-based analysis engine |
| `ai_provider.py` | LLM provider abstraction |
| `frontend/index.html` | Entire frontend UI |
| `requirements.txt` | Python dependencies |
| `Dockerfile` | Container setup |
| `ast_analyzer.py` | Deep Python AST analysis |
| `duplicate_detector.py` | Multi-language duplicate code detection engine |
| `security.py` | JWT auth helpers and route protection |
| `sanitize.py` | Input sanitization for code and language hints |
| `token_denylist.py` | JWT logout revocation store |
| `collaboration.py` | WebSocket room state and live collaboration |
| `middleware.py` | Request middleware for auth, security, and observability |
| `observability.py` | Metrics, logging, and health instrumentation |
| `README.md` | Setup and usage guide |

---

## Rule-Based vs LLM Mode

| | Rule-Based | LLM Mode |
|---|---|---|
| Speed | Fast | Slower |
| Requires API key | No | Yes |
| Works offline | Yes | No |
| Analysis depth | Pattern matching | Deep reasoning |
| Languages supported | 7 | Any |

---

## Contributing

New to the project? Start here:
1. Read `README.md` for setup instructions
2. Look at `code_assistant.py` to understand how rules work
3. Check open issues labeled `good first issue`
4. See `CONTRIBUTING.md` for PR guidelines
