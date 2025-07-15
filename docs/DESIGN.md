# DESIGN.md

## ASGI Concurrency Model

### Event Loop vs Thread Pool

**Event Loop (Primary)**: All WebSocket operations run on the main event loop
- Message handling: `async def receive()` - pure async, no blocking I/O
- Heartbeat broadcasting: `asyncio.create_task(heartbeat())` - async task
- Connection management: Native async WebSocket operations

**Thread Pool (HTTP endpoints)**: Sync views automatically wrapped with `sync_to_async()`
- Health checks (`/healthz`, `/readyz`): Run in Django's thread pool
- Metrics endpoint (`/metrics`): Wrapped with `sync_to_async(thread_sensitive=True)`
- Django ASGI handler detects sync views and dispatches to threads

### Why Async for WebSockets vs Sync for HTTP

**WebSockets → Async** (Perfect fit):
- **Long-lived connections**: 1000 connections = 1 event loop vs 1000 threads (~8MB per thread means 8GB RAM)
- **Real-time broadcasting**: Concurrent heartbeat + message handling
- **High concurrency**: 5000+ connections with minimal memory overhead

**HTTP Endpoints → Sync** (Acceptable overhead):
- **Simple CRUD operations**: Single request-response cycle
- **Low frequency**: Health checks every 30s, metrics scraping every 15s
- **Thread pool overhead**: ~1ms penalty per request (acceptable for HTTP)

### Worker Configuration

```yaml
# docker/compose.yml
UVICORN_WORKERS=3          # Parallel Running Uvicorn Servers
UVICORN_LOOP=uvloop        # 2x faster than asyncio
UVICORN_LIMIT_CONCURRENCY=7000  # Per-worker connection limit
```

**Rationale**: 
- WebSocket workload is I/O-bound (waiting for client messages)
- 3 workers handle 21,000 concurrent connections (7k each) (Ideally!)
- uvloop provides C-based event loop performance
- No shared mutable state between workers (Redis sessions are worker-agnostic)


### Key Architecture Decisions

**Load Balancer**: **Traefik v3** instead of nginx for better load testing
- Dynamic configuration via environment variables and composer file
- Direct environment access via path prefixes
- Uses dynamic configuration with environment variable substitution instead of static nginx configuration:

```yaml
# traefik.yml template
services:
  active-app:
    loadBalancer:
      servers:
        - url: "http://${ACTIVE_ENV}:8000"
```

This enables zero-downtime switching by updating the `ACTIVE_ENV` variable and restarting only the load balancer.

**Application Server**: **Starlette + Django ASGI** hybrid
- Starlette provides lifespan management for startup/shutdown hooks
- Django handles HTTP endpoints and WebSocket routing
- Uvicorn with uvloop for high-performance async I/O

### Concurrency Pitfalls Avoided

1. **Shared session state**: Redis provides consistent sessions across workers and blue-green deployments
2. **Async-only operations**: No blocking calls in async context
3. **Graceful shutdown**: SIGTERM handling with lifespan hooks, allows graceful closure of active WebSocket connections
4. **Memory channel layer**: In-memory for simplicity (Redis layer available for scale)

### Reconnection Support

- Sessions stored in Redis with 1-hour TTL
- Clients reconnect with `?session_id=uuid` query parameter
- Message counters resume from last known state
- Works across blue-green deployments

