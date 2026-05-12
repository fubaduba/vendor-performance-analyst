FROM python:3.12-slim

WORKDIR /app

COPY . user_agent/
WORKDIR /app/user_agent

RUN pip install --no-cache-dir --upgrade pip && \
    if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; fi

RUN useradd -m -u 1000 appuser

EXPOSE 8088

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8088/readiness')" || exit 1

USER appuser

CMD ["python", "main.py"]
