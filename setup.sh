#!/bin/bash
#
# Production Setup Script for Plagiarism Detection API
# This script helps generate secure passwords and configure the application
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "=========================================="
echo "Plagiarism Detection API - Setup Script"
echo "=========================================="
echo

# Function to generate secure password
generate_password() {
    openssl rand -base64 32 | tr -d "=+/" | cut -c1-32
}

# Function to generate secret key
generate_secret() {
    openssl rand -hex 32
}

# Check if .env already exists
if [ -f .env ]; then
    echo -e "${YELLOW}⚠️  .env file already exists!${NC}"
    read -p "Do you want to overwrite it? (y/N): " overwrite
    if [[ ! $overwrite =~ ^[Yy]$ ]]; then
        echo "Setup cancelled."
        exit 0
    fi
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    echo -e "${GREEN}✓ Backup created${NC}"
fi

# Check if .env.example exists
if [ ! -f .env.example ]; then
    echo -e "${RED}❌ .env.example not found!${NC}"
    echo "Please ensure you're in the correct directory."
    exit 1
fi

echo -e "${GREEN}🔧 Generating secure configuration...${NC}"
echo

# Generate secure passwords and keys
DB_PASS=$(generate_password)
RMQ_PASS=$(generate_password)
SECRET_KEY=$(generate_secret)
ADMIN_PASS=$(generate_password)

echo "Creating .env file with secure passwords..."

# Create .env from template
cat > .env << EOF
# =============================================================================
# DATABASE CONFIGURATION
# =============================================================================
DB_HOST=postgres
DB_PORT=5432
DB_NAME=plagiarism_db
DB_USER=plagiarism_user
DB_PASS=${DB_PASS}

DB_POOL_SIZE=10
DB_MAX_OVERFLOW=20
DB_POOL_TIMEOUT=30

# =============================================================================
# RABBITMQ CONFIGURATION
# =============================================================================
RMQ_HOST=rabbitmq
RMQ_PORT=5672
RMQ_USER=plagiarism_mq_user
RMQ_PASS=${RMQ_PASS}

# Queue configuration
RMQ_QUEUE_EXCHANGE=plagiarism
RMQ_QUEUE_ROUTING_KEY=plagiarism
RMQ_QUEUE_NAME=plagiarism_queue
RMQ_QUEUE_DEAD_LETTER_EXCHANGE=plagiarism_dlx
RMQ_QUEUE_ROUTING_KEY_DEAD_LETTER=plagiarism.dead
RMQ_QUEUE_DEAD_LETTER_NAME=plagiarism_dead

# =============================================================================
# API CONFIGURATION
# =============================================================================
ENVIRONMENT=production
APP_NAME=Plagiarism Detection API
APP_VERSION=1.0.0
API_HOST=0.0.0.0
API_PORT=8000
API_WORKERS=4
CORS_ORIGINS=http://localhost:3000
SUBPATH=plagitype

# =============================================================================
# AUTHENTICATION CONFIGURATION
# =============================================================================
# JWT secret key - REQUIRED (auto-generated)
SECRET_KEY=${SECRET_KEY}

# Initial admin user (created automatically on first startup)
INITIAL_ADMIN_EMAIL=admin@example.com
INITIAL_ADMIN_PASSWORD=${ADMIN_PASS}

# Token expiration
ACCESS_TOKEN_EXPIRE_MINUTES=1440
REFRESH_TOKEN_EXPIRE_DAYS=7

# =============================================================================
# PLAGIARISM DETECTION SETTINGS
# =============================================================================
DEFAULT_PLAGIARISM_THRESHOLD=0.75
INVERTED_INDEX_MIN_OVERLAP_THRESHOLD=0.15
SUPPORTED_LANGUAGES=python,java,cpp,c,javascript,typescript,go,rust
MAX_FILE_SIZE=1048576
MAX_UPLOAD_REQUEST_SIZE=52428800
MAX_FILES_PER_BATCH=100

# =============================================================================
# STORAGE CONFIGURATION
# =============================================================================
STORAGE_LOCAL_PATH=/app/s3_storage
BUCKET_NAME=plagiarism-bucket

# =============================================================================
# RATE LIMITING
# =============================================================================
RATE_LIMIT_ENABLED=true
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_WINDOW=60

# =============================================================================
# WORKER CONFIGURATION
# =============================================================================
WORKER_CONCURRENCY=4
WORKER_PREFETCH_COUNT=1

# =============================================================================
# REDIS CONFIGURATION
# =============================================================================
REDIS_HOST=redis
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=
REDIS_USE_SSL=false
REDIS_TTL=86400
REDIS_FINGERPRINT_TTL=604800
REDIS_MAXMEMORY=512mb

# =============================================================================
# LOGGING
# =============================================================================
LOG_LEVEL=INFO
LOG_FORMAT=json

# =============================================================================
# MONITORING (Optional)
# =============================================================================
# SENTRY_DSN=
# METRICS_ENDPOINT=
ENABLE_PROFILING=false
EOF

echo -e "${GREEN}✓ .env file created successfully!${NC}"
echo

# Set proper permissions
chmod 600 .env
echo -e "${GREEN}✓ File permissions set (600)${NC}"
echo

echo "=========================================="
echo -e "${GREEN}✅ Setup Complete!${NC}"
echo "=========================================="
echo
echo "Your configuration has been generated with:"
echo "  • Strong database password (32 chars)"
echo "  • Strong RabbitMQ password (32 chars)"
echo "  • JWT secret key (64 chars hex)"
echo "  • Initial admin user credentials"
echo ""
echo "✅ INITIAL ADMIN CREDENTIALS:"
echo -e "  ${YELLOW}Email:${NC}    admin@example.com"
echo -e "  ${YELLOW}Password:${NC} ${ADMIN_PASS}"
echo ""
echo "⚠️  Save these credentials! You will need them to login."
echo ""
echo "The admin user will be created automatically on first startup."
echo
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Review the .env file and adjust settings if needed"
echo "  2. Update CORS_ORIGINS with your frontend domain"
echo "  3. CHANGE THE DEFAULT ADMIN EMAIL AND PASSWORD IN .env!"
echo "  4. Run: docker-compose up -d --build"
echo
echo -e "${RED}⚠️  IMPORTANT:${NC}"
echo "  • Keep your .env file secure and never commit it"
echo "  • It's already added to .gitignore"
echo "  • Make regular backups of your data volumes"
echo
