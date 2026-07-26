FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY requirements.txt pyproject.toml README.md ./
COPY motion_bot ./motion_bot
COPY templates ./templates
COPY data ./data
COPY scripts ./scripts

RUN pip install --upgrade pip setuptools wheel \
 && pip install -e . \
 && mkdir -p /app/output /app/templates/library /app/templates/sample

# Platforms set PORT (default 8000)
ENV PORT=8000 \
    MOTION_BOT_HTTPS=1

EXPOSE 8000

CMD ["sh", "-c", "uvicorn motion_bot.web.app:app --host 0.0.0.0 --port ${PORT:-8000}"]
