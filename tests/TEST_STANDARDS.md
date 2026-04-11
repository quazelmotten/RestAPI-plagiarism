# Test Standards

This document defines the standards and best practices for writing tests in this project.

## Test Organization

```
tests/
├── unit/                    # Unit tests (fast, isolated with mocks)
│   ├── test_migration.py
│   ├── test_config.py
│   └── ...
├── integration/             # Integration tests (require real DB/services)
│   ├── test_api_endpoints.py
│   ├── test_e2e_workflow.py
│   └── conftest.py
├── worker/
│   ├── unit/              # Worker unit tests
│   └── integration/       # Worker integration tests
└── conftest.py           # Shared fixtures
```

## Markers

Use pytest markers to categorize tests:

- `@pytest.mark.unit` - Fast, isolated tests with mocks
- `@pytest.mark.integration` - Tests requiring PostgreSQL/Redis/RabbitMQ
- `@pytest.mark.slow` - Tests that take longer to run
- `@pytest.mark.smoke` - Basic smoke tests (just verify no crash)

---

## Integration Tests

### Status Code Assertions

**ALWAYS use exact expected codes:**

```python
# Good
assert response.status_code == 201
assert response.status_code == 404

# Bad - NEVER accept 500 as valid
assert response.status_code in (200, 500)
assert response.status_code in (201, 405, 500)
```

**Exception - Only use ranges for valid error states:**

```python
# Acceptable - both 422 and 404 are valid error responses
assert response.status_code in (422, 404)

# Still bad - includes server error
assert response.status_code in (422, 404, 500)
```

### Response Validation

Every test should verify the response body:

```python
# Good
response = await client.post("/path", json=payload)
assert response.status_code == 201
data = response.json()
assert "id" in data
assert data["name"] == "expected"

# Minimum acceptable
response = await client.get("/path")
assert response.status_code == 200
data = response.json()
assert isinstance(data, dict)

# Bad - no response validation
response = await client.post("/path", json=payload)
assert response.status_code == 201  # Only checks status
```

### Test Structure Pattern

```python
class TestSomething:
    async def test_create_something(self, client: AsyncClient):
        """Test creating a new something."""
        # Arrange
        payload = {"name": "Test", "description": "Test desc"}
        
        # Act
        response = await client.post("/plagitype/plagiarism/somethings", json=payload)
        
        # Assert
        assert response.status_code == 201, f"Failed: {response.text}"
        data = response.json()
        assert "id" in data
        assert data["name"] == "Test"
```

### Error Cases

```python
async def test_create_something_validation_error(self, client: AsyncClient):
    """Test validation errors are properly returned."""
    response = await client.post("/plagitype/plagiarism/somethings", json={})
    assert response.status_code == 422, f"Expected validation error: {response.text}"
    data = response.json()
    assert "detail" in data
```

---

## Unit Tests

### Prefer Real Implementation Over Mocks

Test actual behavior when possible:

```python
# Good - tests real algorithm
from plagiarism_core.matcher import find_paired_occurrences

def test_finds_matching_hashes():
    index_a = {100: [{"kgram_idx": 0, "start": (1, 0), "end": (1, 10)}]}
    index_b = {100: [{"kgram_idx": 0, "start": (1, 0), "end": (1, 10)}]}
    occs = find_paired_occurrences(index_a, index_b)
    assert len(occs) == 1
    assert occs[0].fingerprint_hash == 100
```

### When to Use Mocks

Use mocks for external dependencies:
- Database connections
- Redis clients
- RabbitMQ publishers
- External API clients
- File system operations (use tmp_path fixture)

### Mock Pattern

```python
@pytest.fixture
def mock_cache():
    """Create a mock cache."""
    cache = MagicMock(spec=FingerprintCache)
    cache.batch_get.return_value = {}
    return cache
```

---

## Test Fixtures

### Creating Reusable Fixtures

Add to `tests/conftest.py`:

```python
@pytest.fixture
def sample_assignment_payload():
    """Returns a minimal valid assignment payload."""
    return {"name": "Test Assignment", "description": "Test description"}
```

### Fixture Scope

- `function` (default) - created for each test
- `class` - created once per test class
- `session` - created once per test session

---

## Running Tests

### Run All Tests
```bash
pytest
```

### Run Only Unit Tests
```bash
pytest -m unit
```

### Run Only Integration Tests
```bash
pytest -m integration
```

### Run with Coverage
```bash
pytest --cov=src --cov-report=term-missing
```

---

## Anti-Patterns to Avoid

1. **No assertions**: Tests that just call code without verifying behavior
2. **Over-permissive status codes**: Accepting 500 as valid
3. **No response validation**: Only checking status, not body
4. **Try/except/pass**: Swallowing exceptions without verification
5. **Testing stdlib behavior**: Don't test Python built-ins (json.loads, etc.)
6. **Over-mocking**: Mocking everything instead of testing real behavior
7. **Magic numbers**: Using unexplained values in assertions

---

## Checklist Before Submitting Tests

- [ ] Status code is exact (not a range including 500)
- [ ] Response body is validated
- [ ] Error messages include `f"Context: {response.text}"` 
- [ ] Test has a clear docstring
- [ ] Mock usage is minimal and justified
- [ ] No try/except/pass patterns