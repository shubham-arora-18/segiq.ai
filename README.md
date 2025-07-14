# SigIQ WebSocket Service

Production-ready Django WebSocket service with blue-green deployment and observability.

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

- **WebSocket Chat**: Message counter at `/ws/chat/`
- **Blue-Green Deployment**: Zero-downtime releases
- **Monitoring**: Prometheus metrics + Grafana dashboards
- **Load Testing**: 5000+ concurrent connections with Locust

## Endpoints

- `ws://localhost/ws/chat/` - WebSocket endpoint
- `http://localhost/healthz` - Health check
- `http://localhost/metrics` - Prometheus metrics
- `http://localhost:3000` - Grafana (admin/admin)
- `http://localhost:9090` - Prometheus

## Architecture

```
nginx (load balancer)
├── app_blue:8000   (Django + Channels)
├── app_green:8000  (Django + Channels)
├── prometheus:9090 (metrics)
└── grafana:3000    (dashboards)
```

## Blue-Green Deployment

The `promote.sh` script automatically:
1. Builds & starts next environment
2. Runs health checks & smoke tests  
3. Switches nginx traffic
4. Retires old environment

## Monitoring

- **Metrics**: WebSocket connections, messages, errors
- **Logs**: Structured JSON with request IDs
- **Alerts**: No active connections >60s
- **Dashboard**: Real-time connection graphs

## Load Testing

Supports 5000+ concurrent WebSocket connections:
- 80% active chatters (2-10s intervals)
- 20% lurkers (30-120s intervals)
- Realistic message patterns
