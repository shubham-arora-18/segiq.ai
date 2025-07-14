FROM python:3.11-slim as base

# Install system dependencies
RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Create django user for security
RUN useradd --create-home --shell /bin/bash django

# Set work directory
WORKDIR /workspace

# Install Python dependencies
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy application code
COPY app/ ./app/

# Change ownership to django user
RUN chown -R django:django /workspace

# Switch to non-root user
USER django

# Set environment variables for uvicorn configuration
ENV UVICORN_HOST=0.0.0.0 \
    UVICORN_PORT=8000 \
    UVICORN_LOOP=uvloop \
    UVICORN_LIMIT_CONCURRENCY=5000 \
    UVICORN_LOG_LEVEL=info \
    UVICORN_ACCESS_LOG=true \
    UVICORN_WORKERS=2

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=3s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/healthz || exit 1

# Command using environment variables
CMD exec uvicorn app.manage:application \
    --host $UVICORN_HOST \
    --port $UVICORN_PORT \
    --workers $UVICORN_WORKERS \
    --loop $UVICORN_LOOP \
    --limit-concurrency $UVICORN_LIMIT_CONCURRENCY \
    --log-level $UVICORN_LOG_LEVEL \
    $([ "$UVICORN_ACCESS_LOG" = "true" ] && echo "--access-log" || echo "")