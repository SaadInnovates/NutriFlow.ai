from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING

from app.db.mongodb import get_collection


class ChatStore:
	def __init__(self) -> None:
		self.collection = get_collection("chat_messages")
		self._init_db()

	def _init_db(self) -> None:
		self.collection.create_index([("user_email", ASCENDING), ("session_id", ASCENDING), ("created_at", ASCENDING)])

	def add_message(self, user_email: str, session_id: str, mode: str, role: str, message: str) -> None:
		self.collection.insert_one(
			{
				"user_email": user_email,
				"session_id": session_id,
				"mode": mode,
				"role": role,
				"message": message,
				"created_at": datetime.now(timezone.utc).isoformat(),
			}
		)

	def get_history(self, user_email: str, session_id: str, limit: int = 50) -> list[dict[str, Any]]:
		docs = self.collection.find(
			{"user_email": user_email, "session_id": session_id},
			{"_id": 0, "session_id": 1, "mode": 1, "role": 1, "message": 1, "created_at": 1},
		).sort("created_at", ASCENDING).limit(limit)
		return list(docs)

	def reset_session(self, user_email: str, session_id: str) -> int:
		result = self.collection.delete_many({"user_email": user_email, "session_id": session_id})
		return result.deleted_count

	def list_sessions(self, user_email: str, mode: str | None = None, limit: int = 30) -> list[dict[str, Any]]:
		match_stage: dict[str, Any] = {"user_email": user_email}
		if mode:
			match_stage["mode"] = mode

		pipeline = [
			{"$match": match_stage},
			{"$sort": {"created_at": -1}},
			{
				"$group": {
					"_id": {"session_id": "$session_id", "mode": "$mode"},
					"updated_at": {"$first": "$created_at"},
					"last_message": {"$first": "$message"},
					"last_role": {"$first": "$role"},
					"message_count": {"$sum": 1},
				},
			},
			{"$sort": {"updated_at": -1}},
			{"$limit": max(1, limit)},
		]

		docs = list(self.collection.aggregate(pipeline))
		return [
			{
				"session_id": item["_id"]["session_id"],
				"mode": item["_id"].get("mode") or "health",
				"updated_at": item.get("updated_at", ""),
				"last_message": item.get("last_message", ""),
				"last_role": item.get("last_role", "assistant"),
				"message_count": int(item.get("message_count", 0)),
			}
			for item in docs
		]


_CHAT_STORE: ChatStore | None = None


def get_chat_store() -> ChatStore:
	global _CHAT_STORE
	if _CHAT_STORE is None:
		_CHAT_STORE = ChatStore()
	return _CHAT_STORE
