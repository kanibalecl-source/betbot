FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN apt-get update \
    && apt-get install -y --no-install-recommends gosu \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 kanibal \
    && chown -R kanibal:kanibal /app \
    && install -m 0755 docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh

ENV BETTING_ENABLED=false \
    KANIBAL_REQUIRE_PERSISTENT_STORAGE=1 \
    BETBOT_SERVER_BACKUP_EMERGENCY_REUSE_HOURS=24

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8501')+'/_stcore/health', timeout=3)"

CMD ["sh", "start.sh"]
