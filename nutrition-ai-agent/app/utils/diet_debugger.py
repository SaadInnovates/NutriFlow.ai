from typing import Any


def profile_warnings(payload: dict[str, Any]) -> list[str]:
	warnings: list[str] = []
	allergies = {item.lower() for item in payload.get("allergies", [])}
	medical_conditions = {item.lower() for item in payload.get("medical_conditions", [])}
	goal = (payload.get("goal") or "").lower()
	preference = (payload.get("diet_preference") or "").lower()

	if "keto" in preference and any(term in medical_conditions for term in {"kidney disease", "ckd"}):
		warnings.append("Keto with kidney conditions may require medical supervision.")
	if "fat loss" in goal and payload.get("cooking_time_minutes", 0) < 20:
		warnings.append("Low cooking time may reduce dietary adherence; use meal prep batching.")
	if {"peanut", "tree nut"}.intersection(allergies) and "high_protein" in preference:
		warnings.append("Review protein source choices to avoid nut-based products.")
	if "diabetes" in medical_conditions and "keto" not in preference:
		warnings.append("Prioritize lower glycemic carbs and tighter carbohydrate distribution.")

	return warnings


def plan_debug_report(plan_text: str) -> dict[str, Any]:
	required_sections = [
		"Summary",
		"Daily Calories & Macros",
		"7-Day Meal Plan",
		"Grocery List",
		"Habit & Adherence Tips",
		"Safety Notes",
	]

	missing_sections = [section for section in required_sections if section not in plan_text]
	return {
		"section_check": {
			"required": required_sections,
			"missing": missing_sections,
			"is_complete": len(missing_sections) == 0,
		},
		"length": {
			"characters": len(plan_text),
			"words": len(plan_text.split()),
		},
	}


def general_suggestions(payload: dict[str, Any]) -> list[str]:
	suggestions = [
		"Build each main meal around a protein source and at least one high-fiber food.",
		"Keep hydration consistent across the day instead of drinking large amounts at once.",
		"Use a weekly meal template to reduce decision fatigue and improve adherence.",
	]

	goal = (payload.get("goal") or "").lower()
	activity_level = (payload.get("activity_level") or "moderate").lower()
	budget_level = (payload.get("budget_level") or "medium").lower()

	if "fat loss" in goal or "weight loss" in goal:
		suggestions.append("Prioritize high-volume, low-calorie meals and keep protein high for satiety.")
	if "muscle" in goal or "gain" in goal:
		suggestions.append("Spread protein across 3-5 feedings to support muscle protein synthesis.")
	if activity_level in {"active", "very_active"}:
		suggestions.append("Increase pre/post-workout carbohydrate timing to support training quality.")
	if budget_level == "low":
		suggestions.append("Use budget staples like eggs, lentils, oats, seasonal produce, and frozen vegetables.")

	return suggestions
