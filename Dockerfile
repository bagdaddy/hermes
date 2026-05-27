FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    chromium \
    chromium-driver \
    ca-certificates \
    fonts-liberation \
    libglib2.0-0 \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libasound2 \
    && rm -rf /var/lib/apt/lists/*

# Node 20 (needed by Hermes' browser toolset — it shells out via `npx agent-browser`)
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir hermes-agent aiohttp websockets

# Hermes' browser toolset uses `agent-browser`. Install it globally + pull its bundled deps.
RUN npm install -g agent-browser \
    && agent-browser install --with-deps || echo "[warn] agent-browser install returned non-zero; continuing"

RUN mkdir -p /root/.hermes/skills /crawls

COPY config/hermes.yaml /root/.hermes/config.yaml
COPY skills/ /root/.hermes/skills/
COPY scripts/entrypoint.sh /entrypoint.sh
COPY scripts/proxy.py /proxy.py
RUN chmod +x /entrypoint.sh

EXPOSE 8644

ENTRYPOINT ["/entrypoint.sh"]
