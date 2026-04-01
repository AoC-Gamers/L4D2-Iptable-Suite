FROM python:3.12-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends bash curl ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY geoip-updater/run-update.sh /app/run-update.sh

RUN chmod +x /app/run-update.sh

ENTRYPOINT ["/app/run-update.sh"]