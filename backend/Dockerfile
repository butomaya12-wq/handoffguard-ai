FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    HANDOFFGUARD_DATABASE_URL=sqlite:////data/handoffguard.db

WORKDIR /app

COPY backend/pyproject.toml ./pyproject.toml
COPY backend/app ./app

RUN pip install --no-cache-dir .

RUN groupadd --system handoffguard \
    && useradd --system --gid handoffguard handoffguard \
    && mkdir -p /data \
    && chown handoffguard:handoffguard /data

USER handoffguard

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
