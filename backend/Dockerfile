FROM python:3.12-slim

WORKDIR /app

# Install system dependencies required by some Python packages
RUN apt-get update \
	&& apt-get install -y --no-install-recommends libmagic1 \
	&& rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy frontend
COPY frontend/ ./frontend/

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]