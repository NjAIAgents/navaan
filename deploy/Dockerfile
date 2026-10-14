# NAVAAN Studio server image (linux/arm64 on the Oracle VM). Build context: the repo root.
#   docker compose -f deploy/compose.yml build
# Nothing from songs/, navaan.config.json or any credential is baked in (constitution II, VI).
FROM node:22-bookworm-slim AS node

FROM python:3.13-slim-bookworm
ENV DEBIAN_FRONTEND=noninteractive PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1 NPM_CONFIG_UPDATE_NOTIFIER=false

# ffmpeg; fonts (Devanagari for Hindi lyrics); shared libraries headless Chrome needs (Remotion renders with it)
RUN apt-get update && apt-get install -y --no-install-recommends \
      ca-certificates curl ffmpeg tini fonts-noto-core fonts-noto-color-emoji libraqm0 \
      libnss3 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 libgbm1 libxkbcommon0 \
      libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libasound2 libpango-1.0-0 libcairo2 libxshmfence1 \
 && rm -rf /var/lib/apt/lists/*

# Node 22 from the official image (only the binary and npm, so Python's /usr/local stays intact)
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN npm install -g @anthropic-ai/claude-code \
 && pip install cryptography pillow requests google-api-python-client google-auth google-auth-oauthlib oci-cli \
 && python3 -c "import googleapiclient.discovery, google.oauth2.credentials, google.auth.transport.requests, google_auth_oauthlib.flow, PIL, cryptography" \
 && oci --version

RUN useradd --create-home --uid 10001 navaan && mkdir -p /app /opt/navaan-src && chown navaan:navaan /app
USER navaan
ENV HOME=/home/navaan

# Caption timing tools (vocal separation and Whisper small ONNX, about 700 MB from GitHub and PyPI), installed once at build time into
# ~/.cache/navaan, which is where setup_captions.py looks. With them present the `captions_setup` approval gate never fires on the server.
# Placed before the plugin COPY so a code change does not download them again (Docker keeps this layer).
COPY --chown=navaan:navaan plugins/navaan-studio/scripts/setup_captions.py /tmp/setup_captions.py
RUN python3 /tmp/setup_captions.py --yes && python3 /tmp/setup_captions.py --check && rm /tmp/setup_captions.py

COPY --chown=navaan:navaan .claude-plugin /opt/navaan-src/.claude-plugin
COPY --chown=navaan:navaan plugins /opt/navaan-src/plugins

# Install the plugin from the local marketplace so `claude -p "Use the <skill> skill"` resolves, then use that same copy
# for the portal (one copy of the code, same as the skills run). /opt/navaan-plugin points at the installed copy.
RUN claude plugin marketplace add /opt/navaan-src \
 && claude plugin install navaan-studio@navaan \
 && ln -s "$(ls -d $HOME/.claude/plugins/cache/navaan/navaan-studio/* | head -n1)" /home/navaan/plugin \
 && cd /home/navaan/plugin/remotion && npm ci && npx remotion browser ensure

COPY --chown=navaan:navaan deploy/entrypoint.sh deploy/vault_sync.py /home/navaan/
RUN chmod +x /home/navaan/entrypoint.sh

ENV NAVAAN_ROOT=/app NAVAAN_BIND=0.0.0.0 NAVAAN_HEADLESS=1
WORKDIR /app
EXPOSE 8765
ENTRYPOINT ["tini", "--", "/home/navaan/entrypoint.sh"]
