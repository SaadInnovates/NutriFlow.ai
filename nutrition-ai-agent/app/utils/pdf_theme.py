from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_THEME_PATH = BASE_DIR / "data" / "pdf_theme.json"


@dataclass
class PDFTheme:
	report_title: str
	company_name: str
	header_text_rgb: tuple[int, int, int]
	header_line_rgb: tuple[int, int, int]
	cover_fill_rgb: tuple[int, int, int]
	title_text_rgb: tuple[int, int, int]
	body_text_rgb: tuple[int, int, int]
	muted_text_rgb: tuple[int, int, int]
	font_family: str
	font_size_body: int
	font_size_title: int
	font_size_heading: int
	font_size_meta: int


DEFAULT_THEME = PDFTheme(
	report_title="Nutrition AI Agent Report",
	company_name="Nutrition AI Agent",
	header_text_rgb=(32, 39, 56),
	header_line_rgb=(210, 214, 220),
	cover_fill_rgb=(255, 255, 255),
	title_text_rgb=(20, 30, 50),
	body_text_rgb=(35, 42, 58),
	muted_text_rgb=(120, 125, 135),
	font_family="Helvetica",
	font_size_body=11,
	font_size_title=22,
	font_size_heading=13,
	font_size_meta=9,
)


def _hex_to_rgb(value: str, fallback: tuple[int, int, int]) -> tuple[int, int, int]:
	text = (value or "").strip().lstrip("#")
	if len(text) != 6:
		return fallback
	try:
		return tuple(int(text[index : index + 2], 16) for index in (0, 2, 4))  # type: ignore[return-value]
	except Exception:
		return fallback


def _read_theme_config(path: Path) -> dict[str, Any]:
	if not path.exists():
		return {}
	try:
		return json.loads(path.read_text(encoding="utf-8"))
	except Exception:
		return {}


def get_pdf_theme(theme_path: Path = DEFAULT_THEME_PATH) -> PDFTheme:
	config = _read_theme_config(theme_path)
	colors = config.get("colors", {})
	typography = config.get("typography", {})

	return PDFTheme(
		report_title=config.get("report_title", DEFAULT_THEME.report_title),
		company_name=config.get("company_name", DEFAULT_THEME.company_name),
		header_text_rgb=_hex_to_rgb(colors.get("header_text", ""), DEFAULT_THEME.header_text_rgb),
		header_line_rgb=_hex_to_rgb(colors.get("header_line", ""), DEFAULT_THEME.header_line_rgb),
		cover_fill_rgb=_hex_to_rgb(colors.get("cover_fill", ""), DEFAULT_THEME.cover_fill_rgb),
		title_text_rgb=_hex_to_rgb(colors.get("title_text", ""), DEFAULT_THEME.title_text_rgb),
		body_text_rgb=_hex_to_rgb(colors.get("body_text", ""), DEFAULT_THEME.body_text_rgb),
		muted_text_rgb=_hex_to_rgb(colors.get("muted_text", ""), DEFAULT_THEME.muted_text_rgb),
		font_family=typography.get("font_family", DEFAULT_THEME.font_family),
		font_size_body=int(typography.get("font_size_body", DEFAULT_THEME.font_size_body)),
		font_size_title=int(typography.get("font_size_title", DEFAULT_THEME.font_size_title)),
		font_size_heading=int(typography.get("font_size_heading", DEFAULT_THEME.font_size_heading)),
		font_size_meta=int(typography.get("font_size_meta", DEFAULT_THEME.font_size_meta)),
	)
