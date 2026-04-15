class UIAnalyzerError(Exception):
    """Raised on hard failures in ui-analyzer.

    Hard failures (raise UIAnalyzerError):
        - URL load failure (404, timeout, blank page)
        - File not found or unsupported type
        - ANTHROPIC_API_KEY not set
        - Anthropic API timeout or rate limit

    Soft failures (return degraded Markdown report, never raise):
        - axe-core failure
        - Claude returning malformed XML
        - Partial tier output
    """
