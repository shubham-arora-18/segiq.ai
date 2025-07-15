# DESIGN.md

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              CLIENT LAYER                              │
├─────────────────┬─────────────────┬─────────────────┬─────────────────────┤
│  WebSocket      │  WebSocket      │  WebSocket      │  Load Test Client   │
│  Client 1       │  Client 2       │  Client N       │  (Locust)          │
└─────────────────┴─────────────────┴─────────────────┴─────────────────────┘
                                    │
                        WebSocket connections (5000+)
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                         LOAD BALANCER LAYER                            │
│                     Traefik v3 (:80)                                   │
│                 Dynamic Blue-Green Routing                             │
└─────────────────────────────────────────────────────────────────────────┘
                                    │
                          ┌─────────┴──────────┐
                          ▼                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    BLUE-GREEN APPLICATION LAYER                        │
├──────────────────────────────────┬──────────────────────────────────────┤
│        BLUE ENVIRONMENT          │        GREEN ENVIRONMENT            │
│     app_blue:8000                │     app_green:8000                  │
│   Django + Channels              │   Django + Channels                 │
│   Uvicorn Workers: 2             │   Uvicorn Workers: 3                │
│   Concurrency: 7000              │   Concurrency: 7000                 │
└──────────────────────────────────┴──────────────────────────────────────┘
                                    │
                            Session persistence
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           STORAGE LAYER                                │
│                    Redis:6379                                          │
│                Session Storage (TTL: 1 hour)                           │
└─────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                         MONITORING STACK                               │
├──────────────────────────────────┬──────────────────────────────────────┤
│        Prometheus:9090           │        Grafana:3000                 │
│    Metrics Collection            │       Dashboards                    │
│   (15s scrape interval)          │      (5s refresh)                   │
└──────────────────────────────────┴──────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────┐
│                      DEPLOYMENT & CI LAYER                             │
├───────────────┬─────────────────┬───────────────────────────────────────┤
│ GitHub Actions│   promote.sh    │         monitor.sh                    │
│  CI Pipeline  │ Blue-Green      │      Ops Monitoring                   │
│               │   Script        │                                       │
└───────────────┴─────────────────┴───────────────────────────────────────┘
```

### System Flow:
1. **Client connections** → Traefik load balancer
2. **Active environment routing** → Blue OR Green (based on ACTIVE_ENV)
3. **Session persistence** → Redis storage for reconnection support
4. **Metrics collection** → Prometheus scrapes both environments
5. **Deployment automation** → promote.sh handles blue-green switching

## Data Flow Architecture

```
WebSocket Connection & Message Flow:

Client                Traefik              App              Redis           Prometheus
  │                     │                   │                │                  │
  │ ws://localhost/     │                   │                │                  │
  │ ws/chat/?session_id │                   │                │                  │
  ├────────────────────▶│                   │                │                  │
  │                     │ Route to active   │                │                  │
  │                     ├──────────────────▶│                │                  │
  │                     │                   │ GET session:   │                  │
  │                     │                   │ uuid:count     │                  │
  │                     │                   ├───────────────▶│                  │
  │                     │                   │ ◀──────────────┤                  │
  │                     │                   │ Return count   │                  │
  │                     │                   ├────────────────┼─────────────────▶│
  │                     │                   │                │ Increment        │
  │                     │                   │                │ active_connections│
  │ ◀───────────────────┼───────────────────┤                │                  │
  │ Connection          │                   │                │                  │
  │ established         │                   │                │                  │
  │                     │                   │                │                  │
  │ Text message        │                   │                │                  │
  ├────────────────────▶│──────────────────▶│                │                  │
  │                     │                   │ Increment      │                  │
  │                     │                   │ counter        │                  │
  │                     │                   ├───────────────▶│                  │
  │                     │                   │ SETEX session  │                  │
  │                     │                   │ TTL=3600       │                  │
  │                     │                   ├────────────────┼─────────────────▶│
  │                     │                   │                │ Increment        │
  │                     │                   │                │ messages_total   │
  │ ◀───────────────────┼───────────────────┤                │                  │
  │ {"count": n}        │                   │                │                  │
  │                     │                   │                │                  │
  │ Every 30s:          │                   │                │                  │
  │ ◀───────────────────┼───────────────────┤                │                  │
  │ {"type":"heartbeat",│                   │ Broadcast      │                  │
  │  "ts":"ISO"}        │                   │ task           │                  │
  │                     │                   │                │                  │
  │ Disconnect/SIGTERM  │                   │                │                  │
  │ ◀───────────────────┼───────────────────┤                │                  │
  │ Close code 1001     │                   ├────────────────┼─────────────────▶│
  │                     │                   │                │ Decrement        │
  │                     │                   │                │ active_connections│
```

## Blue-Green Deployment Flow

```
                    Blue-Green Deployment Process

    [Start Deployment]
            │
            ▼
    {Current = Blue?}
       ┌────┴────┐
       │ Yes     │ No
       ▼         ▼
  [Deploy Green] [Deploy Blue]
       │         │
       ▼         ▼
  [Health Check] [Health Check]
    Green         Blue
       │         │
       ▼         ▼
  [Smoke Test]  [Smoke Test]
    Green         Blue
       │         │
       ▼         ▼
  [Switch to    [Switch to
   Green]        Blue]
       │         │
       ▼         ▼
  [Retire Blue] [Retire Green]
       │         │
       └────┬────┘
            ▼
      [Complete]

    Rollback on Failure:
    Health Check Fail ──┐
    Smoke Test Fail ────┼──▶ [Retire Failed Env]
    Switch Fail ────────┘         │
                                  ▼
                           [Rollback Complete]
```

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

