import os
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring a real ANTHROPIC_API_KEY"
    )


@pytest.fixture
def fixtures_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")
