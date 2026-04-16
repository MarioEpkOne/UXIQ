"""Tests for ui_analyzer.utils — safe_log_url."""
from ui_analyzer.utils import safe_log_url


def test_safe_log_url_strips_path_query_fragment():
    url = "https://example.com/path/to/page?token=abc123&v=2#section"
    assert safe_log_url(url) == "https://example.com"


def test_safe_log_url_no_query_string():
    url = "https://example.com/dashboard"
    assert safe_log_url(url) == "https://example.com"


def test_safe_log_url_bare_host_no_path():
    url = "https://example.com"
    assert safe_log_url(url) == "https://example.com"


def test_safe_log_url_http_scheme():
    url = "http://internal.example.com/api?key=secret"
    assert safe_log_url(url) == "http://internal.example.com"


def test_safe_log_url_preserves_port():
    url = "https://example.com:8443/admin?token=xyz"
    assert safe_log_url(url) == "https://example.com:8443"
