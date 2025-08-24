FROM python:3.11-slim

WORKDIR /app

# Copy only requirements.txt first for better Docker cache usage
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    rm -rf /root/.cache

# Pre-download the SentenceTransformer model to avoid runtime download issues
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Copy the whole app code into the container
COPY . .

# Run the FastAPI app using Uvicorn on port 8080
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]





