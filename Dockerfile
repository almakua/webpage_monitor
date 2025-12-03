FROM python:3.12-slim

LABEL org.opencontainers.image.description="Monitor per One Piece (TCB Scans) e WTC Terrain Map Pack"
LABEL org.opencontainers.image.source="https://github.com/USER/webpage-monitor"

# Installa ghostscript per compressione PDF
RUN apt-get update && \
    apt-get install -y --no-install-recommends ghostscript && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copia e installa dipendenze
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia script
COPY monitor.py .

# Directory per config (mount volume) - stato e download persistenti
VOLUME /config

# Graceful shutdown
STOPSIGNAL SIGTERM

# Default: modalità daemon (loop continuo)
ENTRYPOINT ["python", "-u", "monitor.py", "--config", "/config/config.yaml"]
CMD ["--daemon"]

