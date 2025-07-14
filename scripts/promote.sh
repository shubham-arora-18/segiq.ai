#!/bin/bash

# Blue-Green Deployment Promotion Script
# Usage: ./scripts/promote.sh

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_ROOT/docker"
HEALTH_CHECK_RETRIES=5
HEALTH_CHECK_INTERVAL=2
PORT="${PORT:-80}"
export PORT

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if Docker and Docker Compose are available
check_dependencies() {
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi

    if ! command -v docker-compose &> /dev/null; then
        log_error "Docker Compose is not installed or not in PATH"
        exit 1
    fi
}

# Get current active environment
get_current_active() {
    local active_env="${ACTIVE_ENV:-app_blue}"
    if [[ "$active_env" == *"blue"* ]]; then
        echo "blue"
    else
        echo "green"
    fi
}

# Get target environment (opposite of current)
get_target_env() {
    local current="$1"
    if [ "$current" = "blue" ]; then
        echo "green"
    else
        echo "blue"
    fi
}

# Health check function
health_check() {
    local env="$1"

    log_info "Performing health check for $env environment..."

    for i in $(seq 1 $HEALTH_CHECK_RETRIES); do
        if curl -f -s -H "Host: ${env}.localhost" "http://localhost:${PORT}/${env}/healthz" > /dev/null; then
            log_success "Health check passed for $env environment via nginx"
            return 0
        fi

        log_warning "Health check attempt $i/$HEALTH_CHECK_RETRIES failed, retrying in ${HEALTH_CHECK_INTERVAL}s..."
        sleep $HEALTH_CHECK_INTERVAL
    done

    log_error "Health check failed for $env environment after $HEALTH_CHECK_RETRIES attempts"
    return 1
}

# Smoke test function
smoke_test() {
    local target_env="$1"
    export TARGET_ENV="$target_env"

    log_info "Running smoke tests for $target_env environment..."

    if ! curl -f -s "http://localhost:${PORT}/${target_env}/readyz" > /dev/null; then
        log_error "Readiness endpoint smoke test failed via nginx."
        return 1
    fi

    pytest tests || {
        log_error "Smoke tests failed."
        return 1
    }

    log_success "Smoke tests passed for $target_env environment"
    return 0
}

# Update nginx configuration to switch traffic
switch_traffic() {
    local target_env="$1"

    log_info "Switching traffic to $target_env environment..."

    export ACTIVE_ENV="app_${target_env}"

    ACTIVE_ENV="app_${target_env}" PORT="${PORT}" docker-compose -f "$DOCKER_DIR/compose.yml" up -d nginx

    if [ $? -eq 0 ]; then
        log_success "Traffic switched to $target_env environment"
        echo "ACTIVE_ENV=app_${target_env}" > "$PROJECT_ROOT/.env"
    else
        log_error "Failed to restart nginx with new configuration"
        return 1
    fi
}

# Build and start target environment
deploy_target() {
    local target_env="$1"

    log_info "Building and starting $target_env environment..."

    export BUILD_VERSION="${BUILD_VERSION:-$(date +%Y%m%d-%H%M%S)}"

    if PORT="${PORT}" docker-compose -f "$DOCKER_DIR/compose.yml" up -d --build app_${target_env} nginx; then
        log_success "Successfully started $target_env environment"
    else
        log_error "Failed to start $target_env environment"
        return 1
    fi

    log_info "Waiting for $target_env environment to be ready..."
    sleep 2
}

# Retire old environment
retire_old() {
    local old_env="$1"

    log_info "Retiring $old_env environment..."

    docker-compose -f "$DOCKER_DIR/compose.yml" stop -t 10 app_${old_env}

    log_success "Successfully retired $old_env environment"
}

# Main deployment function
deploy() {
    local current_env
    local target_env

    log_info "Starting blue-green deployment..."

    # Load current ACTIVE_ENV from .env file if it exists
    if [ -f "$PROJECT_ROOT/.env" ]; then
        export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
    fi

    current_env=$(get_current_active)
    target_env=$(get_target_env "$current_env")

    log_info "Current active environment: $current_env"
    log_info "Target environment: $target_env"

    # Step 1: Build and start target environment
    if ! deploy_target "$target_env"; then
        log_error "Deployment failed at build/start stage"
        exit 1
    fi

    # Step 2: Health check
    if ! health_check "$target_env"; then
        log_error "Deployment failed at health check stage"
        retire_old "$target_env"
        exit 1
    fi

    # Step 3: Smoke tests
    if ! smoke_test "$target_env"; then
        log_error "Deployment failed at smoke test stage"
        retire_old "$target_env"
        exit 1
    fi

    # Step 4: Switch traffic
    if ! switch_traffic "$target_env"; then
        log_error "Deployment failed at traffic switch stage"
        retire_old "$target_env"
        exit 1
    fi

    # Step 5: Final verification
    sleep 5
    if ! health_check "$target_env"; then
        log_error "Post-switch health check failed"
        switch_traffic "$current_env"
        retire_old "$target_env"
        exit 1
    fi

    # Step 6: Retire old environment
    retire_old "$current_env"

    log_success "Blue-green deployment completed successfully!"
    log_success "Active environment: $target_env"
    log_info "Application available at: http://localhost:${PORT}"
}

# Status function
status() {
    if [ -f "$PROJECT_ROOT/.env" ]; then
        export $(grep -v '^#' "$PROJECT_ROOT/.env" | xargs)
    fi

    local current_env=$(get_current_active)
    echo "Current active environment: $current_env"
    echo "ACTIVE_ENV variable: ${ACTIVE_ENV:-app_blue}"

    for env in blue green; do
        local container_name="segiq_app_${env}"
        local status=$(docker inspect --format='{{.State.Status}}' "$container_name" 2>/dev/null || echo "not found")
        local health=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "no health check")
        echo "$env environment: $status ($health)"
    done
}

# Usage function
usage() {
    cat << EOF
Blue-Green Deployment Script

Usage: $0 [COMMAND] [OPTIONS]

Commands:
    deploy                    Automatically Deploys and Switches between Blue and Green Envs.
    status                    Show current deployment status
    help                      Show this help message

Examples:
    $0 deploy                Auto-deploy to next environment
    $0 status                Show current status

Environment Variables:
    BUILD_VERSION           Version tag for the build (default: timestamp)
    PORT                    Port for nginx (default: 80)

EOF
}

# Main script logic
main() {
    check_dependencies

    case "${1:-}" in
        deploy)
            deploy
            ;;
        status)
            status
            ;;
        help|--help|-h)
            usage
            ;;
        *)
            if [ $# -eq 0 ]; then
                deploy
            else
                log_error "Unknown command: ${1:-}"
                usage
                exit 1
            fi
            ;;
    esac
}

# Run main function with all arguments
main "$@"