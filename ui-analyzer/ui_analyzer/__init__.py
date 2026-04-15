import os
from ui_analyzer.exceptions import UIAnalyzerError

if not os.getenv("ANTHROPIC_API_KEY"):
    raise UIAnalyzerError("ANTHROPIC_API_KEY environment variable not set.")

from ui_analyzer.handler import analyze_ui_screenshot
from ui_analyzer.tool_definition import TOOL_DEFINITION

__all__ = ["UIAnalyzerError", "analyze_ui_screenshot", "TOOL_DEFINITION"]
