# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1
ENV PYTHONPATH=/app/src

WORKDIR /app

# System dependencies (minimal; extend as needed)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
 && rm -rf /var/lib/apt/lists/*

# Install Poetry and project dependencies (leverage Docker layer cache)
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir "poetry==1.8.3"

# Copy only pyproject first to cache dependency resolution
COPY pyproject.toml ./
RUN poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --no-root

# Copy project files
COPY . .

# Install the project itself (creates console scripts like 'doxie-mcp')
RUN poetry install --no-interaction --no-ansi

# Expose default app port
EXPOSE 8000

# Default command: run the Doxie MCP server (HTTP/SSE or stdio based on env)
CMD ["doxie-mcp"]
