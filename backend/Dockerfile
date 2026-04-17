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

# start.sh is included in COPY . . above; re-copy to root and make executable
RUN chmod +x start.sh
CMD ["sh", "start.sh"]
