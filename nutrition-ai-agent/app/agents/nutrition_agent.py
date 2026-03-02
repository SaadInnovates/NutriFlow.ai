from functools import lru_cache
import hashlib
import json
import re
import time
from typing import Any

from app.config import get_settings
from app.prompts.chat_prompts import (
	build_debug_chat_prompt,
	build_debug_modify_prompt,
	build_health_chat_prompt,
	build_recipe_prompt,
	build_suggestions_chat_prompt,
)
from app.prompts.diet_prompt import build_diet_planner_prompt
from app.utils.diet_debugger import general_suggestions, plan_debug_report, profile_warnings
from app.utils.nutrition_math import calculate_targets
from app.utils.response_format import clean_markdown_tokens


class NutritionAgent:
	SECTION_HINTS = {
		"Summary": ["summary", "overview", "goal", "target"],
		"Daily Calories & Macros": ["calorie", "macro", "protein", "carb", "fat", "bmr", "tdee"],
		"7-Day Meal Plan": ["meal", "breakfast", "lunch", "dinner", "snack", "day"],
		"Grocery List": ["grocery", "shopping", "ingredients", "produce", "staple"],
		"Habit & Adherence Tips": ["habit", "adherence", "routine", "consistency", "prep"],
		"Safety Notes": ["safety", "risk", "allergy", "medical", "condition", "consult"],
	}

	def __init__(self, api_key: str | None = None) -> None:
		settings = get_settings()
		resolved_api_key = (api_key or settings.groq_api_key).strip()
		if not resolved_api_key:
			raise ValueError("GROQ_API_KEY is missing. Add it to your environment or .env file.")

		from langchain_groq import ChatGroq

		self.settings = settings
		self.llm = ChatGroq(
			api_key=resolved_api_key,
			model=settings.groq_model,
			temperature=settings.temperature,
			max_tokens=settings.max_tokens,
		)
		from app.rag.retriever import get_retriever
		from langchain_core.runnables import RunnableLambda

		self.retriever = get_retriever()
		self.context_runnable = RunnableLambda(self._prepare_context_bundle)
		self.plan_runnable = RunnableLambda(self._to_prompt_inputs) | RunnableLambda(build_diet_planner_prompt) | self.llm
		self.health_chat_runnable = RunnableLambda(self._to_health_chat_inputs) | RunnableLambda(build_health_chat_prompt) | self.llm
		self.suggestions_chat_runnable = RunnableLambda(self._to_suggestions_chat_inputs) | RunnableLambda(build_suggestions_chat_prompt) | self.llm
		self.debug_chat_runnable = RunnableLambda(self._to_debug_chat_inputs) | RunnableLambda(build_debug_chat_prompt) | self.llm
		self.debug_modify_runnable = RunnableLambda(self._to_debug_modify_inputs) | RunnableLambda(build_debug_modify_prompt) | self.llm
		self.recipe_runnable = RunnableLambda(self._to_recipe_inputs) | RunnableLambda(build_recipe_prompt) | self.llm
		self.plan_cache: dict[str, tuple[float, dict[str, Any]]] = {}
		self._api_key = resolved_api_key

	def _plan_cache_key(self, payload: dict[str, Any]) -> str:
		serialized = json.dumps(payload, sort_keys=True, default=str)
		return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

	def _prune_plan_cache(self, now: float) -> None:
		ttl = self.settings.plan_cache_ttl_seconds
		if ttl <= 0 or not self.plan_cache:
			return
		expired_keys = [key for key, (created_at, _) in self.plan_cache.items() if now - created_at > ttl]
		for key in expired_keys:
			self.plan_cache.pop(key, None)

	def _trim_context(self, context: str) -> str:
		max_chars = max(500, int(self.settings.plan_context_max_chars))
		if len(context) <= max_chars:
			return context
		return context[:max_chars].rsplit(" ", 1)[0]

	def _build_query(self, payload: dict[str, Any]) -> str:
		return (
			f"Goal: {payload.get('goal', '')}; "
			f"locality: {payload.get('locality', '')}; "
			f"diet preference: {payload.get('diet_preference', '')}; "
			f"medical conditions: {payload.get('medical_conditions', '')}; "
			f"constraints: {payload.get('constraints', '')}"
		)

	def _prepare_context_bundle(self, payload: dict[str, Any]) -> dict[str, Any]:
		query = self._build_query(payload)
		docs = self.retriever.invoke(query)
		context = "\n\n".join(doc.page_content for doc in docs)
		context = self._trim_context(context)
		calculated_targets = calculate_targets(payload)
		return {
			"payload": payload,
			"docs": docs,
			"context": context,
			"calculated_targets": calculated_targets,
		}

	def _to_prompt_inputs(self, bundle: dict[str, Any]) -> dict[str, Any]:
		payload = bundle["payload"]
		return {
			"context": bundle["context"],
			"age": payload.get("age", "N/A"),
			"sex": payload.get("sex", "N/A"),
			"height_cm": payload.get("height_cm", "N/A"),
			"weight_kg": payload.get("weight_kg", "N/A"),
			"activity_level": payload.get("activity_level", "N/A"),
			"goal": payload.get("goal", "N/A"),
			"locality": payload.get("locality", "Global"),
			"diet_preference": payload.get("diet_preference", "N/A"),
			"allergies": ", ".join(payload.get("allergies", [])) or "None",
			"medical_conditions": ", ".join(payload.get("medical_conditions", [])) or "None",
			"budget_level": payload.get("budget_level", "N/A"),
			"cooking_time_minutes": payload.get("cooking_time_minutes", "N/A"),
			"disliked_foods": ", ".join(payload.get("disliked_foods", [])) or "None",
			"constraints": ", ".join(payload.get("constraints", [])) or "None",
			"calculated_targets": bundle["calculated_targets"],
		}

	def _history_to_text(self, history: list[dict[str, Any]]) -> str:
		if not history:
			return "No prior messages."
		last_messages = history[-12:]
		return "\n".join(f"{item['role']}: {item['message']}" for item in last_messages)

	def _to_health_chat_inputs(self, bundle: dict[str, Any]) -> dict[str, Any]:
		return {
			"history": self._history_to_text(bundle.get("history", [])),
			"message": bundle["message"],
		}

	def _to_suggestions_chat_inputs(self, bundle: dict[str, Any]) -> dict[str, Any]:
		profile = {
			"goal": bundle.get("profile", {}).get("goal", "N/A"),
			"activity_level": bundle.get("profile", {}).get("activity_level", "N/A"),
			"locality": bundle.get("profile", {}).get("locality", "Global"),
			"diet_preference": bundle.get("profile", {}).get("diet_preference", "N/A"),
			"budget_level": bundle.get("profile", {}).get("budget_level", "N/A"),
		}
		return {
			"history": self._history_to_text(bundle.get("history", [])),
			"message": bundle["message"],
			"profile": profile,
		}

	def _to_debug_chat_inputs(self, bundle: dict[str, Any]) -> dict[str, Any]:
		return {
			"history": self._history_to_text(bundle.get("history", [])),
			"message": bundle["message"],
			"plan_text": bundle.get("plan_text", "No plan snippet provided."),
		}

	def _to_debug_modify_inputs(self, bundle: dict[str, Any]) -> dict[str, Any]:
		profile = bundle.get("profile", {})
		return {
			"instruction": bundle["instruction"],
			"plan_text": bundle.get("plan_text", ""),
			"profile": profile,
			"locality": profile.get("locality", "Global"),
		}

	def _to_recipe_inputs(self, bundle: dict[str, Any]) -> dict[str, Any]:
		profile = bundle.get("profile", {})
		return {
			"dish_request": bundle.get("dish_request", ""),
			"cuisine": bundle.get("cuisine", "Any"),
			"servings": bundle.get("servings", 2),
			"notes": bundle.get("notes", ""),
			"profile": {
				"goal": profile.get("goal", "N/A"),
				"activity_level": profile.get("activity_level", "N/A"),
				"diet_preference": profile.get("diet_preference", "N/A"),
				"allergies": profile.get("allergies", []),
				"medical_conditions": profile.get("medical_conditions", []),
				"budget_level": profile.get("budget_level", "N/A"),
				"locality": profile.get("locality", "Global"),
			},
		}

	def _locality_food_suggestions(self, locality: str) -> list[str]:
		loc = (locality or "").lower()
		if any(key in loc for key in {"pakistan", "india", "bangladesh"}):
			return [
				"Use regional staples like dal, chickpeas, roti, rice, seasonal sabzi, yogurt, and grilled meats.",
				"Prefer baked/grilled kebab or tikka styles over deep-fried preparations.",
			]
		if any(key in loc for key in {"china", "chinese"}):
			return [
				"Use stir-fried vegetables, tofu, eggs, fish, lean meats, and steamed rice portions.",
				"Prefer steamed/boiled dishes and moderate oil/sodium in sauces.",
			]
		if any(key in loc for key in {"middle east", "uae", "saudi", "turkey"}):
			return [
				"Use hummus, lentils, grilled fish/chicken, tabbouleh, and whole-grain pita in balanced portions.",
			]
		return ["Prioritize local seasonal produce and minimally processed staple foods for adherence and affordability."]

	def _is_diet_plan_intent(self, message: str) -> bool:
		text = message.lower()
		return "diet plan" in text or "meal plan" in text or "make me a plan" in text

	def _missing_plan_fields(self, profile: dict[str, Any]) -> list[str]:
		missing: list[str] = []
		if not profile.get("age"):
			missing.append("age")
		if not profile.get("sex"):
			missing.append("sex")
		height_cm = profile.get("height_cm")
		height_in = profile.get("height_in")
		if not height_cm and not height_in:
			missing.append("height (cm or inches)")
		if not profile.get("weight_kg"):
			missing.append("weight_kg")
		if not profile.get("goal"):
			missing.append("goal")
		if not profile.get("locality"):
			missing.append("locality/country")
		return missing

	def _is_relevant_query(self, message: str, mode: str) -> bool:
		text = message.lower().strip()
		if not text:
			return False

		nutrition_terms = {
			"diet",
			"nutrition",
			"meal",
			"meals",
			"recipe",
			"recipes",
			"snack",
			"snacks",
			"breakfast",
			"lunch",
			"dinner",
			"calorie",
			"calories",
			"macro",
			"macros",
			"protein",
			"carb",
			"carbs",
			"fat",
			"fats",
			"fiber",
			"hydrate",
			"weight",
			"gain",
			"loss",
			"diabetes",
			"portion",
			"portions",
			"food",
			"foods",
			"eat",
			"eating",
			"drink",
			"drinks",
			"health",
			"healthy",
			"sleep",
		}
		food_examples = {
			"egg", "eggs", "chicken", "fish", "rice", "oats", "bread", "dal", "lentils", "milk", "yogurt",
			"banana", "apple", "salad", "paneer", "tofu", "beans", "nuts", "dates", "smoothie", "soup",
		}
		query_starters = ("can i", "should i", "what should i", "what can i", "is it ok", "suggest", "recommend")

		if mode == "debug":
			return True

		if mode in {"suggestions", "health"}:
			if any(term in text for term in nutrition_terms):
				return True
			if any(food in text for food in food_examples):
				return True
			if text.startswith(query_starters):
				return True
			if len(text.split()) <= 8 and "?" in text:
				return True
			return False
		return True

	def _build_section_attribution(self, evidence_notes: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
		section_attribution: dict[str, list[dict[str, str]]] = {section: [] for section in self.SECTION_HINTS}
		for section, hints in self.SECTION_HINTS.items():
			scored_notes: list[tuple[int, dict[str, str]]] = []
			for note in evidence_notes:
				excerpt = (note.get("excerpt") or "").lower()
				hint_hits = sum(1 for hint in hints if hint in excerpt)
				if hint_hits > 0:
					scored_notes.append((hint_hits, note))
			scored_notes.sort(key=lambda value: value[0], reverse=True)
			section_attribution[section] = [note for _, note in scored_notes[:3]]
		return section_attribution

	def _tokenize(self, text: str) -> set[str]:
		return set(re.findall(r"[a-zA-Z]{3,}", text.lower()))

	def _extract_plan_sections(self, plan_text: str) -> dict[str, str]:
		sections = {name: "" for name in self.SECTION_HINTS}
		current_section = "Summary"
		for raw_line in plan_text.splitlines():
			line = raw_line.replace("*", "").replace(":", "").strip()
			for section_name in self.SECTION_HINTS:
				if line.lower() == section_name.lower():
					current_section = section_name
					break
			else:
				sections[current_section] = (sections[current_section] + " " + raw_line.strip()).strip()
		return sections

	def _build_advanced_section_attribution(
		self,
		plan_text: str,
		evidence_notes: list[dict[str, str]],
	) -> tuple[dict[str, list[dict[str, str]]], dict[str, float]]:
		plan_sections = self._extract_plan_sections(plan_text)
		result: dict[str, list[dict[str, str]]] = {section: [] for section in self.SECTION_HINTS}
		confidence: dict[str, float] = {section: 0.0 for section in self.SECTION_HINTS}

		for section, section_text in plan_sections.items():
			section_tokens = self._tokenize(section_text)
			hints = self.SECTION_HINTS[section]
			scored: list[tuple[float, dict[str, str]]] = []
			for note in evidence_notes:
				excerpt = note.get("excerpt", "")
				excerpt_tokens = self._tokenize(excerpt)
				overlap = len(section_tokens.intersection(excerpt_tokens))
				hint_hits = sum(1 for hint in hints if hint in excerpt.lower())
				score = (1.6 * hint_hits) + (0.4 * overlap)
				if score > 0:
					scored.append((score, note))

			scored.sort(key=lambda value: value[0], reverse=True)
			result[section] = [note for _, note in scored[:3]]
			if scored:
				top_score = scored[0][0]
				confidence[section] = round(min(1.0, top_score / 8.0), 3)

		# Fallback for sparse sections
		fallback = self._build_section_attribution(evidence_notes)
		for section in result:
			if not result[section]:
				result[section] = fallback.get(section, [])
				if result[section]:
					confidence[section] = 0.25
		return result, confidence

	def _extract_finish_reason(self, response: Any) -> str:
		metadata = getattr(response, "response_metadata", {}) or {}
		return str(metadata.get("finish_reason") or metadata.get("stop_reason") or "").lower()

	def _extract_text(self, response: Any) -> str:
		content = getattr(response, "content", response)
		return content if isinstance(content, str) else str(content)

	def _invoke_complete(self, runnable: Any, payload: dict[str, Any]) -> str:
		response = runnable.invoke(payload)
		text = self._extract_text(response)
		finish_reason = self._extract_finish_reason(response)
		attempts = 0

		while finish_reason == "length" and attempts < max(0, self.settings.max_continuation_attempts):
			continuation_prompt = (
				"Continue exactly from where the previous response ended. "
				"Do not repeat earlier content. Return only the continuation text.\n\n"
				f"Previous response:\n{text}"
			)
			followup = self.llm.invoke(continuation_prompt)
			followup_text = self._extract_text(followup).strip()
			if not followup_text:
				break
			text = f"{text.rstrip()}\n{followup_text}"
			finish_reason = self._extract_finish_reason(followup)
			attempts += 1

		return clean_markdown_tokens(text)

	def generate_plan(self, payload: dict[str, Any]) -> dict[str, Any]:
		started = time.perf_counter()
		cache_key = self._plan_cache_key(payload)
		now = time.time()
		if self.settings.enable_plan_cache:
			self._prune_plan_cache(now)
			cached = self.plan_cache.get(cache_key)
			if cached is not None:
				_, cached_result = cached
				result = dict(cached_result)
				result["cache_hit"] = True
				result["latency_ms"] = int((time.perf_counter() - started) * 1000)
				return result

		bundle = self.context_runnable.invoke(payload)
		text = self._invoke_complete(self.plan_runnable, bundle)

		sources = [doc.metadata.get("source", "unknown") for doc in bundle["docs"]]
		evidence_notes = [
			{
				"source": doc.metadata.get("source", "unknown"),
				"excerpt": (doc.page_content or "").replace("\n", " ").strip()[:220],
			}
			for doc in bundle["docs"]
		]
		section_attribution, section_confidence = self._build_advanced_section_attribution(text, evidence_notes)
		result = {
			"plan": text,
			"sources": sorted(set(sources)),
			"evidence_notes": evidence_notes,
			"section_attribution": section_attribution,
			"section_confidence": section_confidence,
			"model": self.settings.groq_model,
			"calculated_targets": bundle["calculated_targets"],
			"debug": plan_debug_report(text),
			"profile_warnings": profile_warnings(payload),
			"general_suggestions": general_suggestions(payload),
		}
		if self.settings.enable_plan_cache:
			self.plan_cache[cache_key] = (now, dict(result))
		result["cache_hit"] = False
		result["latency_ms"] = int((time.perf_counter() - started) * 1000)
		return result

	def modify_plan(self, payload: dict[str, Any], current_plan_text: str, instruction: str) -> dict[str, Any]:
		updated_text = self._invoke_complete(
			self.debug_modify_runnable,
			{
				"profile": payload,
				"plan_text": current_plan_text,
				"instruction": instruction,
			}
		)
		return {
			"updated_plan": updated_text,
			"plan_debug": plan_debug_report(updated_text),
			"calculated_targets": calculate_targets(payload),
			"warnings": profile_warnings(payload),
			"suggestions": general_suggestions(payload) + self._locality_food_suggestions(payload.get("locality", "")),
		}

	def generate_recipe(
		self,
		dish_request: str,
		profile: dict[str, Any] | None = None,
		cuisine: str = "Any",
		servings: int = 2,
		notes: str = "",
	) -> dict[str, str]:
		recipe_text = self._invoke_complete(
			self.recipe_runnable,
			{
				"dish_request": dish_request,
				"profile": profile or {},
				"cuisine": cuisine,
				"servings": servings,
				"notes": notes,
			},
		)
		return {"recipe": recipe_text}

	def chat_message(
		self,
		mode: str,
		message: str,
		history: list[dict[str, Any]],
		profile: dict[str, Any] | None = None,
		plan_text: str | None = None,
	) -> dict[str, Any]:
		bundle = {
			"message": message,
			"history": history,
			"profile": profile or {},
			"plan_text": plan_text or "",
		}

		mode_key = mode.lower().strip()
		if not self._is_relevant_query(message, mode_key):
			return {
				"mode": mode_key,
				"assistant_message": (
					"I can only help with nutrition, diet planning, health-related food guidance, "
					"and diet debugging. Please ask a relevant nutrition question."
				),
			}

		profile_payload = profile or {}
		if mode_key == "health" and self._is_diet_plan_intent(message):
			missing = self._missing_plan_fields(profile_payload)
			if missing:
				return {
					"mode": mode_key,
					"assistant_message": (
						"To create a personalized diet plan, please provide: " + ", ".join(missing)
					),
				}
			result = self.generate_plan(profile_payload)
			return {
				"mode": mode_key,
				"assistant_message": result["plan"],
			}

		if mode_key == "health":
			text = self._invoke_complete(self.health_chat_runnable, bundle)
		elif mode_key == "suggestions":
			text = self._invoke_complete(self.suggestions_chat_runnable, bundle)
		elif mode_key == "debug":
			text = self._invoke_complete(self.debug_chat_runnable, bundle)
		elif mode_key == "recipe":
			text = self._invoke_complete(
				self.recipe_runnable,
				{
					"dish_request": message,
					"profile": profile or {},
					"cuisine": (profile or {}).get("locality", "Any"),
					"servings": 2,
					"notes": "",
				},
			)
		elif mode_key == "plan":
			text = self._invoke_complete(self.plan_runnable, self.context_runnable.invoke(profile or {}))
		else:
			raise ValueError(f"Unsupported chat mode: {mode}")

		return {
			"mode": mode_key,
			"assistant_message": text,
		}


@lru_cache
def get_nutrition_agent(api_key: str | None = None) -> NutritionAgent:
	normalized_key = (api_key or "").strip() or None
	return NutritionAgent(api_key=normalized_key)
