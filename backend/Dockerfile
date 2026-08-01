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

# Container-level health check. Docker / Compose use this; Kubernetes ignores
# it in favour of the manifest probes that hit /healthz/live and /healthz/ready
# directly.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; \
sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/healthz/live', timeout=4).status==200 else 1)" \
    || exit 1

# Run
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]
