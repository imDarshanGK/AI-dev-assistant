# Setup Instructions

## 1. Clone the Repository

```bash
git clone https://github.com/your-username/AI-dev-assistant.git
cd AI-dev-assistant
```

---

## 2. Create a Virtual Environment

### Windows

```bash
python -m venv venv
venv\Scripts\activate
```

### Linux / Mac

```bash
python3 -m venv venv
source venv/bin/activate
```

---

## 3. Install Dependencies

```bash
cd backend
pip install -r requirements.txt
```

---

## 4. Run the Backend Server

```bash
uvicorn app.main:app --reload
```

Server will start at:

```txt
http://127.0.0.1:8000
```

---

## 5. Open the Frontend

Open:

```txt
http://127.0.0.1:8000/app/
```

---

## 6. Run Tests

```bash
pytest -q
```

---

## 7. Optional: Enable AI/LLM Support

Create a `.env` file inside `backend/`

```env
LLM_ENABLED=true
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o-mini
```

⚠️ Never commit `.env` files or API keys.