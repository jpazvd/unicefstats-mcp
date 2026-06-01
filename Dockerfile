FROM python:3.12-slim

WORKDIR /app
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# Drop root before runtime. The MCP server only needs to bind a TCP port and
# read its own package files; no privileged operations.
RUN useradd --create-home --uid 10001 mcp
USER mcp

EXPOSE 8000

# SSE transport for remote deployment (Smithery, Railway, fly.io)
CMD ["unicefstats-mcp", "--transport", "sse", "--port", "8000"]
