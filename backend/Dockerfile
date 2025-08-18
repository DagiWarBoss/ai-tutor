FROM python:3.11-slim

WORKDIR /app

# Copy only needed files (not giant folders or hidden files)
COPY . /app

# Install the required packages (no CUDA, so lighter)
RUN pip install --upgrade pip && \
    pip install sentence-transformers fastapi uvicorn[standard] psycopg2-binary python-dotenv requests && \
    rm -rf /root/.cache

# Start your API (change main:app if needed)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
