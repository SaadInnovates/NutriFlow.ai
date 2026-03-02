import re


def clean_markdown_tokens(text: str) -> str:
	if not text:
		return ""

	lines: list[str] = []
	for raw_line in text.splitlines():
		line = raw_line.strip()
		if not line:
			lines.append("")
			continue

		line = re.sub(r"^#{1,6}\s*", "", line)
		line = re.sub(r"^\*{3,}\s*", "", line)
		line = re.sub(r"\*{2,}(.*?)\*{2,}", r"\1", line)
		line = re.sub(r"\*(.*?)\*", r"\1", line)
		line = line.replace("```", "")
		if re.fullmatch(r"[-_*]{3,}", line):
			continue

		lines.append(line)

	cleaned = "\n".join(lines)
	cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
	return cleaned.strip()
