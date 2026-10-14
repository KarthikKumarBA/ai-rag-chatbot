# RAG API (FastAPI + LangChain + Chroma). Documents come from the wiki REST API.
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# uid 1000 matches runAsUser in the Helm chart
RUN useradd -m -u 1000 appuser \
    && mkdir -p /app/vectorstore \
    && chown -R appuser:appuser /app
USER 1000

EXPOSE 8000

HEALTHCHECK --interval=15s --timeout=3s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health')"

CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]
