# Makefile for SigIQ Django WebSocket Application

.PHONY: help dev-up dev-down build deploy rollback status logs test load-test clean

# Default target
help:
	@echo "SigIQ Django WebSocket Application"
	@echo ""
	@echo "Available targets:"
	@echo "  dev-up      Deploy to next environment (blue-green)"
	@echo "  status      Show deployment status"
	@echo "  logs        Show application logs"
	@echo "  load-test   Run load tests (requires Locust)"
	@echo "  clean       Clean up containers and images"

# Blue-green deployment
dev-up:
	@echo "🚀 Starting blue-green deployment..."
	chmod +x scripts/promote.sh
	./scripts/promote.sh deploy
	@echo "✅ Deployment completed"

status:
	@echo "📊 Deployment status:"
	chmod +x scripts/promote.sh
	./scripts/promote.sh status

# Logs
logs:
	@echo "📋 Application logs:"
	docker-compose -f docker/compose.yml logs -f --tail=100

logs-blue:
	@echo "📋 Blue environment logs:"
	docker-compose -f docker/compose.yml logs -f --tail=100 app_blue

logs-green:
	@echo "📋 Green environment logs:"
	docker-compose -f docker/compose.yml logs -f --tail=100 app_green

# Load testing (requires Locust to be set up)
load-test:
	@echo "⚡ Running load tests..."
	@if command -v locust >/dev/null 2>&1; then \
		echo "Starting Locust load test..."; \
		locust -f tests/locustfile.py --users=40000 --spawn-rate=500 --run-time=300s --headless --html=tests/load_test_report.html; \
	else \
		echo "❌ Locust not found. Install with: pip install locust"; \
		echo "Then run: locust -f tests/locustfile.py --host=http://localhost"; \
	fi

# Monitoring
monitor:
	@echo "📊 Starting monitoring..."
	chmod +x scripts/monitor.sh
	./scripts/monitor.sh

# Cleanup
clean:
	@echo "🧹 Cleaning up..."
	docker-compose -f docker/compose.yml down --remove-orphans
	docker system prune -f
	@echo "✅ Cleanup completed"