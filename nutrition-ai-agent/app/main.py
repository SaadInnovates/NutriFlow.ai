from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import logging
import os
from pathlib import Path
import sys
import time

if __package__ is None or __package__ == "":
	ROOT_DIR = Path(__file__).resolve().parents[1]
	if str(ROOT_DIR) not in sys.path:
		sys.path.insert(0, str(ROOT_DIR))

from app.config import get_settings
from app.routes.auth import router as auth_router
from app.routes.chat import router as chat_router
from app.utils.secrets_guard import find_hardcoded_secrets


settings = get_settings()

app = FastAPI(
	title=settings.app_name,
	version=settings.app_version,
)

app.add_middleware(
	CORSMiddleware,
	allow_origins=settings.cors_origins,
	allow_credentials=True,
	allow_methods=["*"],
	allow_headers=["*"],
)

app.include_router(chat_router, prefix="/api")
app.include_router(auth_router, prefix="/api")


logger = logging.getLogger(__name__)
_VECTORSTORE_PRELOADED = False


@app.on_event("startup")
def startup_checks() -> None:
	global _VECTORSTORE_PRELOADED

	if settings.enable_startup_secret_scan:
		issues = find_hardcoded_secrets(Path(__file__).resolve().parents[0])
		if issues:
			raise RuntimeError(
				"Hardcoded API-like secrets detected in source files: " + ", ".join(issues)
			)

	required_values = {
		"GROQ_MODEL": settings.groq_model,
		"EMBEDDING_MODEL": settings.embedding_model,
		"NUTRITION_DOCS_DIR": str(settings.data_dir),
	}

	missing = [name for name, value in required_values.items() if not str(value).strip()]
	if missing:
		logger.warning("Missing required environment values: %s", ", ".join(missing))

	if not settings.groq_api_key:
		logger.warning("GROQ_API_KEY is empty. /api/chat/plan will return 503 until configured.")

	if settings.preload_vectorstore_on_startup and not _VECTORSTORE_PRELOADED:
		start_time = time.perf_counter()
		try:
			from app.rag.vectorstore import get_vectorstore

			vectorstore = get_vectorstore()
			_VECTORSTORE_PRELOADED = True
			elapsed = round(time.perf_counter() - start_time, 2)
			logger.info("Vectorstore preloaded successfully in %ss (chunks=%s).", elapsed, len(vectorstore.index_to_docstore_id))
		except Exception as error:
			elapsed = round(time.perf_counter() - start_time, 2)
			logger.warning("Vectorstore preload failed after %ss; will lazy-load on first request. Reason: %s", elapsed, error)

	if settings.preload_agent_on_startup:
		start_time = time.perf_counter()
		try:
			from app.agents.nutrition_agent import get_nutrition_agent

			get_nutrition_agent()
			elapsed = round(time.perf_counter() - start_time, 2)
			logger.info("Nutrition agent preloaded successfully in %ss.", elapsed)
		except Exception as error:
			elapsed = round(time.perf_counter() - start_time, 2)
			logger.warning("Nutrition agent preload failed after %ss; will initialize on first request. Reason: %s", elapsed, error)


@app.get("/")
def root() -> dict[str, str]:
	return {
		"message": "Nutrition AI backend is running",
		"docs": "/docs",
	}


if __name__ == "__main__":
	import uvicorn

	port = int(os.getenv("PORT", "8001"))
	uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=False)
