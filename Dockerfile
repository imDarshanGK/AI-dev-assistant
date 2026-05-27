FROM python:3.12-slim

WORKDIR /app

# Install dependencies
COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/

# Copy frontend
COPY frontend/ ./frontend/

# Security fix: Create non-root user (fixes #389)
RUN addgroup --system appgroup && \
    adduser --system --ingroup appgroup appuser

# Transfer ownership of working directory to non-root user
RUN chown -R appuser:appgroup /app

# Switch to non-root user — never run containers as root in production
USER appuser

# Expose port
EXPOSE 8000

# Run
CMD ["uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]