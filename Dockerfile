FROM python:3.12-slim

WORKDIR /app
COPY . .
RUN pip install --no-cache-dir .

EXPOSE 8000

# SSE transport for remote deployment (Smithery, Railway, fly.io)
CMD ["unicefstats-mcp", "--transport", "sse", "--port", "8000"]
