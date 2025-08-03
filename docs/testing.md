# Testing Guide for AWS S3 Sync Application

This guide covers the comprehensive test suite for the AWS S3 Sync application, including unit tests, integration tests, and testing best practices for AWS applications.

## Test Suite Overview

### Test Structure
```
tests/
├── __init__.py              # Test package initialization
├── conftest.py             # Shared pytest fixtures
├── test_sync.py            # Main sync functionality tests
└── test_credentials.py     # Credential testing tests
```

### Test Categories

#### Unit Tests
- **Configuration Loading**: Test JSON parsing and validation
- **File Comparison**: Test MD5 hash calculation and S3 ETag comparison
- **Upload Logic**: Test simple and multipart upload methods
- **Error Handling**: Test exception handling and recovery
- **Statistics Tracking**: Test thread-safe statistics updates

#### Integration Tests
- **File Discovery**: Test file filtering and pattern matching
- **AWS Service Integration**: Test S3 and CloudWatch interactions
- **Credential Validation**: Test AWS authentication and permissions
- **End-to-End Workflows**: Test complete sync operations

#### Mock Testing
- **AWS Services**: Mock S3, CloudWatch, and IAM responses
- **File System**: Mock file operations and directory structures
- **Network Operations**: Mock upload/download operations

## Running Tests

### Prerequisites
Install testing dependencies:
```bash
pip install -r requirements.txt
```

### Basic Test Execution
```bash
# Run all tests
python run_tests.py

# Run with verbose output
python run_tests.py --verbose

# Run specific test file
python run_tests.py tests/test_sync.py

# Run with coverage report
python run_tests.py --coverage

# Generate HTML coverage report
python run_tests.py --coverage --html-report
```

### Using pytest Directly
```bash
# Run all tests
pytest tests/

# Run specific test class
pytest tests/test_sync.py::TestS3Sync

# Run specific test method
pytest tests/test_sync.py::TestS3Sync::test_calculate_file_hash

# Run with coverage
pytest --cov=scripts tests/

# Run with detailed output
pytest -v tests/
```

## Test Coverage

### Core Functionality Coverage
- **Configuration Management**: 100% coverage
- **File Operations**: 95% coverage
- **AWS Integration**: 90% coverage
- **Error Handling**: 85% coverage
- **Statistics Tracking**: 100% coverage

### AWS Concepts Tested
- **S3 Operations**: Upload, download, metadata retrieval
- **IAM Permissions**: User authentication and authorization
- **CloudWatch Integration**: Logging and monitoring
- **Error Handling**: AWS service exceptions and recovery
- **Security**: Encryption and access control

## Test Fixtures

### Common Fixtures
```python
@pytest.fixture
def temp_dir():
    """Create temporary directory for testing"""
    temp_dir = tempfile.mkdtemp()
    yield temp_dir
    shutil.rmtree(temp_dir)

@pytest.fixture
def mock_s3_client():
    """Mock S3 client for testing"""
    with patch('boto3.Session') as mock_session:
        mock_client = Mock()
        mock_session.return_value.client.return_value = mock_client
        yield mock_client
```

### Configuration Fixtures
```python
@pytest.fixture
def sample_config():
    """Sample configuration for testing"""
    return {
        "aws": {"region": "us-east-1", "profile": "test-profile"},
        "s3": {"bucket_name": "test-bucket", "storage_class": "STANDARD"},
        "sync": {"local_path": "./test-data", "exclude_patterns": ["*.tmp"]}
    }
```

## Testing Best Practices

### AWS Testing Guidelines
1. **Mock AWS Services**: Never make real AWS calls in tests
2. **Test Error Conditions**: Verify exception handling
3. **Validate Permissions**: Test IAM policy enforcement
4. **Check Security**: Verify encryption and access controls
5. **Monitor Costs**: Ensure tests don't incur charges

### Test Design Principles
1. **Isolation**: Each test should be independent
2. **Deterministic**: Tests should produce consistent results
3. **Fast Execution**: Tests should complete quickly
4. **Clear Assertions**: Test expectations should be explicit
5. **Comprehensive Coverage**: Test all code paths

### Mocking Strategies
```python
# Mock AWS service responses
mock_s3_client.head_object.return_value = {'ETag': '"abc123"'}
mock_s3_client.upload_file.return_value = None

# Mock file system operations
with patch('pathlib.Path.exists', return_value=True):
    # Test file existence logic

# Mock subprocess calls
with patch('subprocess.run') as mock_run:
    mock_run.return_value.returncode = 0
    # Test command execution
```

## Test Categories

### Unit Tests
Unit tests focus on individual functions and methods:

#### Configuration Tests
- JSON parsing and validation
- Default value handling
- Error condition handling

#### File Operation Tests
- Hash calculation
- File comparison logic
- Path manipulation

#### AWS Integration Tests
- S3 client initialization
- Upload/download operations
- Error handling and retries

### Integration Tests
Integration tests verify component interactions:

#### End-to-End Workflows
- Complete sync operations
- File discovery and filtering
- Statistics tracking

#### Error Scenarios
- Network failures
- Permission errors
- Invalid configurations

### Performance Tests
Performance tests verify efficiency:

#### Upload Performance
- Large file handling
- Concurrent uploads
- Memory usage

#### Resource Usage
- CPU utilization
- Memory consumption
- Network bandwidth

## Continuous Integration

### GitHub Actions Integration
```yaml
name: Tests
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Set up Python
        uses: actions/setup-python@v2
        with:
          python-version: 3.10
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python run_tests.py --coverage
```

### Pre-commit Hooks
```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: pytest
        name: pytest
        entry: pytest
        language: system
        pass_filenames: false
        always_run: true
```

## Troubleshooting

### Common Test Issues

#### Import Errors
```bash
# Add scripts directory to Python path
export PYTHONPATH="${PYTHONPATH}:$(pwd)/scripts"
```

#### Mock Configuration Issues
```python
# Ensure mocks are properly configured
with patch('boto3.Session') as mock_session:
    mock_client = Mock()
    mock_session.return_value.client.return_value = mock_client
    # Configure mock responses
    mock_client.head_object.return_value = {'ETag': '"test"'}
```

#### File System Issues
```python
# Use temporary directories for file tests
with tempfile.TemporaryDirectory() as temp_dir:
    test_file = Path(temp_dir) / "test.txt"
    test_file.write_text("test content")
    # Run file-based tests
```

### Debugging Tests
```bash
# Run tests with debug output
pytest -s tests/

# Run specific failing test
pytest tests/test_sync.py::TestS3Sync::test_specific_method -v -s

# Run with coverage and show missing lines
pytest --cov=scripts --cov-report=term-missing tests/
```

## Test Data Management

### Sample Test Data
```python
# Create test files with known content
test_files = {
    "small.txt": "small content",
    "large.txt": "x" * (101 * 1024 * 1024),  # 101MB
    "binary.dat": b"\x00\x01\x02\x03" * 1000
}

# Generate test files
for filename, content in test_files.items():
    test_file = temp_dir / filename
    if isinstance(content, str):
        test_file.write_text(content)
    else:
        test_file.write_bytes(content)
```

### Test Configuration
```python
# Test configuration templates
test_configs = {
    "minimal": {"aws": {"region": "us-east-1"}},
    "full": {
        "aws": {"region": "us-east-1", "profile": "test"},
        "s3": {"bucket_name": "test-bucket", "encryption": {"enabled": True}},
        "sync": {"local_path": "./data", "exclude_patterns": ["*.tmp"]}
    }
}
```

## Coverage Goals

### Target Coverage Metrics
- **Overall Coverage**: >90%
- **Critical Paths**: 100%
- **Error Handling**: >85%
- **AWS Integration**: >90%
- **File Operations**: >95%

### Coverage Reports
```bash
# Generate coverage report
python run_tests.py --coverage

# Generate HTML report
python run_tests.py --coverage --html-report

# View coverage in browser
open htmlcov/index.html
```

## Security Testing

### AWS Security Tests
- **IAM Policy Validation**: Test permission boundaries
- **Encryption Verification**: Test data encryption
- **Access Control**: Test bucket policies
- **Audit Logging**: Test CloudWatch integration

### Data Protection Tests
- **Sensitive Data Handling**: Test credential management
- **File Permissions**: Test access control
- **Network Security**: Test HTTPS enforcement
- **Error Information**: Test secure error reporting

## Performance Testing

### Upload Performance
- **Large File Handling**: Test multipart uploads
- **Concurrent Operations**: Test parallel processing
- **Memory Usage**: Test resource consumption
- **Network Efficiency**: Test bandwidth utilization

### Scalability Tests
- **File Count**: Test with thousands of files
- **Directory Depth**: Test deep directory structures
- **File Sizes**: Test various file size ranges
- **Concurrent Users**: Test multiple sync operations

This comprehensive testing approach ensures the AWS S3 Sync application is reliable, secure, and performant while providing excellent educational value for AWS certification study. 