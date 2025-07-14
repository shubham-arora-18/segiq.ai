# OBSERVABILITY.md

## Metrics

**Prometheus endpoint**: `/metrics`

### Key Metrics (Includes aggregation in case of multiple workers)
- `websocket_active_connections` - Current WebSocket connections
- `websocket_messages_total` - Total messages processed
- `websocket_errors_total` - WebSocket error count
- `sigiq_startup_time_seconds` - Application startup time
- `sigiq_shutdown_time_seconds` - Graceful shutdown time

### Collection
- **Scrape interval**: 15s
- **Retention**: Default Prometheus (15 days)
- **Targets**: `app_blue:8000`, `app_green:8000`

## Logging

**Format**: Structured JSON with `structlog`

### Log Fields Example
```json
{
  "event": "WebSocket connected",
  "session_id": "uuid",
  "request_id": "uuid", 
  "timestamp": "2024-01-01T12:00:00Z",
  "level": "info",
  "filename": "consumers.py",
  "lineno": 42
}
```

### Key Events
- WebSocket connect/disconnect
- Message processing
- Heartbeat broadcasts  
- Errors and exceptions
- Graceful shutdown

## Health Checks

### Endpoints
- `/healthz` - Liveness probe (always returns 200)
- `/readyz` - Readiness probe (503 during shutdown)

### Monitoring
- **Interval**: 30s health checks in Docker
- **Timeout**: 10s
- **Retries**: 3 failed attempts before unhealthy

## Alerts

### Prometheus Rules (`alerts.yml`)
```yaml
- alert: NoActiveWebSocketConnections
  expr: sum(websocket_active_connections) == 0
  for: 60s
  labels:
    severity: warning
```

### Alert Manager
- **Trigger**: No active connections >60s
- **Severity**: Warning level
- **Action**: Investigation required

## Dashboards

**Grafana**: `http://localhost:3000` (admin/admin)

### Panels
1. **Active Connections** - Real-time gauge
2. **Total Messages** - Cumulative counter  
3. **Error Count** - Error rate tracking
4. **Connection Timeline** - Historical graph

### Refresh
- **Rate**: 5s auto-refresh
- **Range**: Last 1 hour default

## Monitoring Script

`scripts/monitor.sh` provides:
- Tail logs for ERROR entries
- Top 5 metrics every 3s
- Real-time operational view
