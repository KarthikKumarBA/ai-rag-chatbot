# Northwind Wiki (FastAPI + Jinja2 + SQLite)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    WIKI_DB_PATH=/app/data/wiki.db

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Package lives in /app/wiki so "wiki.app:app" imports work
COPY . /app/wiki

# uid 1000 matches runAsUser in the Helm chart
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/data \
    && chown -R appuser:appuser /app/data
USER 1000

EXPOSE 8088

HEALTHCHECK --interval=15s --timeout=3s --start-period=15s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8088/health')"

CMD ["uvicorn", "wiki.app:app", "--host", "0.0.0.0", "--port", "8088"]
