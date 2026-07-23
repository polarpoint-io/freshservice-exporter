FROM python:3.12-slim

ARG VERSION=

WORKDIR /app

COPY pyproject.toml exporter.py client.py dora.py constants.py metrics.py emit.py ./

RUN pip install --no-cache-dir --upgrade pip && \
    if [ -n "$VERSION" ]; then \
      echo "Installing freshservice-exporter==${VERSION} from PyPI" && \
      pip install --no-cache-dir "freshservice-exporter==${VERSION}"; \
    else \
      echo "Installing from local source (snapshot build)" && \
      pip install --no-cache-dir -e .; \
    fi

ENV EXPORTER_PORT=9192 \
    SCRAPE_INTERVAL=300 \
    FRESHSERVICE_ENABLE_DORA=true \
    FRESHSERVICE_INCLUDE_STATS=true

EXPOSE 9192

CMD ["freshservice-exporter"]
