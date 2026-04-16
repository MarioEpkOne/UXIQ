"""cli.py — Command-line entry point for uxiq.

Usage:
    uxiq analyze <image_source> --app-type <type> [-o <output>]
    uxiq list-app-types
    uxiq --version
"""
from __future__ import annotations

import argparse
import sys
from importlib.metadata import version, PackageNotFoundError

from pydantic import ValidationError

from ui_analyzer.exceptions import UIAnalyzerError

VALID_APP_TYPES = ["forms", "landing_page", "onboarding_flow", "web_dashboard"]


def main() -> None:
    """Entry point registered in pyproject.toml."""
    parser = _build_parser()
    args = parser.parse_args()
    args.func(args)


def _cmd_analyze(args: argparse.Namespace) -> None:
    """Handle `uxiq analyze <image_source> --app-type <type> [-o <path>]`."""
    from ui_analyzer.handler import analyze_ui_screenshot

    try:
        report = analyze_ui_screenshot(args.image_source, args.app_type)
    except ValidationError as exc:
        # Invalid app_type value (already caught by argparse choices, but belt+suspenders)
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
        choices=VALID_APP_TYPES,
        metavar="APP_TYPE",
        help=f"Type of app being audited. One of: {', '.join(VALID_APP_TYPES)}",
    )
    analyze_parser.add_argument(
        "--output", "-o",
        dest="output",
        default=None,
        help="Optional path to write the Markdown report. Defaults to stdout.",
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
