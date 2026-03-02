import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app
from app.security import get_current_user


class TestNutritionAPI(unittest.TestCase):
	def setUp(self) -> None:
		app.dependency_overrides[get_current_user] = lambda: {
			"full_name": "Test User",
			"email": "test@example.com",
			"created_at": "2026-03-01T00:00:00+00:00",
		}
		self.client = TestClient(app)
		self.sample_payload = {
			"age": 29,
			"sex": "male",
			"height_cm": 175,
			"weight_kg": 78,
			"activity_level": "moderate",
			"goal": "fat loss",
			"diet_preference": "balanced",
			"allergies": ["peanut"],
			"medical_conditions": [],
			"budget_level": "medium",
			"cooking_time_minutes": 40,
			"disliked_foods": ["broccoli"],
			"constraints": ["high protein"],
		}

	def tearDown(self) -> None:
		app.dependency_overrides.clear()

	def test_root(self) -> None:
		response = self.client.get("/")
		self.assertEqual(response.status_code, 200)
		self.assertIn("message", response.json())

	def test_health(self) -> None:
		response = self.client.get("/api/chat/health")
		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertIn("status", body)
		self.assertIn("groq_key_configured", body)

	def test_openapi(self) -> None:
		response = self.client.get("/openapi.json")
		self.assertEqual(response.status_code, 200)

	def test_docs(self) -> None:
		response = self.client.get("/docs")
		self.assertEqual(response.status_code, 200)

	@patch("app.routes.chat.get_nutrition_agent")
	def test_plan(self, mocked_get_agent) -> None:
		mocked_get_agent.return_value.generate_plan.return_value = {
			"plan": "Summary\nDaily Calories & Macros\n7-Day Meal Plan\nGrocery List\nHabit & Adherence Tips\nSafety Notes",
			"sources": ["default_knowledge"],
			"section_confidence": {"Summary": 0.8, "7-Day Meal Plan": 0.7},
			"model": "mock-model",
			"calculated_targets": {"available": True, "target_calories": 2100},
			"debug": {"section_check": {"is_complete": True}, "length": {"words": 12}},
			"profile_warnings": [],
			"general_suggestions": ["Stay consistent."],
		}
		response = self.client.post("/api/chat/plan", json=self.sample_payload)
		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertIn("plan", body)
		self.assertIn("debug", body)
		self.assertIn("section_confidence", body)

	@patch("app.routes.chat.get_chat_store")
	@patch("app.routes.chat.get_nutrition_agent")
	def test_chat_message(self, mocked_get_agent, mocked_get_store) -> None:
		mocked_get_agent.return_value.chat_message.return_value = {
			"mode": "health",
			"assistant_message": "Hydration and sleep are key.",
		}
		mocked_get_store.return_value.get_history.return_value = []

		response = self.client.post(
			"/api/chat/message",
			json={
				"mode": "health",
				"message": "How do I improve energy?",
			},
		)
		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertIn("session_id", body)
		self.assertEqual(body["mode"], "health")
		self.assertIn("assistant_message", body)

	@patch("app.routes.chat.get_chat_store")
	@patch("app.routes.chat.get_nutrition_agent")
	def test_health_chat_diet_plan_intake(self, mocked_get_agent, mocked_get_store) -> None:
		mocked_get_store.return_value.get_history.return_value = []
		mocked_get_agent.return_value.chat_message.return_value = {
			"mode": "health",
			"assistant_message": "To create a personalized diet plan, please provide: age, sex, height (cm or inches), weight_kg, goal, locality/country",
		}
		response = self.client.post(
			"/api/chat/message",
			json={
				"mode": "health",
				"message": "create a diet plan",
			},
		)
		self.assertEqual(response.status_code, 200)
		self.assertIn("assistant_message", response.json())

	@patch("app.routes.chat.get_chat_store")
	def test_chat_history(self, mocked_get_store) -> None:
		mocked_get_store.return_value.get_history.return_value = [
			{"role": "user", "message": "hi", "mode": "health", "session_id": "abc", "created_at": "2026-03-01"},
			{"role": "assistant", "message": "hello", "mode": "health", "session_id": "abc", "created_at": "2026-03-01"},
		]

		response = self.client.get("/api/chat/history/abc")
		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertEqual(body["session_id"], "abc")
		self.assertEqual(len(body["history"]), 2)

	@patch("app.routes.chat.get_chat_store")
	def test_chat_reset(self, mocked_get_store) -> None:
		mocked_get_store.return_value.reset_session.return_value = 4

		response = self.client.post("/api/chat/reset/abc")
		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertEqual(body["status"], "reset")
		self.assertEqual(body["deleted_messages"], 4)

	@patch("app.routes.chat.get_nutrition_agent")
	def test_debug_modify(self, mocked_get_agent) -> None:
		mocked_get_agent.return_value.modify_plan.return_value = {
			"updated_plan": "Summary\nUpdated meal details",
			"plan_debug": {"section_check": {"is_complete": False, "missing": ["Safety Notes"]}},
			"calculated_targets": {"available": True, "target_calories": 2200},
			"warnings": [],
			"suggestions": ["Keep protein consistent."],
		}
		response = self.client.post(
			"/api/chat/debug/modify",
			json={
				"profile": self.sample_payload,
				"current_plan_text": "Summary\nMeal 1: eggs, toast, fruit\nMeal 2: chicken, rice, salad",
				"instruction": "Replace breakfast with oats and eggs",
			},
		)
		self.assertEqual(response.status_code, 200)
		body = response.json()
		self.assertIn("updated_plan", body)
		self.assertIn("plan_debug", body)


if __name__ == "__main__":
	unittest.main()
