import json
import os
import re
import sys
import time
from pathlib import Path
import urllib.error
import urllib.request
from uuid import uuid4
from pypdf import PdfReader

if __package__ is None or __package__ == "":
	ROOT_DIR = Path(__file__).resolve().parents[1]
	if str(ROOT_DIR) not in sys.path:
		sys.path.insert(0, str(ROOT_DIR))

from app.utils.pdf_report import save_plan_pdf


# You can override backend URL for different host/port setups:
# set NUTRITION_API_BASE_URL, e.g. http://127.0.0.1:8001
BASE_URL = os.getenv("NUTRITION_API_BASE_URL", "http://127.0.0.1:8001").rstrip("/")
APP_ROOT = Path(__file__).resolve().parents[1]
LAST_GENERATED_PDF: str | None = None
LAST_PLAN_PAYLOAD: dict | None = None
DEBUG_SESSION_PDF: dict[str, str] = {}

# Keep menu labels in one place so option text stays consistent and duplicate items
# are not accidentally introduced during future edits.
MENU_OPTIONS = [
	"1) Backend Health",
	"2) Generate Diet Plan",
	"3) Root",
	"4) Health Chatbot",
	"5) Suggestions Chatbot",
	"6) Diet Debug Chatbot",
	"7) Open Last Generated PDF",
	"8) Exit",
]

ACTIVITY_ALIASES = {
	"high": "active",
	"very high": "very_active",
	"very-high": "very_active",
	"low": "light",
	"medium": "moderate",
}

DIET_ALIASES = {
	"low": "balanced",
	"high protein": "high_protein",
	"high-protein": "high_protein",
	"med": "mediterranean",
}

SEX_ALIASES = {
	"m": "male",
	"f": "female",
}


def call_api(method: str, path: str, payload: dict | None = None, timeout_seconds: int = 30) -> tuple[int, str]:
	url = f"{BASE_URL}{path}"
	data = json.dumps(payload).encode("utf-8") if payload is not None else None
	headers = {"Content-Type": "application/json"}
	request = urllib.request.Request(url, data=data, headers=headers, method=method)
	try:
		with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
			return response.status, response.read().decode("utf-8")
	except urllib.error.HTTPError as error:
		return error.code, error.read().decode("utf-8")
	except Exception as error:
		return 0, str(error)


def _parse_height_inches(raw: str) -> float | None:
	value = raw.strip().lower().replace('"', "").replace("inches", "in").replace("inch", "in")
	if not value:
		return None

	feet_inch_match = re.match(r"^(\d+)\s*(?:ft|')\s*(\d{1,2})?$", value)
	if feet_inch_match:
		feet = int(feet_inch_match.group(1))
		inches = int(feet_inch_match.group(2) or 0)
		return float((feet * 12) + inches)

	if value.endswith("in"):
		numeric = value[:-2].strip()
		if numeric.replace(".", "", 1).isdigit():
			return float(numeric)

	if value.replace(".", "", 1).isdigit():
		numeric = float(value)
		if 24 <= numeric <= 96:
			return numeric

	return None


def save_plan_as_pdf(plan_result: dict, payload: dict | None) -> str:
	return save_plan_pdf(
		plan_text=plan_result.get("plan", ""),
		payload=payload or {},
		targets=plan_result.get("calculated_targets", {}),
		sources=plan_result.get("sources", []),
		model=plan_result.get("model", "unknown"),
	)


def open_last_generated_pdf() -> None:
	global LAST_GENERATED_PDF
	if not LAST_GENERATED_PDF:
		print("No generated PDF yet. Create a diet plan and save it first.\n")
		return
	path = Path(LAST_GENERATED_PDF)
	if not path.exists():
		print(f"Saved PDF not found: {LAST_GENERATED_PDF}\n")
		return
	os.startfile(str(path.resolve()))
	print(f"Opened PDF: {path}\n")


def sample_payload() -> dict:
	return {
		"age": 29,
		"sex": "male",
		"height_cm": 175,
		"height_in": None,
		"weight_kg": 78,
		"activity_level": "moderate",
		"goal": "fat loss",
		"locality": "Pakistan",
		"diet_preference": "balanced",
		"allergies": ["peanut"],
		"medical_conditions": [],
		"budget_level": "medium",
		"cooking_time_minutes": 40,
		"disliked_foods": ["broccoli"],
		"constraints": ["high protein"],
	}


def interactive_payload() -> dict:
	print("Enter profile values (press Enter to use defaults).")
	payload = sample_payload()
	age_raw = input(f"Age [{payload['age']}]: ").strip()
	if age_raw:
		payload["age"] = int(age_raw)

	sex_raw = input(f"Sex [{payload['sex']}] (male/female/other): ").strip().lower()
	if sex_raw:
		payload["sex"] = SEX_ALIASES.get(sex_raw, sex_raw)

	height_unit_raw = input("Height unit [cm] (cm/in or e.g. 5'7): ").strip().lower()
	height_unit = "cm"
	direct_height_in = None
	if not height_unit_raw:
		height_unit = "cm"
	elif height_unit_raw in {"cm", "in"}:
		height_unit = height_unit_raw
	else:
		direct_height_in = _parse_height_inches(height_unit_raw)
		if direct_height_in is not None:
			height_unit = "in"
		else:
			print("Invalid height unit. Using cm.")
	height_default = payload["height_cm"] if height_unit == "cm" else round(payload["height_cm"] / 2.54, 1)
	height_prompt_default = direct_height_in if direct_height_in is not None else height_default
	height_raw = input(f"Height ({height_unit}) [{height_prompt_default}]: ").strip()
	if height_unit == "in":
		if height_raw:
			parsed_height_in = _parse_height_inches(height_raw)
			if parsed_height_in is None:
				payload["height_in"] = float(height_raw)
			else:
				payload["height_in"] = parsed_height_in
		elif direct_height_in is not None:
			payload["height_in"] = direct_height_in
		else:
			payload["height_in"] = round(payload["height_cm"] / 2.54, 1)
		if payload["height_in"]:
			payload["height_cm"] = round(payload["height_in"] * 2.54, 2)
	else:
		if height_raw:
			payload["height_cm"] = float(height_raw)
		payload["height_in"] = round(payload["height_cm"] / 2.54, 1)

	weight_raw = input(f"Weight (kg) [{payload['weight_kg']}]: ").strip()
	if weight_raw:
		payload["weight_kg"] = float(weight_raw)

	payload["goal"] = input(f"Goal [{payload['goal']}]: ").strip() or payload["goal"]
	locality = input(f"Locality/Country [{payload['locality']}]: ").strip()
	if locality:
		payload["locality"] = locality
	diet = input(
		f"Diet preference [{payload['diet_preference']}] "
		"(balanced/vegetarian/vegan/keto/paleo/mediterranean/high_protein): "
	).strip()
	if diet:
		payload["diet_preference"] = DIET_ALIASES.get(diet.lower(), diet.lower())
	activity = input(f"Activity level [{payload['activity_level']}]: ").strip()
	if activity:
		payload["activity_level"] = ACTIVITY_ALIASES.get(activity.lower(), activity.lower())
	constraints = input("Constraints (comma separated, optional): ").strip()
	if constraints:
		payload["constraints"] = [item.strip() for item in constraints.split(",") if item.strip()]
	return payload


def _read_pdf_text(file_path: str) -> str:
	reader = PdfReader(file_path)
	return "\n".join((page.extract_text() or "") for page in reader.pages).strip()


def endpoint_exists(path: str) -> bool:
	status, content = call_api("GET", "/openapi.json")
	if status >= 400:
		return False
	try:
		parsed = json.loads(content)
		return path in parsed.get("paths", {})
	except Exception:
		return False


def backend_is_reachable() -> bool:
	# Retry briefly to avoid false negatives while the backend is still starting up.
	for _ in range(4):
		status, _ = call_api("GET", "/api/chat/health", timeout_seconds=6)
		if status == 200:
			return True
		time.sleep(0.6)
	return False


def print_backend_unreachable() -> None:
	print("Backend is not reachable at http://127.0.0.1:8001.")
	print("Start the server first:")
	print(f"  cd \"{APP_ROOT}\"")
	print("  uvicorn app.main:app --host 127.0.0.1 --port 8001")
	print()
	print("Or run from parent folder:")
	print("  uvicorn app.main:app --app-dir nutrition-ai-agent --host 127.0.0.1 --port 8001")
	print()


def print_history(session_id: str) -> None:
	status, content = call_api("GET", f"/api/chat/history/{session_id}")
	if status >= 400:
		print_response(status, content)
		return
	parsed = json.loads(content)
	history = parsed.get("history", [])
	if not history:
		print("No chat history yet.\n")
		return
	print()
	for item in history:
		role = item.get("role", "unknown").capitalize()
		message = item.get("message", "")
		print(f"{role}: {message}")
	print()


def reset_history(session_id: str) -> None:
	status, content = call_api("POST", f"/api/chat/reset/{session_id}")
	if status >= 400:
		print_response(status, content)
		return
	parsed = json.loads(content)
	print(f"Session reset. Deleted messages: {parsed.get('deleted_messages', 0)}\n")


def run_chat_mode(mode: str) -> None:
	if not endpoint_exists("/api/chat/message"):
		print("Chat endpoint is not available on the running backend.")
		print("Restart uvicorn so latest routes are loaded, then try again.\n")
		return

	print(f"Starting {mode} chat mode. Type /exit to return.")
	print("Commands: /history, /reset, /session, /exit")
	existing_session = input("Enter existing session ID to resume (or press Enter for new): ").strip()
	session_id = existing_session or str(uuid4())
	print(f"Session ID: {session_id}")
	profile = interactive_payload() if mode in {"suggestions"} else None
	plan_text = ""

	while True:
		user_message = input("You: ").strip()
		if not user_message:
			continue
		if user_message == "/exit":
			print("Leaving chat mode.\n")
			break
		if user_message == "/history":
			print_history(session_id)
			continue
		if user_message == "/reset":
			reset_history(session_id)
			continue
		if user_message == "/session":
			new_session = input("Enter session ID to switch to: ").strip()
			if new_session:
				session_id = new_session
				print(f"Switched to session: {session_id}\n")
			else:
				print("Session ID cannot be empty.\n")
			continue

		payload = {
			"session_id": session_id,
			"mode": mode,
			"message": user_message,
		}
		if mode == "health" and ("diet plan" in user_message.lower() or "meal plan" in user_message.lower()):
			print("To create a diet plan, please share profile details.")
			profile = interactive_payload()
		if profile is not None:
			payload["profile"] = profile
		if plan_text:
			payload["plan_text"] = plan_text

		status, content = call_api("POST", "/api/chat/message", payload, timeout_seconds=90)
		if status >= 400:
			print_response(status, content)
			continue

		parsed = json.loads(content)
		print(f"Assistant: {parsed.get('assistant_message', '')}\n")


def run_debug_chat_mode() -> None:
	if not endpoint_exists("/api/chat/debug/modify"):
		print("Debug modify endpoint is not available on the running backend.")
		print("Restart uvicorn so latest routes are loaded, then try again.\n")
		return

	print("Starting debug chat mode.")
	print("What do you want to change in your diet plan?")
	print("Commands: /history, /session, /exit")
	session_id = input("Enter existing session ID (or press Enter for new): ").strip() or str(uuid4())
	print(f"Session ID: {session_id}")
	profile = interactive_payload()
	pdf_path = input("Upload current diet plan PDF path: ").strip().strip('"')
	if not pdf_path or not Path(pdf_path).exists() or Path(pdf_path).suffix.lower() != ".pdf":
		print("Error: valid PDF path is required for debug mode.\n")
		return

	current_plan_text = _read_pdf_text(pdf_path)
	if not current_plan_text:
		print("Error: uploaded PDF has no readable text.\n")
		return

	while True:
		user_message = input("You (change request): ").strip()
		if not user_message:
			continue
		if user_message == "/exit":
			print("Leaving debug chat mode.\n")
			break
		if user_message == "/history":
			print_history(session_id)
			continue
		if user_message == "/session":
			session_id = input("Enter session ID to switch to: ").strip() or session_id
			print(f"Current session: {session_id}\n")
			continue

		status, content = call_api(
			"POST",
			"/api/chat/debug/modify",
			{
				"profile": profile,
				"current_plan_text": current_plan_text,
				"instruction": user_message,
			},
			timeout_seconds=120,
		)
		if status >= 400:
			print_response(status, content)
			continue

		parsed = json.loads(content)
		updated_plan = parsed.get("updated_plan", "")
		current_plan_text = updated_plan or current_plan_text
		print("Assistant (updated plan):")
		print(updated_plan)
		print()

		regen = input("Regenerate PDF for this session? (y/n): ").strip().lower()
		if regen == "y":
			old_pdf = DEBUG_SESSION_PDF.get(session_id)
			if old_pdf and Path(old_pdf).exists():
				Path(old_pdf).unlink(missing_ok=True)
			plan_result = {
				"plan": current_plan_text,
				"sources": ["user_uploaded_pdf_modified"],
				"model": "debug-modifier",
				"calculated_targets": parsed.get("calculated_targets", {}),
			}
			saved_path = save_plan_as_pdf(plan_result, profile)
			DEBUG_SESSION_PDF[session_id] = saved_path
			print(f"Saved regenerated PDF: {saved_path}\n")


def print_response(status: int, content: str) -> None:
	print()
	if status == 0:
		print_backend_unreachable()
		return

	try:
		parsed = json.loads(content)
	except Exception:
		parsed = content

	if status >= 400:
		if isinstance(parsed, dict) and "detail" in parsed:
			detail = parsed["detail"]
			if isinstance(detail, list):
				print("Error:")
				for item in detail:
					field = ".".join(str(loc) for loc in item.get("loc", []) if loc != "body")
					message = item.get("msg", "Invalid input")
					if field:
						print(f"- {field}: {message}")
					else:
						print(f"- {message}")
			else:
				print(f"Error: {detail}")
		else:
			print(f"Error: {parsed}")
		print()
		return

	if isinstance(parsed, dict):
		if "plan" in parsed:
			global LAST_GENERATED_PDF
			global LAST_PLAN_PAYLOAD
			print(parsed["plan"])
			print()
			if parsed.get("section_confidence"):
				print("Section confidence:")
				for section, score in parsed["section_confidence"].items():
					percent = int(float(score) * 100)
					print(f"- {section}: {percent}%")
				print()
			if parsed.get("evidence_notes"):
				print("Evidence notes:")
				for item in parsed["evidence_notes"][:5]:
					source = item.get("source", "unknown")
					excerpt = item.get("excerpt", "")
					print(f"- [{source}] {excerpt}")
				print()
			if parsed.get("section_attribution"):
				print("Section attribution:")
				for section, notes in parsed["section_attribution"].items():
					if not notes:
						continue
					first_note = notes[0]
					print(f"- {section}: {first_note.get('source', 'unknown')}")
				print()
			if parsed.get("profile_warnings"):
				for item in parsed["profile_warnings"]:
					print(f"- {item}")
				print()
			if parsed.get("general_suggestions"):
				for item in parsed["general_suggestions"]:
					print(f"- {item}")
			print()
			download_choice = input("Download this plan as PDF? (y/n): ").strip().lower()
			if download_choice == "y":
				saved_path = save_plan_as_pdf(parsed, LAST_PLAN_PAYLOAD)
				LAST_GENERATED_PDF = saved_path
				print(f"Saved PDF: {saved_path}")
		elif "calculated_targets" in parsed and "suggestions" in parsed and "warnings" in parsed:
			targets = parsed["calculated_targets"]
			if targets.get("available"):
				print(
					"Targets: "
					f"Calories {targets.get('target_calories')}, "
					f"Protein {targets.get('protein_g')}g, "
					f"Fat {targets.get('fat_g')}g, "
					f"Carbs {targets.get('carb_g')}g"
				)
			else:
				print("Targets unavailable: missing required profile fields.")
			print()
			if parsed["warnings"]:
				for item in parsed["warnings"]:
					print(f"- {item}")
			if parsed["suggestions"]:
				for item in parsed["suggestions"]:
					print(f"- {item}")
			if parsed.get("plan_debug"):
				report = parsed["plan_debug"]
				missing = report.get("section_check", {}).get("missing", [])
				if missing:
					print("Missing plan sections from uploaded PDF:")
					for section in missing:
						print(f"- {section}")
			if not parsed["warnings"] and not parsed["suggestions"]:
				print("No warnings or suggestions right now.")
		elif "status" in parsed and "groq_key_configured" in parsed:
			key_text = "configured" if parsed["groq_key_configured"] else "not configured"
			print(f"Service is {parsed['status']}. Groq key is {key_text}.")
		elif "message" in parsed and "docs" in parsed:
			print(f"{parsed['message']}")
			print(f"Docs: {BASE_URL}{parsed['docs']}")
		elif "suggestions" in parsed and "warnings" in parsed:
			if parsed["suggestions"]:
				for item in parsed["suggestions"]:
					print(f"- {item}")
			if parsed["warnings"]:
				for item in parsed["warnings"]:
					print(f"- {item}")
			if not parsed["suggestions"] and not parsed["warnings"]:
				print("No suggestions or warnings right now.")
		else:
			print(json.dumps(parsed, indent=2))
	else:
		print(parsed)
	print()


def run_menu() -> None:
	while True:
		print("Nutrition Agent Terminal Interface")
		for item in MENU_OPTIONS:
			print(item)
		choice = input("Choose an option: ").strip()

		if choice in {"2", "3", "4", "5", "6"} and not backend_is_reachable():
			print()
			print_backend_unreachable()
			continue

		if choice == "1":
			status, content = call_api("GET", "/api/chat/health")
			print_response(status, content)
		elif choice == "2":
			global LAST_PLAN_PAYLOAD
			payload = interactive_payload()
			LAST_PLAN_PAYLOAD = payload
			status, content = call_api("POST", "/api/chat/plan", payload, timeout_seconds=120)
			print_response(status, content)
		elif choice == "3":
			status, content = call_api("GET", "/")
			print_response(status, content)
		elif choice == "4":
			run_chat_mode("health")
		elif choice == "5":
			run_chat_mode("suggestions")
		elif choice == "6":
			run_debug_chat_mode()
		elif choice == "7":
			open_last_generated_pdf()
		elif choice == "8":
			print("Bye.")
			break
		else:
			print("Invalid option.\n")


if __name__ == "__main__":
	run_menu()
