FROM python:3.12-slim

WORKDIR /app

# System deps: asyncpg (libpq), pdfplumber (libffi), python-docx
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# Make both entry points executable
RUN chmod +x start.sh worker.sh

# WORKER_MODE=1 → run Celery worker; anything else → run API server
CMD ["sh", "-c", "if [ \"$WORKER_MODE\" = '1' ]; then sh worker.sh; else sh start.sh; fi"]
