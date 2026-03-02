from functools import lru_cache
from pathlib import Path
import os

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "nutrition_docs"


class Settings:
	def __init__(self) -> None:
		load_dotenv(BASE_DIR / ".env")

		def _as_bool(name: str, default: bool) -> bool:
			value = os.getenv(name)
			if value is None:
				return default
			return value.strip().lower() in {"1", "true", "yes", "on"}

		self.app_name = os.getenv("APP_NAME", "Nutrition AI Agent")
		self.app_version = os.getenv("APP_VERSION", "0.1.0")

		self.groq_api_key = os.getenv("GROQ_API_KEY", "")
		self.groq_model = os.getenv("GROQ_MODEL", "llama-3.1-8b-instant")
		self.temperature = float(os.getenv("MODEL_TEMPERATURE", "0.2"))
		self.max_tokens = int(os.getenv("MODEL_MAX_TOKENS", "1800"))
		self.max_continuation_attempts = int(os.getenv("MODEL_MAX_CONTINUATION_ATTEMPTS", "1"))

		self.embedding_model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
		self.chunk_size = int(os.getenv("CHUNK_SIZE", "700"))
		self.chunk_overlap = int(os.getenv("CHUNK_OVERLAP", "120"))
		self.retrieval_k = int(os.getenv("RETRIEVAL_K", "3"))
		self.plan_context_max_chars = int(os.getenv("PLAN_CONTEXT_MAX_CHARS", "2200"))
		self.enable_plan_cache = _as_bool("ENABLE_PLAN_CACHE", True)
		self.plan_cache_ttl_seconds = int(os.getenv("PLAN_CACHE_TTL_SECONDS", "900"))
		self.preload_vectorstore_on_startup = _as_bool("PRELOAD_VECTORSTORE_ON_STARTUP", True)
		self.preload_agent_on_startup = _as_bool("PRELOAD_AGENT_ON_STARTUP", True)
		self.enable_startup_secret_scan = _as_bool("ENABLE_STARTUP_SECRET_SCAN", False)

		self.mongodb_uri = os.getenv("MONGODB_URI", "mongodb://127.0.0.1:27017")
		self.mongodb_db_name = os.getenv("MONGODB_DB_NAME", "nutrition_ai")

		self.jwt_secret_key = os.getenv("JWT_SECRET_KEY", "change-me-in-production")
		self.jwt_algorithm = os.getenv("JWT_ALGORITHM", "HS256")
		self.jwt_access_token_expire_minutes = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "120"))
		self.auth_rate_limit_window_seconds = int(os.getenv("AUTH_RATE_LIMIT_WINDOW_SECONDS", "900"))
		self.auth_verify_request_limit = int(os.getenv("AUTH_VERIFY_REQUEST_LIMIT", "5"))
		self.auth_forgot_request_limit = int(os.getenv("AUTH_FORGOT_REQUEST_LIMIT", "5"))
		self.auth_verify_confirm_limit = int(os.getenv("AUTH_VERIFY_CONFIRM_LIMIT", "10"))
		self.auth_reset_password_limit = int(os.getenv("AUTH_RESET_PASSWORD_LIMIT", "10"))

		self.frontend_base_url = os.getenv("FRONTEND_BASE_URL", "http://127.0.0.1:5173")
		self.smtp_host = os.getenv("SMTP_HOST", "")
		self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
		raw_smtp_username = os.getenv("SMTP_USERNAME", "").strip()
		self.smtp_password = os.getenv("SMTP_PASSWORD", "").replace(" ", "").strip()
		self.smtp_from_email = os.getenv("SMTP_FROM_EMAIL", "").strip()
		self.smtp_username = raw_smtp_username or self.smtp_from_email
		self.smtp_from_name = os.getenv("SMTP_FROM_NAME", "Nutrition AI")
		self.smtp_use_tls = _as_bool("SMTP_USE_TLS", True)
		self.smtp_use_ssl = _as_bool("SMTP_USE_SSL", False)

		self.data_dir = Path(os.getenv("NUTRITION_DOCS_DIR", str(DATA_DIR)))

		cors_origins_raw = os.getenv("CORS_ORIGINS", "*")
		self.cors_origins = [origin.strip() for origin in cors_origins_raw.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
	return Settings()
