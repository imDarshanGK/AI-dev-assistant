
# AI Developer Assistant

<p align="center">
  <img src="screenshots/demo.png" alt="AI Developer Assistant Demo" width="400"/>
</p>

<p align="center">
  <a href="https://github.com/imDarshanGK/AI-dev-assistant/stargazers"><img src="https://img.shields.io/github/stars/imDarshanGK/AI-dev-assistant?style=social" alt="GitHub stars"></a>
  <a href="https://github.com/imDarshanGK/AI-dev-assistant/network/members"><img src="https://img.shields.io/github/forks/imDarshanGK/AI-dev-assistant?style=social" alt="GitHub forks"></a>
  <a href="https://github.com/imDarshanGK/AI-dev-assistant/issues"><img src="https://img.shields.io/github/issues/imDarshanGK/AI-dev-assistant" alt="GitHub issues"></a>
  <a href="LICENSE"><img src="https://img.shields.io/github/license/imDarshanGK/AI-dev-assistant" alt="License"></a>
</p>

---

## 🌟 Why This Project

AI Developer Assistant is designed to help beginners understand, debug, and improve code with simple, friendly explanations. It aims to make programming more accessible and collaborative for everyone.

---

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


## 📸 Screenshots

<p align="center">
  <img src="screenshots/demo.png" alt="Demo Screenshot" width="600"/>
</p>

---

## 🚀 Roadmap

- [ ] Add more advanced code analysis features
- [ ] Integrate AI/LLM for smarter suggestions
- [ ] Add user authentication (optional)
- [ ] Improve frontend UI/UX
- [ ] Add Docker support for easy setup
- [ ] Write more tests and CI integration

---

## 👨‍💻 How to Contribute

We welcome all contributions! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

1. Fork the repository
2. Create a new branch for your feature or bugfix
3. Make your changes and test them
4. Submit a pull request with a clear description

---

## 🏷️ Beginner-friendly Issues

Check out [issues labeled "good first issue"](https://github.com/imDarshanGK/AI-dev-assistant/labels/good%20first%20issue) to start contributing as a beginner!

---

## Contributing
See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.
