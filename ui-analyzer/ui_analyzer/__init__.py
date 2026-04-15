import os
from ui_analyzer.exceptions import UIAnalyzerError

if not os.getenv("ANTHROPIC_API_KEY"):
    raise UIAnalyzerError("ANTHROPIC_API_KEY environment variable not set.")

__all__ = ["UIAnalyzerError"]
