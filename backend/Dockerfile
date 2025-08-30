FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for sentence-transformers and health checks
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    rm -rf /root/.cache

# Pre-download the model during build to avoid runtime delays
RUN python -c "from sentence_transformers import SentenceTransformer; print('Downloading model...'); SentenceTransformer('all-MiniLM-L6-v2'); print('Model downloaded successfully')"

COPY . .

# Verify agentic.py presence
RUN ls -l /app/agentic.py

# Note: Fly.io handles health checks, so we don't need Docker health checks
# HEALTHCHECK --interval=30s --timeout=30s --start-period=120s --retries=3 \
#     CMD curl -f http://localhost:8080/health || exit 1

# Start the application directly - startup checks are handled in main.py
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
