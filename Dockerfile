# Gateway image: non-root, read-only friendly, no model weights or keys baked in.
FROM python:3.13-slim@sha256:d98cc29d3266e535dd9da1099688d9cb3ca4753813571e071763d17725460962
WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
COPY config ./config
COPY data ./data
COPY templates ./templates
RUN pip install --no-cache-dir . && useradd -u 10001 -m app
USER 10001
EXPOSE 8360
ENTRYPOINT ["p360", "serve", "--config", "/app/config/gateway.json"]
