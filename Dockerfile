FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml exporter.py client.py dora.py constants.py metrics.py emit.py ./

RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -e .

ENV EXPORTER_PORT=9192 \
    SCRAPE_INTERVAL=300 \
    FRESHSERVICE_ENABLE_DORA=true \
    FRESHSERVICE_INCLUDE_STATS=true

EXPOSE 9192

CMD ["freshservice-exporter"]
