# A6 Draw System - Flask + htmx
#
#   docker build -t fallback-v2 .
#   docker run --rm -p 8000:8000 fallback-v2
#
# Draw state (including the uploaded participant file) is kept in memory,
# so this must run as ONE gunicorn worker. Threads share that memory and
# are fine. Do not raise --workers or run several replicas behind a load
# balancer: requests would land on a process that doesn't know the draw.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt gunicorn==23.0.0

COPY fallback ./fallback

RUN useradd --system --uid 10001 --no-create-home app
USER app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/static/css/app.css', timeout=2)"

CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--workers", "1", "--threads", "8", \
     "--timeout", "120", "--access-logfile", "-", "fallback:create_app()"]
