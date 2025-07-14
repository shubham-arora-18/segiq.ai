# DESIGN.md

## ASGI Concurrency Model

### Event Loop vs Thread Pool

**Event Loop (Primary)**: All WebSocket operations run on the main event loop
- Message handling: `async def receive()` - pure async, no blocking I/O
- Heartbeat broadcasting: `asyncio.create_task(heartbeat())` - async task
- Connection management: Native async WebSocket operations

**Thread Pool (Minimal)**: Only for potential blocking operations
- Session persistence: Currently in-memory (no thread pool needed)
- Future file I/O or database operations would use `sync_to_async()`

### Worker Configuration

```yaml
# docker/compose.yml
UVICORN_WORKERS=3          # Parallely Running Uvicorn Servers
UVICORN_LOOP=uvloop        # 2x faster than asyncio
UVICORN_LIMIT_CONCURRENCY=7000  # Per-worker connection limit
```

**Rationale**: 
- WebSocket workload is I/O-bound (waiting for client messages)
- 3 workers handle 21,000 concurrent connections (7k each) (Ideally!)
- uvloop provides C-based event loop performance
- No shared mutable state between workers (in-memory sessions are worker-local)

### Concurrency Pitfalls Avoided

1. **No shared state**: Each worker maintains its own `session_store`. But this can aslo be seen as a bug, if reconnection support is needed consistently. For that redis/memcache would be required as we have multiple uvicorn workers running in the background for an app's single docker container.
2. **Async-only operations**: No blocking calls in async context
3. **Graceful shutdown**: SIGTERM handling prevents connection drops
