from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fpdf import FPDF
from fpdf.errors import FPDFException

from app.utils.pdf_theme import PDFTheme, get_pdf_theme


class DietPlanPDF(FPDF):
	def __init__(self, theme: PDFTheme) -> None:
		super().__init__()
		self.theme = theme
		self.report_title = theme.report_title
		self.set_auto_page_break(auto=True, margin=14)

	def header(self) -> None:
		if self.page_no() == 1:
			return
		self.set_font(self.theme.font_family, "B", 10)
		self.set_text_color(*self.theme.header_text_rgb)
		self.cell(0, 8, self.report_title, new_x="LMARGIN", new_y="NEXT")
		self.set_draw_color(*self.theme.header_line_rgb)
		self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
		self.ln(3)

	def footer(self) -> None:
		self.set_y(-12)
		self.set_font(self.theme.font_family, "", self.theme.font_size_meta)
		self.set_text_color(*self.theme.muted_text_rgb)
		self.cell(0, 8, f"Page {self.page_no()}", align="C")


SECTION_NAMES = [
	"Summary",
	"Daily Calories & Macros",
	"7-Day Meal Plan",
	"Grocery List",
	"Habit & Adherence Tips",
	"Safety Notes",
]


def _sanitize_text(value: str) -> str:
	text = value.replace("\t", " ").replace("\u00a0", " ")
	return text.encode("latin-1", errors="replace").decode("latin-1")


def _safe_multicell(pdf: DietPlanPDF, text: str, line_height: int = 7, x: float | None = None) -> None:
	if x is not None:
		pdf.set_x(x)
	min_x = pdf.l_margin
	if pdf.get_x() >= (pdf.w - pdf.r_margin - 5):
		pdf.set_x(min_x)
	available_width = max(20, pdf.w - pdf.r_margin - pdf.get_x())
	safe_text = _sanitize_text(text)
	try:
		pdf.multi_cell(available_width, line_height, safe_text)
	except FPDFException:
		for chunk_start in range(0, len(safe_text), 70):
			pdf.multi_cell(available_width, line_height, safe_text[chunk_start : chunk_start + 70])


def _split_sections(plan_text: str) -> list[tuple[str, str]]:
	lines = [_sanitize_text(line.strip()) for line in plan_text.splitlines()]
	sections: list[tuple[str, list[str]]] = []
	current_title = "Plan"
	current_lines: list[str] = []

	def is_heading(line: str) -> str | None:
		normalized = line.replace("*", "").replace(":", "").strip().lower()
		for name in SECTION_NAMES:
			if normalized == name.lower():
				return name
		return None

	for raw in lines:
		if not raw:
			current_lines.append("")
			continue
		heading = is_heading(raw)
		if heading:
			sections.append((current_title, current_lines))
			current_title = heading
			current_lines = []
		else:
			current_lines.append(raw)
	sections.append((current_title, current_lines))

	result: list[tuple[str, str]] = []
	for title, content_lines in sections:
		text = "\n".join(content_lines).strip()
		if title == "Plan" and not text:
			continue
		result.append((title, text))
	return result


def _write_cover(pdf: DietPlanPDF, payload: dict[str, Any], theme: PDFTheme) -> None:
	pdf.add_page()
	pdf.set_xy(pdf.l_margin, pdf.t_margin + 4)
	pdf.set_text_color(*theme.title_text_rgb)
	pdf.set_font(theme.font_family, "B", theme.font_size_title)
	_safe_multicell(pdf, "Personalized Nutrition Plan", line_height=12, x=pdf.l_margin)

	pdf.set_font(theme.font_family, "", theme.font_size_body)
	pdf.set_text_color(*theme.body_text_rgb)
	_safe_multicell(pdf, theme.company_name, x=pdf.l_margin)
	pdf.set_font(theme.font_family, "", theme.font_size_meta)
	pdf.set_text_color(*theme.muted_text_rgb)
	_safe_multicell(pdf, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}", x=pdf.l_margin)
	pdf.set_draw_color(*theme.header_line_rgb)
	pdf.line(pdf.l_margin, pdf.get_y() + 1, pdf.w - pdf.r_margin, pdf.get_y() + 1)

	pdf.ln(6)
	pdf.set_text_color(*theme.body_text_rgb)
	pdf.set_font(theme.font_family, "B", 12)
	pdf.cell(0, 8, "Client Profile", new_x="LMARGIN", new_y="NEXT")

	pdf.set_font(theme.font_family, "", theme.font_size_body)
	profile_lines = [
		f"Goal: {payload.get('goal', 'N/A')}",
		f"Diet preference: {payload.get('diet_preference', 'N/A')}",
		f"Activity level: {payload.get('activity_level', 'N/A')}",
		f"Age/Sex: {payload.get('age', 'N/A')} / {payload.get('sex', 'N/A')}",
		f"Height/Weight: {payload.get('height_cm', 'N/A')} cm / {payload.get('weight_kg', 'N/A')} kg",
	]
	for line in profile_lines:
		_safe_multicell(pdf, line, x=pdf.l_margin)
	pdf.ln(2)


def _write_targets(pdf: DietPlanPDF, targets: dict[str, Any], theme: PDFTheme) -> None:
	pdf.set_font(theme.font_family, "B", 12)
	pdf.set_text_color(*theme.title_text_rgb)
	pdf.cell(0, 8, "Calculated Baseline Targets", new_x="LMARGIN", new_y="NEXT")

	pdf.set_font(theme.font_family, "", theme.font_size_body)
	pdf.set_text_color(*theme.body_text_rgb)
	if not targets.get("available"):
		_safe_multicell(pdf, targets.get("reason", "Targets unavailable."), x=pdf.l_margin)
		pdf.ln(2)
		return

	rows = [
		("Target Calories", f"{targets.get('target_calories', 'N/A')} kcal"),
		("Protein", f"{targets.get('protein_g', 'N/A')} g"),
		("Fat", f"{targets.get('fat_g', 'N/A')} g"),
		("Carbohydrates", f"{targets.get('carb_g', 'N/A')} g"),
		("BMR", f"{targets.get('bmr', 'N/A')}"),
		("TDEE", f"{targets.get('tdee', 'N/A')}"),
	]
	for label, value in rows:
		pdf.set_font(theme.font_family, "B", 10)
		pdf.cell(45, 7, _sanitize_text(label))
		pdf.set_font(theme.font_family, "", 10)
		pdf.cell(0, 7, _sanitize_text(value), new_x="LMARGIN", new_y="NEXT")
	if targets.get("note"):
		pdf.ln(1)
		pdf.set_font(theme.font_family, "I", theme.font_size_meta)
		_safe_multicell(pdf, str(targets["note"]), line_height=6, x=pdf.l_margin)
	pdf.ln(3)


def _write_sections(pdf: DietPlanPDF, plan_text: str, theme: PDFTheme) -> None:
	sections = _split_sections(plan_text)
	for title, content in sections:
		pdf.set_font(theme.font_family, "B", theme.font_size_heading)
		pdf.set_text_color(*theme.title_text_rgb)
		pdf.cell(0, 8, _sanitize_text(title), new_x="LMARGIN", new_y="NEXT")
		pdf.set_draw_color(*theme.header_line_rgb)
		pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
		pdf.ln(2)

		pdf.set_font(theme.font_family, "", theme.font_size_body)
		pdf.set_text_color(*theme.body_text_rgb)
		if not content:
			_safe_multicell(pdf, "No content provided.", x=pdf.l_margin)
			pdf.ln(2)
			continue

		for raw_line in content.splitlines():
			line = _sanitize_text(raw_line.strip())
			if not line:
				pdf.ln(4)
				continue
			if line.startswith("- "):
				pdf.cell(5, 7, "-")
				_safe_multicell(pdf, line[2:])
			else:
				_safe_multicell(pdf, line, x=pdf.l_margin)
		pdf.ln(3)


def _write_footer_meta(pdf: DietPlanPDF, sources: list[str], model: str, theme: PDFTheme) -> None:
	pdf.set_font(theme.font_family, "B", 10)
	pdf.set_text_color(*theme.body_text_rgb)
	pdf.cell(0, 7, "Generation Metadata", new_x="LMARGIN", new_y="NEXT")

	pdf.set_font(theme.font_family, "", theme.font_size_meta)
	_safe_multicell(pdf, f"Model: {model}", line_height=6, x=pdf.l_margin)
	if sources:
		_safe_multicell(pdf, "Sources: " + ", ".join(sources), line_height=6, x=pdf.l_margin)


def build_plan_pdf_bytes(
	plan_text: str,
	payload: dict[str, Any],
	targets: dict[str, Any],
	sources: list[str],
	model: str,
) -> bytes:
	theme = get_pdf_theme()
	pdf = DietPlanPDF(theme)
	_write_cover(pdf, payload, theme)
	_write_targets(pdf, targets, theme)
	_write_sections(pdf, plan_text, theme)
	_write_footer_meta(pdf, sources, model, theme)
	output = pdf.output()
	if isinstance(output, str):
		return output.encode("latin-1", errors="replace")
	return bytes(output)


def save_plan_pdf(
	plan_text: str,
	payload: dict[str, Any],
	targets: dict[str, Any],
	sources: list[str],
	model: str,
	output_dir: Path | None = None,
) -> str:
	target_dir = output_dir or (Path("data") / "generated_plans")
	target_dir.mkdir(parents=True, exist_ok=True)
	timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
	file_path = target_dir / f"diet_plan_{timestamp}.pdf"
	file_path.write_bytes(build_plan_pdf_bytes(plan_text, payload, targets, sources, model))
	return str(file_path)
