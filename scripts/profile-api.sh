#!/bin/bash
#
# Profile the API container using Py-Spy
# Usage: ./scripts/profile-api.sh [duration_seconds]
#
# Examples:
#   ./scripts/profile-api.sh 30          # Profile for 30 seconds
#   ./scripts/profile-api.sh 60         # Profile for 60 seconds
#   ./scripts/profile-api.sh            # Profile for 30 seconds (default)
#
# Output: Creates api-profile-<timestamp>.svg flame graph in current directory

set -e

DURATION=${1:-30}
OUTPUT_DIR="profiles"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_FILE="${OUTPUT_DIR}/api-profile-${TIMESTAMP}.svg"

echo "=== Py-Spy API Profiling ==="
echo "Duration: ${DURATION} seconds"
echo "Output: ${OUTPUT_FILE}"
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
    if $DOCKER_COMPOSE ps | grep -q "api.*Up"; then
        echo "Note: For py-spy to work, containers need SYS_PTRACE capability."
        echo "If you get 'Operation not permitted', restart with:"
        echo "  $DOCKER_COMPOSE -f docker-compose.yml -f docker-compose.profiling.yml up -d --build"
        echo ""
        PROFILING_OVERRIDE="-f docker-compose.yml -f docker-compose.profiling.yml"
    fi
fi

# Check if API container is running
if ! $DOCKER_COMPOSE $PROFILING_OVERRIDE ps | grep -q "api.*Up"; then
    echo "ERROR: API container is not running"
    echo "Start services with: $DOCKER_COMPOSE up -d"
    exit 1
fi

# Check if py-spy is installed in container
if ! $DOCKER_COMPOSE $PROFILING_OVERRIDE exec -T api which py-spy &> /dev/null; then
    echo "ERROR: py-spy is not installed in the API container"
    echo "Make sure 'py-spy' is in src/requirements.txt and rebuild:"
    echo "  $DOCKER_COMPOSE build api"
    exit 1
fi

# Create output directory
mkdir -p "${OUTPUT_DIR}"

# Get the PID of the API process in the container
# Uvicorn runs as the main process in the API container
PID=$($DOCKER_COMPOSE $PROFILING_OVERRIDE exec -T api pgrep -f "uvicorn")

if [ -z "$PID" ]; then
    echo "ERROR: Could not find uvicorn process in API container"
    echo "Check running processes: $DOCKER_COMPOSE $PROFILING_OVERRIDE exec api ps aux"
    exit 1
fi

echo "Found API process PID: $PID"
echo "Starting profiling..."
echo ""

# Profile the running process
# Using --native can cause issues with C extension symbols. Try without first.
# --pid tells py-spy to attach to an existing process
# We'll try native first, if it fails, retry without native
set +e
$DOCKER_COMPOSE $PROFILING_OVERRIDE exec -T api py-spy record \
    --pid "$PID" \
    --duration "$DURATION" \
    --output "/tmp/api-profile-${TIMESTAMP}.svg" \
    --native 2>&1
PROFILE_EXIT_CODE=$?
set -e

# If native profiling failed, retry without --native
if [ $PROFILE_EXIT_CODE -ne 0 ]; then
    echo "Native profiling failed (missing debug symbols?). Retrying without --native..."
    $DOCKER_COMPOSE $PROFILING_OVERRIDE exec -T api py-spy record \
        --pid "$PID" \
        --duration "$DURATION" \
        --output "/tmp/api-profile-${TIMESTAMP}.svg" \
        2>&1
    PROFILE_EXIT_CODE=$?
fi

if [ $PROFILE_EXIT_CODE -ne 0 ]; then
    echo "ERROR: Profiling failed"
    exit 1
fi

# Copy the profile from container to host
$DOCKER_COMPOSE $PROFILING_OVERRIDE exec -T api cat "/tmp/api-profile-${TIMESTAMP}.svg" > "${OUTPUT_FILE}"

echo ""
echo "Profile generated: ${OUTPUT_FILE}"
echo ""
echo "To view: open ${OUTPUT_FILE} in a browser"
echo "Or convert to other formats:"
echo "  $DOCKER_COMPOSE $PROFILING_OVERRIDE exec -T api py-spy dump -p $PID > api-profile.txt"
