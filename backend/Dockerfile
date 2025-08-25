FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    rm -rf /root/.cache

RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

COPY . .

# Verify agentic.py presence
RUN ls -l /app/agentic.py

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
