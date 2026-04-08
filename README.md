
# AI Developer Assistant

<p align="center">
  <img src="screenshots/demo.png" alt="AI Developer Assistant Demo" width="500"/>
</p>

<p align="center">
  <a href="https://github.com/imDarshanGK/AI-dev-assistant/actions/workflows/ci.yml"><img src="https://img.shields.io/github/actions/workflow/status/imDarshanGK/AI-dev-assistant/ci.yml?branch=main" alt="CI"></a>
  <a href="https://github.com/imDarshanGK/AI-dev-assistant/stargazers"><img src="https://img.shields.io/github/stars/imDarshanGK/AI-dev-assistant?style=social" alt="GitHub stars"></a>
  <a href="https://github.com/imDarshanGK/AI-dev-assistant/network/members"><img src="https://img.shields.io/github/forks/imDarshanGK/AI-dev-assistant?style=social" alt="GitHub forks"></a>
  <a href="https://github.com/imDarshanGK/AI-dev-assistant/issues"><img src="https://img.shields.io/github/issues/imDarshanGK/AI-dev-assistant" alt="GitHub issues"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/imDarshanGK/AI-dev-assistant" alt="License"></a>
</p>

An open-source AI-powered developer assistant that helps beginners understand code, debug errors, and improve programming skills with simple explanations.

The current version includes a rule-based assistant engine and an AI-provider abstraction layer, so it works today and is ready for future live LLM integration.

## Why This Project

This project is designed for learners and new contributors:

- Understand code in simple language
- Learn debugging patterns using clear issue reports
- Improve code quality with actionable suggestions
- Explore a clean architecture that is ready for future LLM integration

## Features

- Code explanation endpoint with language guess and key points
- Debugging endpoint with rule-based issue detection
- Improvement endpoint with suggestion cards and next steps
- Unified full analysis endpoint that returns explanation, debugging, and suggestions in one response
- Input validation and beginner-friendly error messages
- Frontend with API URL setting, clear UX states, and formatted output
- Frontend dark mode toggle, file upload (.py/.js/.java), result copy button, and query history
- Drag-drop upload, side-by-side editor/output view, language auto-detect UI, and keyboard shortcuts
- Result download as TXT
- Dashboard summary cards and saved favorite results stored locally in the browser
- Backend hardening: rate limiting, request-size limits, request-id headers, and centralized exception responses
- Optional error tracking (Sentry DSN) and caching (Redis URL with in-memory fallback)
- Swagger docs available at /docs

## Tech Stack

- Backend: FastAPI, Pydantic
- Frontend: HTML, CSS, JavaScript
- Testing: Pytest, FastAPI TestClient

## Project Structure

```text
AI-dev-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   ├── schemas.py
│   │   ├── routers/
│   │   │   ├── analyze.py
│   │   │   ├── debugging.py
│   │   │   ├── explanation.py
│   │   │   └── suggestions.py
│   │   └── services/
│   │       ├── ai_provider.py
│   │       └── code_assistant.py
│   ├── requirements.txt
│   └── tests/
│       ├── test_endpoints.py
│       └── test_ping.py
├── frontend/
│   ├── index.html
│   ├── script.js
│   ├── style.css
│   └── public/
│       └── favicon.ico
├── screenshots/
│   └── demo.png
├── CONTRIBUTING.md
├── LICENSE
└── README.md
```

## Setup Instructions

### 1. Start Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend URLs:

- API root: http://localhost:8000/
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### 2. Start Frontend

Open frontend/index.html in your browser and keep backend running.

## API Usage

### POST /explanation/

Request:

```json
{
  "code": "def add(a, b):\n    return a + b"
}
```

### POST /debugging/

Request:

```json
{
  "code": "def broken(\n  return 1"
}
```

### POST /suggestions/

Request:

```json
{
  "code": "x=1\nprint(x)"
}
```

### POST /analyze/

Request:

```json
{
  "code": "def add(a, b):\n    return a + b"
}
```

This endpoint returns provider metadata and all three analysis sections in one response.

## Running Tests

```bash
cd backend
pytest -q
```

GitHub Actions runs the same test command automatically on every push and pull request to `main`.

## Deployment

Recommended deployment setup for this project:

### Backend on Render

1. Connect this GitHub repository to Render.
2. Use the `render.yaml` blueprint at the repository root.
3. Render will build the backend from `backend/Dockerfile`.
4. The health check endpoint is `/health`.

### Frontend as a Static Site

1. Deploy the `frontend/` folder to a static host such as Netlify or Render Static Site.
2. Open the frontend and enter the deployed backend URL in the API field.
3. The frontend remembers the last API URL in the browser for easier reuse.

### If Backend and Frontend Share One Service

Open the service root URL in your browser. The app now redirects to the frontend page instead of showing the API JSON response.
The frontend app is also available at `/app/`.

### Dashboard Data

Saved favorites and query history currently use browser local storage. This is the foundation for a later database-backed dashboard and user accounts.

### Environment Variables

If you want to change the provider metadata later, set these variables on the backend host:

- `AI_PROVIDER`
- `AI_MODEL`
- `CACHE_ENABLED`
- `CACHE_TTL_SECONDS`
- `REDIS_URL` (optional)
- `SENTRY_DSN` (optional)
- `SENTRY_TRACES_SAMPLE_RATE` (optional)

The current app uses a rule-based engine and provider abstraction so it is ready for future AI integration.

## Screenshots

<p align="center">
  <img src="screenshots/demo.png" alt="Demo Screenshot" width="700"/>
</p>

## Roadmap

- Add language-specific analyzers (Python, JS, Java)
- Add optional LLM provider adapter layer
- Add CI workflow for lint and test checks
- Add Docker setup for one-command run
- Add richer frontend result cards

## How To Contribute

See CONTRIBUTING.md for full contribution workflow.

1. Fork repository
2. Create a feature branch
3. Make and test changes
4. Open a pull request

## Beginner-Friendly Issues

Start with issues labeled good first issue:

https://github.com/imDarshanGK/AI-dev-assistant/labels/good%20first%20issue

## Open Source Support Files

- .github/ISSUE_TEMPLATE/bug_report.md
- .github/ISSUE_TEMPLATE/feature_request.md
- .github/pull_request_template.md
- CODE_OF_CONDUCT.md

## Upgrade Planning Docs

A full audited feature status and phased roadmap are stored in:

- docs/upgrade-plan/current-status.md
- docs/upgrade-plan/phased-roadmap.md
- docs/upgrade-plan/suggested-next-steps.md
