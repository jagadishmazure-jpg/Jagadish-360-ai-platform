# Gateway image: non-root, read-only friendly, no model weights or keys baked in.
FROM python:3.15-slim@sha256:94d3426f1def7db4a106a232ac121bfd975393e5dfd40a619b955fae45fe7913
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
