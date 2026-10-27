# Digest-pinned so builds are reproducible: a floating `python:3.12-slim`
# silently pulls whatever micro-version was published last. This is the
# multi-arch manifest-list digest for python:3.12-slim (2026-07); bump
# deliberately, together with a rebuild + test run.
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Drop root before runtime. The MCP server only needs to bind a TCP port and
# read its own package files; no privileged operations.
RUN useradd --create-home --uid 10001 mcp
USER mcp

EXPOSE 8000

# Liveness: the SSE server must be accepting TCP connections on its port.
# Uses only the stdlib so it adds nothing to the image.
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD ["python", "-c", "import socket; socket.create_connection(('127.0.0.1', 8000), timeout=4).close()"]

# SSE transport for remote deployment (Smithery, Railway, fly.io)
CMD ["unicefstats-mcp", "--transport", "sse", "--port", "8000"]
