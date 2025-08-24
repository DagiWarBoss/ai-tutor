FROM python:3.11-slim

WORKDIR /app

# Copy only requirements.txt first for better cache
COPY requirements.txt .

# Install dependencies
RUN pip install --upgrade pip && \
    pip install -r requirements.txt && \
    rm -rf /root/.cache

# Copy only the main application file(s)
COPY main.py .

# If you have other Python files or folders required, list them explicitly:
# COPY utils.py .
# COPY some_module/ /app/some_module/

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]




