"""utils.py — Shared utility helpers for ui-analyzer."""
from urllib.parse import urlparse


def safe_log_url(url: str) -> str:
    """Return only scheme+netloc — strip path, query, and fragment.

    Used in log messages to prevent token/credential leakage via URLs
    that may contain query-string API keys or session tokens.
    """
    p = urlparse(url)
    return f"{p.scheme}://{p.netloc}"
