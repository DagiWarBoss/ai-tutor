# Start from an official Python slim image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy only requirements.txt first to leverage Docker layer caching
COPY requirements.txt .

# Install dependencies (update pip, install from requirements, clean cache)
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt && \
    rm -rf /root/.cache

# Pre-download the embedding model during build to avoid runtime download issues
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy application files after dependencies to maximize cache usage
COPY . .

# Expose port 8080 (Fly.io default)
EXPOSE 8080

# Run the app with Uvicorn and bind to all interfaces and the right port
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]


