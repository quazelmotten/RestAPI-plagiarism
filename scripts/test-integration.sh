#!/bin/bash
#
# Integration Test Script
# Tests the entire stack: API, Worker, Database, RabbitMQ, Frontend
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

API_URL="${API_URL:-http://localhost:8000}"
FAILED=0
PASSED=0

# Test result tracking
test_start() {
    echo -e "${BLUE}[TEST]${NC} $1..."
}

test_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    PASSED=$((PASSED + 1))
}

test_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    FAILED=$((FAILED + 1))
}

# Test API health endpoint
test_api_health() {
    test_start "API Health Endpoint"
    if curl -s "${API_URL}/health" | grep -q "healthy\|ok"; then
        test_pass "API Health Endpoint"
    else
        test_fail "API Health Endpoint"
    fi
}

# Test API docs endpoint
test_api_docs() {
    test_start "API Documentation"
    if curl -s "${API_URL}/docs" | grep -q "swagger\|openapi"; then
        test_pass "API Documentation"
    else
        test_fail "API Documentation"
    fi
}

# Test API version endpoint
test_api_version() {
    test_start "API Version"
    response=$(curl -s "${API_URL}/version" 2>/dev/null || echo "")
    if [ -n "$response" ]; then
        test_pass "API Version"
    else
        test_fail "API Version"
    fi
}

# Test user registration
test_user_registration() {
    test_start "User Registration"
    response=$(curl -s -X POST "${API_URL}/auth/register" \
        -H "Content-Type: application/json" \
        -d '{
            "username": "testuser_'$(date +%s)'",
            "email": "test_'$(date +%s)'@example.com",
            "password": "TestPassword123!"
        }' 2>/dev/null)
    
    if echo "$response" | grep -q "id\|user_id\|username"; then
        test_pass "User Registration"
        echo "$response" | grep -o '"id":[0-9]*' | cut -d: -f2 > /tmp/test_user_id
    else
        test_fail "User Registration"
    fi
}

# Test user login
test_user_login() {
    test_start "User Login"
    response=$(curl -s -X POST "${API_URL}/auth/login" \
        -H "Content-Type: application/json" \
        -d '{
            "username": "testuser_'$(date +%s)'",
            "email": "test_'$(date +%s)'@example.com",
            "password": "TestPassword123!"
        }' 2>/dev/null || echo "")
    
    if echo "$response" | grep -q "access_token\|token"; then
        test_pass "User Login"
        echo "$response" | grep -o '"access_token":"[^"]*"' | cut -d'"' -f4 > /tmp/test_token
    else
        test_fail "User Login"
    fi
}

# Test plagiarism check endpoint (includes file upload)
test_plagiarism_check() {
    test_start "Plagiarism Check with File Upload"
    
    # Create two test files
    echo "def hello():" > /tmp/test_file1.py
    echo "    print('Hello World')" >> /tmp/test_file1.py
    
    echo "def hello():" > /tmp/test_file2.py
    echo "    print('Hello World')" >> /tmp/test_file2.py
    
    response=$(curl -s -X POST "${API_URL}/plagiarism/check" \
        -F "files=@/tmp/test_file1.py" \
        -F "files=@/tmp/test_file2.py" \
        -F "language=python" 2>/dev/null || echo "")
    
    if echo "$response" | grep -q "task_id\|status"; then
        test_pass "Plagiarism Check with File Upload"
        echo "$response" | grep -o '"task_id":"[^"]*"' | cut -d'"' -f4 > /tmp/test_task_id
    else
        test_fail "Plagiarism Check with File Upload"
        echo "Response: $response"
    fi
}

# Test task status endpoint
test_task_status() {
    test_start "Task Status"
    
    if [ ! -f /tmp/test_task_id ]; then
        test_fail "Task Status (no task ID)"
        return
    fi
    
    task_id=$(cat /tmp/test_task_id)
    response=$(curl -s "${API_URL}/plagiarism/${task_id}" 2>/dev/null || echo "")
    
    if echo "$response" | grep -q "status"; then
        test_pass "Task Status"
    else
        test_fail "Task Status"
        echo "Response: $response"
    fi
}

# Test get tasks list
test_list_tasks() {
    test_start "List Tasks"
    
    response=$(curl -s "${API_URL}/plagiarism/tasks" \
        -H "Authorization: Bearer $(cat /tmp/test_token 2>/dev/null || echo '')" 2>/dev/null || echo "")
    
    if [ -n "$response" ]; then
        test_pass "List Tasks"
    else
        test_fail "List Tasks"
    fi
}

# Test database connectivity
test_database() {
    test_start "Database Connectivity"
    if docker-compose exec -T postgres pg_isready -U plagiarism_user -d plagiarism_db > /dev/null 2>&1; then
        test_pass "Database Connectivity"
    else
        test_fail "Database Connectivity"
    fi
}

# Test RabbitMQ
test_rabbitmq() {
    test_start "RabbitMQ Connectivity"
    if curl -s -u "plagiarism_mq_user:password" http://localhost:15672/api/overview > /dev/null 2>&1; then
        test_pass "RabbitMQ Connectivity"
    else
        test_fail "RabbitMQ Connectivity"
    fi
}

# Test frontend serving
test_frontend() {
    test_start "Frontend Serving"
    response=$(curl -s "${API_URL}" 2>/dev/null || echo "")
    if echo "$response" | grep -q "html\|<!DOCTYPE\|<div"; then
        test_pass "Frontend Serving"
    else
        test_fail "Frontend Serving"
    fi
}

# Test worker status
test_worker() {
    test_start "Worker Service"
    if docker-compose ps | grep -q "worker.*Up"; then
        test_pass "Worker Service"
    else
        test_fail "Worker Service"
    fi
}

# Cleanup function
cleanup() {
    rm -f /tmp/test_*.py /tmp/test_token /tmp/test_user_id /tmp/test_file_id /tmp/test_task_id
}

# Main test execution
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  Running Integration Tests${NC}"
echo -e "${BLUE}  API URL: ${API_URL}${NC}"
echo -e "${BLUE}==========================================${NC}"
echo

# Wait for API to be ready
echo -e "${YELLOW}Waiting for API to be ready...${NC}"
for i in {1..30}; do
    if curl -s "${API_URL}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}API is ready!${NC}"
        break
    fi
    echo -n "."
    sleep 2
    if [ $i -eq 30 ]; then
        echo -e "\n${RED}API failed to start${NC}"
        exit 1
    fi
done
echo

# Run infrastructure tests
echo -e "${BLUE}--- Infrastructure Tests ---${NC}"
test_api_health
test_database
test_rabbitmq
test_worker

# Run API endpoint tests
echo
echo -e "${BLUE}--- API Endpoint Tests ---${NC}"
test_api_docs
test_api_version
test_frontend

# Run functional tests
echo
echo -e "${BLUE}--- Functional Tests ---${NC}"
test_user_registration
test_user_login
test_plagiarism_check
test_task_status
test_list_tasks

# Print summary
echo
echo -e "${BLUE}==========================================${NC}"
echo -e "${BLUE}  Test Summary${NC}"
echo -e "${BLUE}==========================================${NC}"
echo -e "${GREEN}Passed: ${PASSED}${NC}"
echo -e "${RED}Failed: ${FAILED}${NC}"
echo

# Cleanup
cleanup

# Exit with appropriate code
if [ $FAILED -gt 0 ]; then
    echo -e "${RED}Some tests failed!${NC}"
    exit 1
else
    echo -e "${GREEN}All tests passed!${NC}"
    exit 0
fi
