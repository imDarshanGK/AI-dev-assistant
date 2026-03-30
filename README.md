# AI Developer Assistant

A beginner-friendly web application to help users understand, debug, and improve code using AI-powered suggestions.

## Features
- Input code and get simple explanations
- Debugging assistant to identify errors and suggest fixes
- Code improvement suggestions
- Beginner-friendly responses

## Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** Simple HTML/CSS (React optional)
- **API-based design** for future AI integration

## Project Structure
```
AI-dev-assistant/
├── backend/
│   ├── app/
│   │   ├── main.py
│   │   └── routers/
│   │       ├── explanation.py
│   │       ├── debugging.py
│   │       └── suggestions.py
│   ├── requirements.txt
│   └── tests/
│       └── test_ping.py
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── README.md
└── CONTRIBUTING.md
```

## Getting Started

### Backend (FastAPI)
1. Navigate to `backend/`
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the server:
   ```bash
   uvicorn app.main:app --reload
   ```

### Frontend
1. Open `frontend/index.html` in your browser.

## Example API Requests

### 1. Get Code Explanation
```
POST /explanation/
{
  "code": "print('Hello, world!')"
}
```
**Response:**
```
{
  "explanation": "This is a simple explanation for: print('Hello, world!')..."
}
```

### 2. Debug Code
```
POST /debugging/
{
  "code": "print('Hello, world!')"
}
```
**Response:**
```
{
  "errors": ["No errors found (sample)."],
  "suggestions": ["Add more error handling."]
}
```

### 3. Code Improvement Suggestions
```
POST /suggestions/
{
  "code": "x=1"
}
```
**Response:**
```
{
  "suggestions": ["Consider using more descriptive variable names."]
}
```

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
