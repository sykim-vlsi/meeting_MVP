FROM node:22-bookworm-slim

ARG COPILOT_CLI_VERSION=1.0.80

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        python3 \
        python3-pip \
        python3-venv \
    && rm -rf /var/lib/apt/lists/*

RUN npm install --global "@github/copilot@${COPILOT_CLI_VERSION}" \
    && copilot --version

WORKDIR /app
COPY . .

RUN python3 -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --disable-pip-version-check .

ENV PATH="/opt/venv/bin:${PATH}" \
    GITHUB_COPILOT_CLI_PATH="/usr/local/bin/copilot" \
    PORT="8000" \
    PYTHONUNBUFFERED="1"

EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3)"

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]
