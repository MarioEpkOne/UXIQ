"""Tests for ui_analyzer.image_source."""
import io
import os

import pytest
from PIL import Image
from unittest.mock import MagicMock, patch

from ui_analyzer.exceptions import UIAnalyzerError
from ui_analyzer.image_source import ResolvedImage, resolve

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_png_bytes(width: int = 100, height: int = 100) -> bytes:
    """Return in-memory PNG bytes for a solid-colour image."""
    img = Image.new("RGB", (width, height), color=(100, 149, 237))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# File mode — valid input
# ---------------------------------------------------------------------------


def test_image_source_file_valid(fixtures_dir):
    """Valid PNG path returns ResolvedImage with source_type='file' and correct dimensions."""
    path = os.path.join(fixtures_dir, "dashboard_good.png")
    result = resolve(path)

    assert isinstance(result, ResolvedImage)
    assert result.source_type == "file"
    assert len(result.bytes) > 0
    # dashboard_good.png is 200x200 (created in Step 4)
    assert result.width_px == 200
    assert result.height_px == 200


# ---------------------------------------------------------------------------
# File mode — missing file
# ---------------------------------------------------------------------------


def test_image_source_file_missing(tmp_path):
    """Non-existent path raises UIAnalyzerError with correct message."""
    missing = str(tmp_path / "does_not_exist.png")
    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve(missing)
    assert "File not found:" in str(exc_info.value)
    assert "does_not_exist.png" in str(exc_info.value)


# ---------------------------------------------------------------------------
# File mode — bad extension
# ---------------------------------------------------------------------------


def test_image_source_file_bad_extension(tmp_path):
    """Unsupported extension raises UIAnalyzerError with exact catalogue message."""
    pdf_file = tmp_path / "document.pdf"
    pdf_file.write_bytes(b"%PDF-1.4 fake content")

    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve(str(pdf_file))
    assert str(exc_info.value) == "Unsupported file type. Accepted: PNG, JPG, JPEG, WebP."


# ---------------------------------------------------------------------------
# Resize logic — image larger than MAX_EDGE
# ---------------------------------------------------------------------------


def test_image_resize_large(tmp_path):
    """Image with longest edge > 1568px is resized; original bytes not mutated."""
    original_bytes = _make_png_bytes(width=2000, height=1000)
    large_file = tmp_path / "large.png"
    large_file.write_bytes(original_bytes)

    result = resolve(str(large_file))

    # Longest edge must be <= 1568
    assert max(result.width_px, result.height_px) <= 1568
    # Bytes should differ from original (resized)
    assert result.bytes != original_bytes
    # Original file unchanged
    assert large_file.read_bytes() == original_bytes


# ---------------------------------------------------------------------------
# Resize logic — image smaller than or equal to MAX_EDGE
# ---------------------------------------------------------------------------


def test_image_resize_small(tmp_path):
    """Image with longest edge <= 1568px is returned unchanged."""
    original_bytes = _make_png_bytes(width=800, height=600)
    small_file = tmp_path / "small.png"
    small_file.write_bytes(original_bytes)

    result = resolve(str(small_file))

    # Dimensions unchanged
    assert result.width_px == 800
    assert result.height_px == 600
    # Bytes identical to input
    assert result.bytes == original_bytes


# ---------------------------------------------------------------------------
# URL mode — error scenarios (Playwright mocked)
# ---------------------------------------------------------------------------


def _make_mock_pw_context(
    *,
    response_status: int = 200,
    raise_timeout: bool = False,
    body_text: str = "Hello world",
    image_count: int = 0,
    screenshot_bytes: bytes = b"\x89PNG\r\n",
):
    """Build a nested mock that replaces sync_playwright()."""
    mock_response = MagicMock()
    mock_response.status = response_status

    mock_page = MagicMock()
    if raise_timeout:
        from playwright.sync_api import TimeoutError as PlaywrightTimeout
        mock_page.goto.side_effect = PlaywrightTimeout("Timeout exceeded")
    else:
        mock_page.goto.return_value = mock_response

    mock_page.evaluate.side_effect = lambda expr: (
        body_text if "innerText" in expr else image_count
    )
    mock_page.screenshot.return_value = screenshot_bytes

    mock_context = MagicMock()
    mock_context.new_page.return_value = mock_page

    mock_browser = MagicMock()
    mock_browser.new_context.return_value = mock_context

    mock_pw_instance = MagicMock()
    mock_pw_instance.chromium.launch.return_value = mock_browser

    mock_pw_cm = MagicMock()
    mock_pw_cm.__enter__ = MagicMock(return_value=mock_pw_instance)
    mock_pw_cm.__exit__ = MagicMock(return_value=False)

    return mock_pw_cm


def test_url_mode_timeout(mocker):
    """Playwright TimeoutError raises UIAnalyzerError with exact catalogue message."""
    mock_cm = _make_mock_pw_context(raise_timeout=True)
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve("https://example.com")
    assert str(exc_info.value) == "URL did not load within 30s. Provide a screenshot file path instead."


def test_url_mode_http_404(mocker):
    """HTTP 404 response raises UIAnalyzerError with exact catalogue message."""
    mock_cm = _make_mock_pw_context(response_status=404)
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve("https://example.com")
    assert str(exc_info.value) == "Could not load URL: HTTP 404. Provide a screenshot file path instead."


def test_url_mode_http_500(mocker):
    """HTTP 500 response raises UIAnalyzerError with status interpolated."""
    mock_cm = _make_mock_pw_context(response_status=500)
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve("https://example.com")
    assert str(exc_info.value) == "Could not load URL: HTTP 500. Provide a screenshot file path instead."


def test_url_mode_blank_page(mocker):
    """Blank page (no text, no images) raises UIAnalyzerError with exact catalogue message."""
    mock_cm = _make_mock_pw_context(body_text="   ", image_count=0)
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    with pytest.raises(UIAnalyzerError) as exc_info:
        resolve("https://example.com")
    assert str(exc_info.value) == "Page rendered no visible content. Provide a screenshot file path instead."


def test_url_mode_blank_page_with_images_does_not_raise(mocker):
    """Blank body text but images present — should NOT raise (page has content)."""
    screenshot_bytes = _make_png_bytes(1280, 800)
    mock_cm = _make_mock_pw_context(body_text="  ", image_count=3, screenshot_bytes=screenshot_bytes)
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    result = resolve("https://example.com")
    assert result.source_type == "url"
    assert result.width_px == 1280
    assert result.height_px == 800


def test_url_mode_success(mocker):
    """Successful URL capture returns ResolvedImage with source_type='url', w=1280, h=800."""
    screenshot_bytes = _make_png_bytes(1280, 800)
    mock_cm = _make_mock_pw_context(
        response_status=200,
        body_text="Hello world",
        image_count=2,
        screenshot_bytes=screenshot_bytes,
    )
    mocker.patch("ui_analyzer.image_source.sync_playwright", return_value=mock_cm)

    result = resolve("https://example.com")
    assert result.source_type == "url"
    assert len(result.bytes) > 0
    assert result.width_px == 1280
    assert result.height_px == 800

