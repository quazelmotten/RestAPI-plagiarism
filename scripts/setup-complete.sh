#!/bin/bash
#
# One-Command Setup Script for Plagiarism Detection System
# Usage: ./setup-complete.sh [environment]
# Environments: dev, test, prod (default: dev)
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

ENVIRONMENT="${1:-dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  Plagiarism Detection System Setup${NC}"
echo -e "${BLUE}  Environment: ${ENVIRONMENT}${NC}"
echo -e "${BLUE}==========================================${NC}"
echo

# Function to print status
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

# Function to check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to wait for service
wait_for_service() {
    local url=$1
    local service_name=$2
    local max_attempts=${3:-30}
    local attempt=1
    
    print_status "Waiting for $service_name to be ready..."
    while [ $attempt -le $max_attempts ]; do
        if curl -s "$url" > /dev/null 2>&1; then
            print_success "$service_name is ready!"
            return 0
        fi
        echo -n "."
        sleep 2
        attempt=$((attempt + 1))
    done
    print_error "$service_name failed to start after $max_attempts attempts"
    return 1
}

# Step 1: Check prerequisites
print_status "Checking prerequisites..."

if ! command_exists docker; then
    print_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command_exists docker-compose; then
    print_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

print_success "Docker and Docker Compose are installed"

# Step 2: Generate environment file
print_status "Setting up environment configuration..."

if [ -f .env ] && [ "$ENVIRONMENT" != "test" ]; then
    print_warning ".env file already exists"
    read -p "Do you want to recreate it? (y/N): " recreate
    if [[ ! $recreate =~ ^[Yy]$ ]]; then
        print_status "Using existing .env file"
    else
        cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
        print_status "Backup created: .env.backup.$(date +%Y%m%d_%H%M%S)"
        ./setup.sh
    fi
else
    if [ -f setup.sh ]; then
        ./setup.sh
    else
        print_warning "setup.sh not found, creating minimal .env"
        cat > .env << EOF
DB_HOST=postgres
DB_PORT=5432
DB_NAME=plagiarism_db
DB_USER=plagiarism_user
DB_PASS=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
RMQ_HOST=rabbitmq
RMQ_PORT=5672
RMQ_USER=plagiarism_mq_user
RMQ_PASS=$(openssl rand -base64 32 | tr -d "=+/" | cut -c1-32)
SECRET_KEY=$(openssl rand -base64 48)
ENVIRONMENT=${ENVIRONMENT}
API_HOST=0.0.0.0
API_PORT=8000
CORS_ORIGINS=http://localhost:3000
LOG_LEVEL=INFO
EOF
    fi
fi

print_success "Environment configuration ready"

# Step 3: Create necessary directories
print_status "Creating necessary directories..."
mkdir -p frontend/dist
mkdir -p uploads
mkdir -p s3_storage
print_success "Directories created"

# Step 4: Build and start services
print_status "Building Docker images (this may take a few minutes)..."

if [ "$ENVIRONMENT" = "dev" ]; then
    # Development mode - mount source code for hot reload
    print_status "Starting in DEVELOPMENT mode with hot reload..."
    docker-compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build
elif [ "$ENVIRONMENT" = "test" ]; then
    # Test mode - run tests and exit
    print_status "Starting in TEST mode..."
    docker-compose -f docker-compose.yml up -d --build
else
    # Production mode
    print_status "Starting in PRODUCTION mode..."
    docker-compose up -d --build
fi

print_success "Services built and started"

# Step 5: Wait for services to be healthy
print_status "Waiting for services to become healthy..."

# Wait for database
wait_for_service "http://localhost:8000/health" "API Server" 30 || exit 1
wait_for_service "http://localhost:15672" "RabbitMQ Management" 30 || exit 1

print_success "All services are healthy"

# Step 6: Run database migrations if needed
print_status "Checking database migrations..."
docker-compose exec -T api python -c "from database import init_db; init_db()" 2>/dev/null || print_warning "Could not run migrations automatically"

# Step 7: Display service information
echo
print_success "Setup Complete! 🎉"
echo
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  Service URLs:${NC}"
echo -e "${BLUE}==========================================${NC}"
echo -e "  API Server:     ${GREEN}http://localhost:8000${NC}"
echo -e "  API Docs:       ${GREEN}http://localhost:8000/docs${NC}"
echo -e "  RabbitMQ Mgmt:  ${GREEN}http://localhost:15672${NC}"
echo -e "  Database:       ${GREEN}localhost:5432${NC}"
echo
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  Useful Commands:${NC}"
echo -e "${BLUE}==========================================${NC}"
echo -e "  View logs:      ${YELLOW}docker-compose logs -f${NC}"
echo -e "  Stop services:  ${YELLOW}docker-compose down${NC}"
echo -e "  Restart:        ${YELLOW}docker-compose restart${NC}"
echo -e "  Run tests:      ${YELLOW}./scripts/test-integration.sh${NC}"
echo

if [ "$ENVIRONMENT" = "dev" ]; then
    echo -e "${YELLOW}Development mode:${NC}"
    echo -e "  Frontend dev:   ${YELLOW}cd frontend && npm run dev${NC}"
    echo -e "  Hot reload:     ${GREEN}Enabled for API${NC}"
fi

echo -e "${BLUE}==========================================${NC}"

# Run health check
echo
print_status "Running quick health check..."
if curl -s http://localhost:8000/health | grep -q "healthy\|ok"; then
    print_success "Health check passed!"
else
    print_warning "Health check returned unexpected response"
fi
