# LEARN.md

# How I Built QyverixAI

Welcome! 👋

This document explains how I built **QyverixAI**, an open-source AI-powered developer assistant. My goal was to create a tool that helps developers understand code, detect bugs, and improve code quality while also serving as a learning resource for students and open-source contributors.

---

# Why I Started This Project

As a student learning Python, Artificial Intelligence, and software development, I wanted to build a real-world project that combined multiple technologies into one application.

Instead of creating another simple code editor, I wanted to build something that could:

- Explain code in plain English
- Detect programming mistakes
- Suggest improvements
- Analyze complete projects
- Help students learn programming faster

The project also gave me an opportunity to learn how large open-source projects are organized.

---

# Planning the Project

Before writing code, I planned the project by identifying the main features.

Core features included:

- Code explanation
- Bug detection
- Improvement suggestions
- Project-wide ZIP analysis
- AI-powered chat assistant
- Real-time collaboration
- Authentication
- Query history
- Favorites
- Shareable analysis links

Breaking the project into smaller milestones made development much easier.

---

# Choosing the Technology Stack

## Backend

- Python
- FastAPI
- Pydantic
- SQLAlchemy
- PostgreSQL / SQLite
- JWT Authentication

## Frontend

- HTML
- CSS
- JavaScript

## Real-time Features

- WebSockets
- Server-Sent Events (SSE)

## Development Tools

- Git
- GitHub
- GitHub Actions
- Docker
- Docker Compose
- Render

---

# Building the Backend

The backend was developed using FastAPI.

I organized the project into different modules:

- API routers
- Services
- Models
- Database
- Authentication
- Utilities

This structure keeps the code clean and easier to maintain.

---

# Creating the Code Analysis Engine

The most challenging part of the project was creating the rule-based code analysis engine.

It performs tasks such as:

- Language detection
- Bug detection
- Complexity estimation
- Documentation analysis
- Quality scoring
- Improvement suggestions

Python also includes AST-based analysis for deeper code inspection.

---

# Building the Frontend

The frontend was designed to be simple and beginner-friendly.

Users can:

- Paste code
- Upload ZIP projects
- View detected bugs
- Read explanations
- Chat with the AI assistant
- Download reports
- Share results

The goal was to create an interface that works without unnecessary complexity.

---

# Adding AI Features

The project supports optional LLM integration.

Compatible providers include:

- OpenAI
- Groq
- Ollama
- OpenAI-compatible APIs

When no API key is configured, the application automatically falls back to the built-in rule-based engine.

---

# Implementing Real-Time Collaboration

I added WebSocket support so multiple users can work together.

Features include:

- Live code synchronization
- Shared editing
- Cursor presence
- Comments
- Collaborative coding sessions

---

# Authentication

Authentication was implemented using JWT tokens.

Additional features include:

- User registration
- Login
- Logout
- Token revocation
- Favorites
- User history

---

# Security

Security was an important part of the project.

Implemented features include:

- Rate limiting
- Secret scanning
- File validation
- Input sanitization
- JWT security
- MIME type verification

---

# Testing

To improve reliability, I added automated tests for:

- API endpoints
- Authentication
- Bug detection
- File uploads
- WebSockets
- Security
- Integration tests

GitHub Actions automatically runs these tests for every pull request.

---

# Deployment

The application can be deployed using:

- Docker
- Docker Compose
- Render
- Kubernetes

This makes it easier for contributors to run the project locally or deploy it online.

---

# Open Source Collaboration

One of my goals was to build a project that welcomes contributors.

The repository includes:

- CONTRIBUTING.md
- CODE_OF_CONDUCT.md
- Security Policy
- Good First Issues
- GitHub Actions
- Documentation

These resources help beginners make their first open-source contribution.

---

# Challenges I Faced

During development I learned how to solve challenges such as:

- Designing a scalable project structure
- Building REST APIs
- Managing authentication
- Working with databases
- Implementing WebSockets
- Writing automated tests
- Maintaining code quality
- Reviewing pull requests
- Collaborating with contributors

Each challenge helped me become a better software developer.

---

# What I Learned

This project helped me improve my understanding of:

- Python
- FastAPI
- REST APIs
- Artificial Intelligence
- Git and GitHub
- Docker
- PostgreSQL
- Authentication
- Testing
- CI/CD
- Open Source Collaboration

---

# Future Improvements

Some planned features include:

- More programming language support
- Better AI explanations
- Marketplace release for the VS Code extension
- Persistent collaboration rooms
- CLI version
- Additional static analysis rules
- Improved code visualization

---

# Acknowledgements

Thanks to the open-source community and everyone who contributed to this project through issues, pull requests, reviews, and suggestions.

Every contribution helped improve QyverixAI.

---

# Get Started

Clone the repository:

```bash
git clone https://github.com/imDarshanGK/AI-dev-assistant.git
cd AI-dev-assistant
```

Follow the setup instructions in the **README.md** to run the application locally.

Happy coding! 🚀
