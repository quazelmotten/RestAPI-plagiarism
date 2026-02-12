#!/bin/bash
#
# Quick Commands Reference Script
# Usage: ./scripts/quick-cmd.sh [command]
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

show_help() {
    echo -e "${BLUE}Quick Commands for Plagiarism Detection System${NC}"
    echo ""
    echo "Usage: ./scripts/quick-cmd.sh [command]"
    echo ""
    echo "Commands:"
    echo "  setup       - Run full setup (./scripts/setup-complete.sh)"
    echo "  start       - Start all services"
    echo "  stop        - Stop all services"
    echo "  restart     - Restart all services"
    echo "  logs        - View all logs"
    echo "  logs-api    - View API logs only"
    echo "  logs-worker - View Worker logs only"
    echo "  test        - Run integration tests"
    echo "  health      - Check health of all services"
    echo "  clean       - Stop and remove all containers/volumes"
    echo "  build       - Rebuild all Docker images"
    echo "  shell-api   - Open shell in API container"
    echo "  shell-db    - Open shell in database container"
    echo "  db-cli      - Open PostgreSQL CLI"
    echo "  dev         - Start in development mode with hot reload"
    echo ""
}

cmd_setup() {
    ./scripts/setup-complete.sh
}

cmd_start() {
    echo -e "${BLUE}Starting all services...${NC}"
    docker-compose up -d
    echo -e "${GREEN}Services started!${NC}"
    echo -e "API: http://localhost:8000"
    echo -e "RabbitMQ: http://localhost:15672"
}

cmd_stop() {
    echo -e "${BLUE}Stopping all services...${NC}"
    docker-compose down
    echo -e "${GREEN}Services stopped!${NC}"
}

cmd_restart() {
    echo -e "${BLUE}Restarting all services...${NC}"
    docker-compose restart
    echo -e "${GREEN}Services restarted!${NC}"
}

cmd_logs() {
    docker-compose logs -f
}

cmd_logs_api() {
    docker-compose logs -f api
}

cmd_logs_worker() {
    docker-compose logs -f worker
}

cmd_test() {
    ./scripts/test-integration.sh
}

cmd_health() {
    echo -e "${BLUE}Checking service health...${NC}"
    echo ""
    
    # Check API
    if curl -s http://localhost:8000/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} API: Running"
    else
        echo -e "${RED}✗${NC} API: Not responding"
    fi
    
    # Check RabbitMQ
    if curl -s http://localhost:15672 > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} RabbitMQ: Running"
    else
        echo -e "${RED}✗${NC} RabbitMQ: Not responding"
    fi
    
    # Check Database
    if docker-compose exec -T postgres pg_isready > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC} Database: Running"
    else
        echo -e "${RED}✗${NC} Database: Not responding"
    fi
    
    # Check Worker
    if docker-compose ps | grep -q "worker.*Up"; then
        echo -e "${GREEN}✓${NC} Worker: Running"
    else
        echo -e "${RED}✗${NC} Worker: Not running"
    fi
}

cmd_clean() {
    echo -e "${YELLOW}WARNING: This will stop services and remove all data!${NC}"
    read -p "Are you sure? (y/N): " confirm
    if [[ $confirm =~ ^[Yy]$ ]]; then
        docker-compose down -v
        docker system prune -f
        echo -e "${GREEN}Cleanup complete!${NC}"
    else
        echo "Cancelled"
    fi
}

cmd_build() {
    echo -e "${BLUE}Rebuilding Docker images...${NC}"
    docker-compose build --no-cache
    echo -e "${GREEN}Build complete!${NC}"
}

cmd_shell_api() {
    docker-compose exec api /bin/bash
}

cmd_shell_db() {
    docker-compose exec postgres /bin/bash
}

cmd_db_cli() {
    docker-compose exec postgres psql -U plagiarism_user -d plagiarism_db
}

cmd_dev() {
    echo -e "${BLUE}Starting in development mode...${NC}"
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d
    echo -e "${GREEN}Development mode started!${NC}"
    echo -e "Hot reload enabled for API"
}

# Main command handler
case "${1:-help}" in
    setup)
        cmd_setup
        ;;
    start)
        cmd_start
        ;;
    stop)
        cmd_stop
        ;;
    restart)
        cmd_restart
        ;;
    logs)
        cmd_logs
        ;;
    logs-api)
        cmd_logs_api
        ;;
    logs-worker)
        cmd_logs_worker
        ;;
    test)
        cmd_test
        ;;
    health)
        cmd_health
        ;;
    clean)
        cmd_clean
        ;;
    build)
        cmd_build
        ;;
    shell-api)
        cmd_shell_api
        ;;
    shell-db)
        cmd_shell_db
        ;;
    db-cli)
        cmd_db_cli
        ;;
    dev)
        cmd_dev
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        echo -e "${RED}Unknown command: $1${NC}"
        show_help
        exit 1
        ;;
esac
