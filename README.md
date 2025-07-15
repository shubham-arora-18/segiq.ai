# SigIQ WebSocket Service

Production-ready Django WebSocket service with blue-green deployment and observability.

## Documentation

- [📋 System Design & Architecture](docs/DESIGN.md)
- [📊 Observability & Monitoring](docs/OBSERVABILITY.md)

## Quick Start

**Start full stack:**
```bash
make dev-up
```

**Run load test:**
```bash
make load-test
```

**Deploy blue→green:**
```bash
make dev-up
```

## Features

- **WebSocket Chat**: Message counter at `/ws/chat/` with reconnection support
- **Blue-Green Deployment**: Zero-downtime releases
- **Monitoring**: Prometheus metrics + Grafana dashboards
- **Load Testing**: 5000+ concurrent connections with Locust
- **Session Persistence**: Redis-based session storage for reconnection

## Endpoints

- `ws://localhost/ws/chat/` - WebSocket endpoint (supports `?session_id=uuid` for reconnection)
- `http://localhost/healthz` - Health check (liveness)
- `http://localhost/readyz` - Readiness check
- `http://localhost/metrics` - Prometheus metrics
- `http://localhost:3000` - Grafana (admin/admin)
- `http://localhost:9090` - Prometheus

## Architecture

```
traefik (load balancer)
├── app_blue:8000   (Django + Channels)
├── app_green:8000  (Django + Channels)
├── redis:6379      (session storage)
├── prometheus:9090 (metrics)
└── grafana:3000    (dashboards)
```

## Blue-Green Deployment

The `promote.sh` script automatically:
1. Builds & starts next environment
2. Runs health checks & smoke tests  
3. Switches traefik traffic
4. Retires old environment

## Monitoring

- **Metrics**: WebSocket connections, messages, errors, startup/shutdown time
- **Logs**: Structured JSON with request IDs
- **Alerts**: No active connections >60s
- **Dashboard**: Real-time connection graphs

## Load Testing

Supports 5000+ concurrent WebSocket connections:
- 80% active chatters (2-10s intervals)
- 20% lurkers (30-120s intervals)
- Realistic message patterns

## Reconnection Support

Clients can reconnect with previous session: `ws://localhost/ws/chat/?session_id=your-uuid`
Session data persists for 1 hour in Redis.