#!/bin/bash
#
# Real-time profiling of API or worker using Py-Spy top
# Usage: ./scripts/profile-top.sh [service]
#
# Examples:
#   ./scripts/profile-top.sh api          # Monitor API in real-time
#   ./scripts/profile-top.sh worker      # Monitor worker in real-time
#
# Press Ctrl+C to stop

set -e

SERVICE=${1:-api}

echo "=== Py-Spy Real-time Profiling ==="
echo "Service: ${SERVICE}"
echo "Press Ctrl+C to stop"
echo ""

# Determine docker compose command (v1 vs v2)
if command -v docker-compose &> /dev/null; then
    DOCKER_COMPOSE="docker-compose"
elif command -v docker &> /dev/null && docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    echo "ERROR: Neither docker-compose nor docker compose is available"
    exit 1
fi

# Check if profiling override exists
PROFILING_OVERRIDE=""
if [ -f "docker-compose.profiling.yml" ]; then
    # Check if containers are running with profiling capabilities
    if $DOCKER_COMPOSE ps | grep -q "${SERVICE}.*Up"; then
        echo "Note: For py-spy to work, containers need SYS_PTRACE capability."
        echo "If you get 'Operation not permitted', restart with:"
        echo "  $DOCKER_COMPOSE -f docker-compose.yml -f docker-compose.profiling.yml up -d --build"
        echo ""
        PROFILING_OVERRIDE="-f docker-compose.yml -f docker-compose.profiling.yml"
    fi
fi

# Check if service container is running
if ! $DOCKER_COMPOSE $PROFILING_OVERRIDE ps | grep -q "${SERVICE}.*Up"; then
    echo "ERROR: ${SERVICE} container is not running"
    echo "Start services with: $DOCKER_COMPOSE up -d"
    exit 1
fi

# Check if py-spy is installed in container
if ! $DOCKER_COMPOSE $PROFILING_OVERRIDE exec -T ${SERVICE} which py-spy &> /dev/null; then
    echo "ERROR: py-spy is not installed in the ${SERVICE} container"
    echo "Make sure 'py-spy' is in requirements.txt and rebuild:"
    echo "  $DOCKER_COMPOSE build ${SERVICE}"
    exit 1
fi

# Get the PID of the process
if [ "$SERVICE" = "api" ]; then
    PID=$($DOCKER_COMPOSE $PROFILING_OVERRIDE exec -T api pgrep -f "uvicorn")
    PROCESS_NAME="uvicorn"
elif [ "$SERVICE" = "worker" ]; then
    PID=$($DOCKER_COMPOSE $PROFILING_OVERRIDE exec -T worker pgrep -f "worker.py")
    PROCESS_NAME="worker.py"
else
    echo "ERROR: Unknown service. Use 'api' or 'worker'"
    exit 1
fi

if [ -z "$PID" ]; then
    echo "ERROR: Could not find ${PROCESS_NAME} process in ${SERVICE} container"
    echo "Check running processes: $DOCKER_COMPOSE $PROFILING_OVERRIDE exec ${SERVICE} ps aux"
    exit 1
fi

echo "Found ${SERVICE} process PID: $PID"
echo "Starting real-time profiling..."
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Run py-spy top to monitor in real-time
$DOCKER_COMPOSE $PROFILING_OVERRIDE exec -T ${SERVICE} py-spy top --pid "$PID"
