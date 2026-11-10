FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    AERA_HOST="0.0.0.0" \
    PORT=8787

# Standard library only (requirements.txt explains the optional extras).
COPY . .
RUN mkdir -p /app/data

EXPOSE 8787
HEALTHCHECK --interval=30s --timeout=5s CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8787/health',timeout=4)"
CMD ["python", "api.py"]
