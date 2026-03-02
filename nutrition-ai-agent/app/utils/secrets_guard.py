from pathlib import Path
import re


SECRET_PATTERNS = [
	re.compile(r"gsk_[A-Za-z0-9]{20,}"),
	re.compile(r"sk-[A-Za-z0-9]{20,}"),
]


def find_hardcoded_secrets(scan_root: Path) -> list[str]:
	issues: list[str] = []
	for path in scan_root.rglob("*.py"):
		text = path.read_text(encoding="utf-8", errors="ignore")
		for pattern in SECRET_PATTERNS:
			if pattern.search(text):
				issues.append(str(path))
				break
	return sorted(set(issues))
