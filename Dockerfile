FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN useradd --create-home --uid 10001 abeer
COPY pyproject.toml README.md LICENSE ./
COPY abeer_inventory ./abeer_inventory
COPY wsgi.py ./
RUN pip install --upgrade pip && pip install '.[prod]'

RUN mkdir -p /app/instance && chown -R abeer:abeer /app
USER abeer

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "2", "--threads", "4", "--access-logfile", "-", "wsgi:app"]
