
# AI Developer Assistant

<p align="center">
  <img src="screenshots/demo.png" alt="AI Developer Assistant Demo" width="500"/>
</p>

<p align="center">
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
