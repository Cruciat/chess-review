# syntax=docker/dockerfile:1
#
# Immagine unica: FastAPI serve sia l'API sia la UI compilata, sulla stessa
# porta. Tre stadi, così nell'immagine finale non finiscono né Node né
# i sorgenti della UI né gli strumenti usati per scaricare Stockfish.

# ---- 1. Interfaccia ---------------------------------------------------------
FROM node:24-slim AS ui
WORKDIR /ui

# Prima solo i manifest: se non cambiano, Docker riusa lo strato di npm ci
# e le ricompilazioni successive saltano il download dei pacchetti.
COPY ui/package.json ui/package-lock.json ./
RUN npm ci

COPY ui/ ./
RUN npm run build

# ---- 2. Stockfish -----------------------------------------------------------
# Il binario ufficiale "universal" sceglie a runtime il codice più veloce
# per la CPU (AVX2, VNNI...). Quello di Debian è compilato per una CPU
# generica ed è sensibilmente più lento.
FROM debian:trixie-slim AS stockfish
ARG STOCKFISH_VERSION=sf_19

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /tmp/stockfish.tar.gz \
      "https://github.com/official-stockfish/Stockfish/releases/download/${STOCKFISH_VERSION}/stockfish-linux-x86-64-universal.tar.gz" \
 && tar -xzf /tmp/stockfish.tar.gz -C /tmp \
 && install -m 0755 /tmp/stockfish/stockfish-linux-x86-64-universal /stockfish

# ---- 3. Runtime -------------------------------------------------------------
FROM python:3.13-slim-trixie

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    STOCKFISH_PATH=/usr/local/bin/stockfish \
    CHESSREVIEW_UI_DIR=/app/ui

COPY pyproject.toml /tmp/build/
COPY src/ /tmp/build/src/
RUN pip install /tmp/build && rm -rf /tmp/build

COPY --from=stockfish /stockfish /usr/local/bin/stockfish
COPY --from=ui /ui/dist /app/ui

RUN useradd --system --no-create-home --uid 10001 chessreview
USER chessreview
WORKDIR /app

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4)"]

# Un solo worker, ed è voluto: partite scaricate, analisi in cache e lock
# del motore vivono nella memoria del processo. Con più worker ogni
# richiesta finirebbe su un processo diverso, con la sua cache e il suo
# Stockfish.
CMD ["uvicorn", "chessreview.api.app:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "5"]
