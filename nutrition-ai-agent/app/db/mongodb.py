from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.database import Database

from app.config import get_settings


_CLIENT: MongoClient | None = None


def get_mongo_client() -> MongoClient:
	global _CLIENT
	if _CLIENT is None:
		settings = get_settings()
		_CLIENT = MongoClient(settings.mongodb_uri)
	return _CLIENT


def get_mongo_database() -> Database:
	settings = get_settings()
	return get_mongo_client()[settings.mongodb_db_name]


def get_collection(name: str) -> Collection:
	return get_mongo_database()[name]
