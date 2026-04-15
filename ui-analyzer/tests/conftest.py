import os
import pytest

# IMPORTANT: ui_analyzer/__init__.py raises UIAnalyzerError at import time
# if ANTHROPIC_API_KEY is unset. Set a fake key before any ui_analyzer import
# so that unit tests (which mock the API) can import the package.
# This must happen before pytest collects test modules.
if not os.getenv("ANTHROPIC_API_KEY"):
    os.environ["ANTHROPIC_API_KEY"] = "test-key-unit-tests"


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as requiring a real ANTHROPIC_API_KEY"
    )


@pytest.fixture
def fixtures_dir():
    return os.path.join(os.path.dirname(__file__), "fixtures")
