# Use a PyTorch base image for fast setup—comes with torch pre-installed
FROM pytorch/pytorch:2.0.1-cuda11.7-cudnn8-runtime

WORKDIR /app

# Optional: If your code is in src or another folder, adjust accordingly
COPY . /app

# Install all dependencies in one go
RUN pip install --upgrade pip && \
    pip install sentence-transformers fastapi uvicorn[standard] psycopg2-binary python-dotenv requests

# Set environment variables if needed (optional)
# ENV SOME_ENV_VAR=value

# Command to run your backend (update main:app for your entrypoint)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
