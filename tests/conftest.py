import pytest

@pytest.fixture
def sample_data():
    return {
        'key1': 'value1',
        'key2': 'value2',
    }

@pytest.fixture
def sample_formatter():
    return "This is a sample formatter for testing."
