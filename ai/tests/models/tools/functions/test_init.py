import pytest
from unittest.mock import Mock, patch, MagicMock
from models.tools.functions import call_function

# Mock class for testing
class MockClass:
    def test_method(self, *args):
        return f"Mock result with args: {args}"

    def method_with_error(self):
        raise Exception("Test error")

@pytest.fixture
def mock_container():
    """Fixture to mock the service container"""
    with patch('models.tools.functions.container') as mock:
        # Configure the mock to handle make() calls
        mock.make = MagicMock()
        yield mock

@pytest.mark.asyncio
async def test_call_function_success(mock_container):
    """Test successful function call"""
    # Mock test method
    async def test_method(a, b) : 
        assert a == 'arg1' and b == 'arg2'
        return "Mock result with args: ('arg1', 'arg2')"
    
    # Setup mock instance with MagicMock method
    mock_instance = MagicMock()
    # Configure the mock method to return our expected result
    mock_instance.test_method = test_method
    mock_container.make.return_value = mock_instance
    
    # Patch the logger to avoid attribute errors
    with patch('models.tools.functions.logging_decorator.FunctionCallLogger._write_log'):
        # Execute
        result = await call_function('MockClass-test_method', 'arg1', 'arg2')
        
        # Assert
        assert result == "Mock result with args: ('arg1', 'arg2')"
        mock_container.make.assert_called_once_with('MockClass')

@pytest.mark.asyncio
async def test_call_function_class_not_found(mock_container):
    """Test when class is not found in container"""
    # Setup
    mock_container.make.return_value = None
    
    # Execute
    result = await call_function('NonExistentClass-test_method', 'arg1')
    
    # Assert
    assert result is None
    mock_container.make.assert_called_once_with('NonExistentClass')

@pytest.mark.asyncio
async def test_call_function_method_not_found(mock_container):
    """Test when method is not found in class"""
    # Setup
    mock_instance = MockClass()
    mock_container.make.return_value = mock_instance
    
    # Execute
    result = await call_function('MockClass-non_existent_method', 'arg1')
    
    # Assert
    assert result is None
    mock_container.make.assert_called_once_with('MockClass')

@pytest.mark.asyncio
async def test_call_function_with_error(mock_container):
    """Test when method raises an exception"""
    # Setup
    mock_instance = MockClass()
    mock_container.make.return_value = mock_instance
    
    # Execute
    result = await call_function('MockClass-method_with_error')
    
    # Assert
    assert result is None
    mock_container.make.assert_called_once_with('MockClass')

@pytest.mark.asyncio
async def test_call_function_invalid_format():
    """Test when function name format is invalid"""
    # Execute
    result = await call_function('InvalidFormat')
    
    # Assert
    assert result is None