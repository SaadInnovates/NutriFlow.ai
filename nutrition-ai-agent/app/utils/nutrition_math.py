from typing import Any


def _activity_factor(activity_level: str) -> float:
	mapping = {
		"sedentary": 1.2,
		"light": 1.375,
		"moderate": 1.55,
		"active": 1.725,
		"very_active": 1.9,
	}
	return mapping.get(activity_level.lower(), 1.55)


def _goal_adjustment(goal: str) -> float:
	goal_text = goal.lower()
	if any(term in goal_text for term in ["fat loss", "weight loss", "cut"]):
		return -0.15
	if any(term in goal_text for term in ["muscle gain", "bulk", "weight gain"]):
		return 0.1
	return 0.0


def calculate_targets(payload: dict[str, Any]) -> dict[str, Any]:
	age = payload.get("age")
	sex = (payload.get("sex") or "").lower()
	height_cm = payload.get("height_cm")
	weight_kg = payload.get("weight_kg")
	activity_level = payload.get("activity_level", "moderate")
	goal = payload.get("goal", "")

	if not all([age, sex, height_cm, weight_kg]):
		return {
			"available": False,
			"reason": "Missing age, sex, height_cm, or weight_kg.",
		}

	sex_bias = 5 if sex in {"male", "m"} else -161
	bmr = (10 * float(weight_kg)) + (6.25 * float(height_cm)) - (5 * float(age)) + sex_bias
	tdee = bmr * _activity_factor(activity_level)
	target_calories = tdee * (1 + _goal_adjustment(goal))

	protein_g = float(weight_kg) * 1.8
	fat_g = float(weight_kg) * 0.8
	remaining_calories = max(target_calories - ((protein_g * 4) + (fat_g * 9)), 0)
	carb_g = remaining_calories / 4

	return {
		"available": True,
		"bmr": round(bmr),
		"tdee": round(tdee),
		"target_calories": round(target_calories),
		"protein_g": round(protein_g),
		"fat_g": round(fat_g),
		"carb_g": round(carb_g),
		"note": "Baseline estimate; tailor with a registered dietitian for clinical needs.",
	}
