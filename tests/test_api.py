import pytest
import sys
import os
import tempfile

# Pre-create the directory structure before importing anything
temp_dir = tempfile.mkdtemp()
os.makedirs(os.path.join(temp_dir, 's3_storage'), exist_ok=True)

# Set up environment for storage path BEFORE any imports
os.environ['STORAGE_LOCAL_PATH'] = os.path.join(temp_dir, 's3_storage')

# Mock database env vars
os.environ['DB_HOST'] = 'localhost'
os.environ['DB_PORT'] = '5432'
os.environ['DB_NAME'] = 'test_db'
os.environ['DB_USER'] = 'test_user'
os.environ['DB_PASS'] = 'test_password_12345678'
os.environ['DB_POOL_SIZE'] = '5'
os.environ['DB_MAX_OVERFLOW'] = '10'
os.environ['DB_POOL_TIMEOUT'] = '30'

os.environ['RMQ_HOST'] = 'localhost'
os.environ['RMQ_PORT'] = '5672'
os.environ['RMQ_USER'] = 'test_mq_user'
os.environ['RMQ_PASS'] = 'test_mq_password_12345678'
os.environ['RMQ_QUEUE_EXCHANGE'] = 'test'
os.environ['RMQ_QUEUE_ROUTING_KEY'] = 'test'
os.environ['RMQ_QUEUE_NAME'] = 'test_queue'
os.environ['RMQ_QUEUE_DEAD_LETTER_EXCHANGE'] = 'test_dlx'
os.environ['RMQ_QUEUE_ROUTING_KEY_DEAD_LETTER'] = 'test.dead'
os.environ['RMQ_QUEUE_DEAD_LETTER_NAME'] = 'test_dead'

os.environ['ENVIRONMENT'] = 'development'
os.environ['API_HOST'] = '0.0.0.0'
os.environ['API_PORT'] = '8000'
os.environ['API_WORKERS'] = '1'
os.environ['SECRET_KEY'] = 'test_secret_key_12345678901234567890'
os.environ['ACCESS_TOKEN_EXPIRE_MINUTES'] = '30'
os.environ['CORS_ORIGINS'] = 'http://localhost:3000'

os.environ['DEFAULT_PLAGIARISM_THRESHOLD'] = '0.75'
os.environ['SUPPORTED_LANGUAGES'] = 'python,java,cpp'
os.environ['MAX_FILE_SIZE'] = '1048576'
os.environ['MAX_FILES_PER_BATCH'] = '100'

os.environ['WORKER_CONCURRENCY'] = '4'
os.environ['WORKER_PREFETCH_COUNT'] = '1'

os.environ['LOG_LEVEL'] = 'INFO'
os.environ['LOG_FORMAT'] = 'json'

os.environ['REDIS_HOST'] = 'localhost'
os.environ['REDIS_PORT'] = '6379'
os.environ['REDIS_DB'] = '0'
os.environ['REDIS_FINGERPRINT_TTL'] = '604800'
os.environ['REDIS_USE_SSL'] = 'false'

os.environ['INVERTED_INDEX_MIN_OVERLAP_THRESHOLD'] = '0.15'

_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_project_root, 'src'))


class TestHealthEndpoint:
    def test_health_check(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}
    
    def test_version_endpoint(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/version")
        assert response.status_code == 200
        data = response.json()
        assert "version" in data
        assert "service" in data
    
    def test_root_endpoint(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/")
        assert response.status_code == 200


class TestAuthEndpoints:
    def test_register(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post("/auth/register", json={
            "username": "testuser",
            "email": "test@example.com",
            "password": "password123"
        })
        assert response.status_code == 200
        data = response.json()
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
    
    def test_login(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
            "username": "testuser"
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"
    
    def test_login_missing_fields(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.post("/auth/login", json={})
        assert response.status_code == 400
    
    def test_get_me_no_token(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/auth/me")
        assert response.status_code == 401
    
    def test_get_me_with_token(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        # First login to get token
        login_response = client.post("/auth/login", json={
            "email": "test@example.com",
            "password": "password123",
            "username": "testuser"
        })
        token = login_response.json()["access_token"]
        
        response = client.get("/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert "email" in data


class TestPlagiarismEndpoints:
    def test_get_task_not_found(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/plagiarism/nonexistent-id")
        assert response.status_code == 404
    
    def test_get_task_results_not_found(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/plagiarism/nonexistent-id/results")
        assert response.status_code == 404


class TestFileEndpoints:
    def test_get_all_files(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/plagiarism/files/all")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_file_content_not_found(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/plagiarism/files/nonexistent-id/content")
        assert response.status_code == 404


class TestResultsEndpoints:
    def test_get_all_results(self):
        from app import app
        from fastapi.testclient import TestClient
        client = TestClient(app)
        response = client.get("/plagiarism/results/all")
        assert response.status_code == 200
        assert isinstance(response.json(), list)
