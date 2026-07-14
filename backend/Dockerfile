# Codnixy AI Trade — backend (FastAPI + scheduler)
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

# Baza SQLite trăiește pe volum (persistă între deploy-uri)
ENV DATABASE_URL=sqlite:////data/forex.db
VOLUME /data

EXPOSE 8000

# IMPORTANT: exact 1 worker — scheduler-ul, cache-urile și stream-ul WS
# rulează în proces; mai mulți workeri ar dubla semnalele și alertele.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
