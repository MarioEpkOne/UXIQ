import os
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring a real ANTHROPIC_API_KEY"
    )


@pytest.fixture(autouse=True)
def set_dummy_api_key(request, monkeypatch):
    """Set a dummy UXIQ_ANTHROPIC_API_KEY for all non-integration tests.

    Integration tests manage their own key requirement (skipping when absent).
    Unit tests mock the Anthropic client and only need the env var to be truthy
    so the guard in handler.py does not raise before the mocks are reached.
    """
    if "integration" not in request.keywords:
        monkeypatch.setenv("UXIQ_ANTHROPIC_API_KEY", "test-key-unit-tests")


@pytest.fixture
def fixtures_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")
