"""cli.py — Command-line entry point for uxiq.

Usage:
    uxiq analyze <image_source> --app-type <type> [-o <output>]
    uxiq list-app-types
    uxiq --version
"""
from __future__ import annotations

import argparse
import sys
import time
from importlib.metadata import version, PackageNotFoundError

from pydantic import ValidationError

from ui_analyzer.exceptions import UIAnalyzerError

VALID_APP_TYPES = ["forms", "landing_page", "onboarding_flow", "web_dashboard"]


# ---------------------------------------------------------------------------
# Progress reporter
# ---------------------------------------------------------------------------

class StderrProgress:
    """Writes pipeline progress to stderr.

    Satisfies the ProgressCallback protocol in handler.py (duck-typed).
    Each stage produces two lines:
      →  <start label>
      ✓  <completion label> (<elapsed>s)[ — <detail>]
    A final summary line is written by calling .done().
    """

    _ARROW = "\u2192"   # →
    _CHECK = "\u2713"   # ✓
    _ARROW_ASCII = "->"
    _CHECK_ASCII = "OK"

    def __init__(self) -> None:
        self._starts: dict[str, float] = {}
        self._total_start = time.monotonic()

    def stage_start(self, stage: str, label: str) -> None:
        self._starts[stage] = time.monotonic()
        self._write(f"{self._ARROW} {label}", arrow=True)

    def stage_end(self, stage: str, label: str, elapsed: float, detail: str = "") -> None:
        suffix = f" \u2014 {detail}" if detail else ""  # — (em-dash)
        self._write(f"{self._CHECK} {label} ({elapsed:.1f}s){suffix}", arrow=False)

    def done(self) -> None:
        total = time.monotonic() - self._total_start
        self._write(f"{self._CHECK} Done (total: {total:.1f}s)", arrow=False)

    def _write(self, message: str, *, arrow: bool) -> None:
        try:
            print(message, file=sys.stderr)
        except UnicodeEncodeError:
            # Fall back to ASCII equivalents for Windows terminals without UTF-8
            if arrow:
                message = message.replace(self._ARROW, self._ARROW_ASCII)
            else:
                message = message.replace(self._CHECK, self._CHECK_ASCII)
            print(message, file=sys.stderr)


def main() -> None:
    """Entry point registered in pyproject.toml."""
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


def _cmd_analyze(args: argparse.Namespace) -> None:
    """Handle `uxiq analyze <image_source> --app-type <type> [-o <path>] [-q]`."""
    from ui_analyzer.handler import analyze_ui_screenshot

    progress = None if args.quiet else StderrProgress()
    try:
        report = analyze_ui_screenshot(args.image_source, args.app_type, progress=progress)
    except ValidationError as exc:
        # Invalid app_type value — rejected by pydantic before any API call
        app_type_val = args.app_type
        print(
            f"Invalid app-type: {app_type_val!r}. "
            f"Valid: {', '.join(VALID_APP_TYPES)}",
            file=sys.stderr,
        )
        sys.exit(1)
    except UIAnalyzerError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)
    if progress is not None:
        progress.done()

    if args.output:
        try:
            with open(args.output, "w", encoding="utf-8") as fh:
                fh.write(report)
        except OSError as exc:
            print(f"Error writing output file: {exc}", file=sys.stderr)
            sys.exit(1)
        print(f"Report saved to {args.output}", file=sys.stderr)
    else:
        print(report)


def _cmd_list_app_types(args: argparse.Namespace) -> None:
    """Handle `uxiq list-app-types`."""
    for app_type in VALID_APP_TYPES:
        print(app_type)


def _cmd_no_subcommand(args: argparse.Namespace) -> None:
    """Handle `uxiq` with no subcommand — print help and exit 0."""
    args._parser.print_help()
    sys.exit(0)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="uxiq",
        description="UI accessibility and UX auditor powered by Claude.",
    )
    parser.add_argument(
        "-V", "--version",
        action="version",
        version=_get_version(),
    )

    subparsers = parser.add_subparsers(dest="subcommand")

    # uxiq analyze
    analyze_parser = subparsers.add_parser(
        "analyze",
        help="Analyze a UI screenshot or URL and produce a Markdown audit report.",
    )
    analyze_parser.add_argument(
        "image_source",
        help="Path to a local image file or a URL (https://...).",
    )
    analyze_parser.add_argument(
        "--app-type", "-t",
        dest="app_type",
        required=True,
        metavar="APP_TYPE",
        help=f"Type of app being audited. One of: {', '.join(VALID_APP_TYPES)}",
    )
    analyze_parser.add_argument(
        "--output", "-o",
        dest="output",
        default=None,
        help="Optional path to write the Markdown report. Defaults to stdout.",
    )
    analyze_parser.add_argument(
        "--quiet", "-q",
        dest="quiet",
        action="store_true",
        default=False,
        help="Suppress progress output. Useful for scripting and CI.",
    )
    analyze_parser.set_defaults(func=_cmd_analyze)

    # uxiq list-app-types
    list_parser = subparsers.add_parser(
        "list-app-types",
        help="Print all valid app types.",
    )
    list_parser.set_defaults(func=_cmd_list_app_types)

    # Default: no subcommand → print help
    parser.set_defaults(func=lambda args: (args.__setattr__("_parser", parser), _cmd_no_subcommand(args)))

    return parser


def _get_version() -> str:
    try:
        v = version("ui-analyzer")
    except PackageNotFoundError:
        v = "unknown"
    return f"uxiq {v}"


if __name__ == "__main__":
    main()
