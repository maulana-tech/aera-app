FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV AERA_HOST="0.0.0.0"
ENV PORT=8787

# Install OS libraries for compilation and Postgres support if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt boto3

COPY . .

# Ensure data directory exists for SQLite fallback or persistence
RUN mkdir -p /app/data

EXPOSE 8787

CMD ["python", "api.py"]

