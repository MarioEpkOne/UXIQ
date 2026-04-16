# Test-Writing Rules for ui-analyzer

## NEVER make real API calls in unit tests

Unit tests must **never** instantiate `anthropic.Anthropic()` or `anthropic.AsyncAnthropic()` and let them make real network calls. Real API calls cost money and must never run as part of the default `pytest` suite.

All Anthropic client usage must be patched with `unittest.mock.patch` or `pytest-mock` **before** any code under test runs.

## Integration tests

Files matching `test_*_integration.py` may use the real API. They must begin with this skip guard:

```python
import os
import pytest
if not os.getenv("ANTHROPIC_API_KEY") and not os.getenv("UXIQ_ANTHROPIC_API_KEY"):
    pytest.skip("integration test requires ANTHROPIC_API_KEY", allow_module_level=True)
```

Or use the `@pytest.mark.integration` marker — the conftest skip logic handles it automatically.

## Correct mock pattern for Anthropic client

```python
from unittest.mock import MagicMock, patch
import anthropic

def make_text_response(text: str) -> anthropic.types.Message:
    return MagicMock(
        spec=anthropic.types.Message,
        content=[MagicMock(spec=anthropic.types.TextBlock, type="text", text=text)],
        stop_reason="end_turn",
        usage=MagicMock(input_tokens=10, output_tokens=20),
    )

@patch("ui_analyzer.handler.anthropic.Anthropic")
def test_something(mock_anthropic_cls):
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = make_text_response("<audit_report>...</audit_report>")
    # now call your function under test
```

## Socket blocking

`pytest-socket` is installed and `--disable-socket` is set in `pyproject.toml`. Any test that opens a real network socket will **fail with a `SocketBlockedError`**. This is intentional. If your test hits the network, it is wrong — fix it by mocking.

Integration tests that legitimately need network access must use:

```python
@pytest.mark.enable_socket
def test_real_network_thing():
    ...
```
