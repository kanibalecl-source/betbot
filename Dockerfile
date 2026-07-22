FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN useradd --create-home --uid 10001 kanibal \
    && chown -R kanibal:kanibal /app

USER kanibal

ENV BETTING_ENABLED=false \
    KANIBAL_REQUIRE_PERSISTENT_STORAGE=1

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('PORT','8501')+'/_stcore/health', timeout=3)"

CMD ["sh", "start.sh"]
