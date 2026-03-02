from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import logging
from secrets import token_urlsafe
from threading import Lock
import time
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr, Field
from pymongo import ASCENDING

from app.config import get_settings
from app.db.mongodb import get_collection
from app.security import create_access_token, get_current_user, get_password_hash, verify_password
from app.utils.audit import audit_event
from app.utils.mailer import send_email


router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger(__name__)
_RATE_LIMIT_LOCK = Lock()
_RATE_LIMIT_BUCKETS: dict[str, list[float]] = {}


class RegisterRequest(BaseModel):
	full_name: str = Field(..., min_length=2, max_length=100)
	email: EmailStr
	password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
	email: EmailStr
	password: str = Field(..., min_length=8, max_length=128)


class UserResponse(BaseModel):
	full_name: str
	email: EmailStr
	created_at: str
	is_verified: bool = False


class TokenResponse(BaseModel):
	access_token: str
	token_type: str = "bearer"
	user: UserResponse


class GroqKeyRequest(BaseModel):
	api_key: str = Field(..., min_length=10, max_length=200)


class GroqKeyStatusResponse(BaseModel):
	configured: bool


class UpdateProfileRequest(BaseModel):
	full_name: str | None = Field(default=None, min_length=2, max_length=100)
	age: int | None = Field(default=None, ge=1, le=120)
	sex: str | None = None
	height_cm: float | None = Field(default=None, gt=0)
	weight_kg: float | None = Field(default=None, gt=0)
	activity_level: str | None = None
	goal: str | None = Field(default=None, min_length=2, max_length=120)
	locality: str | None = Field(default=None, min_length=2, max_length=120)
	diet_preference: str | None = None
	allergies: list[str] = Field(default_factory=list)
	medical_conditions: list[str] = Field(default_factory=list)
	budget_level: str | None = None
	cooking_time_minutes: int | None = Field(default=None, ge=5, le=240)
	disliked_foods: list[str] = Field(default_factory=list)
	constraints: list[str] = Field(default_factory=list)


class UserProfileResponse(BaseModel):
	profile: dict


class VerifyRequest(BaseModel):
	email: EmailStr


class VerifyStatusResponse(BaseModel):
	verified: bool


class VerifyConfirmRequest(BaseModel):
	email: EmailStr
	token: str = Field(..., min_length=6, max_length=256)


class ForgotPasswordRequest(BaseModel):
	email: EmailStr


class ResetPasswordRequest(BaseModel):
	email: EmailStr
	token: str = Field(..., min_length=6, max_length=256)
	new_password: str = Field(..., min_length=8, max_length=128)


class ActionResponse(BaseModel):
	message: str


def _users_collection():
	users = get_collection("users")
	users.create_index([("email", ASCENDING)], unique=True)
	return users


def _token_hash(token: str) -> str:
	return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_token_pair() -> tuple[str, str]:
	raw = token_urlsafe(32)
	return raw, _token_hash(raw)


def _token_matches(raw_token: str, stored_hash: str) -> bool:
	return hmac.compare_digest(_token_hash(raw_token), stored_hash)


def _parse_expiry(value: str | None) -> datetime | None:
	if not value:
		return None
	try:
		parsed = datetime.fromisoformat(value)
	except ValueError:
		return None
	if parsed.tzinfo is None:
		return parsed.replace(tzinfo=timezone.utc)
	return parsed


def _request_ip(request: Request | None) -> str:
	if request and request.client and request.client.host:
		return request.client.host
	return "unknown"


def _enforce_rate_limit(action: str, identifier: str, max_requests: int, window_seconds: int) -> None:
	if max_requests <= 0 or window_seconds <= 0:
		return
	now = time.time()
	key = f"{action}:{identifier.lower().strip() or 'unknown'}"
	with _RATE_LIMIT_LOCK:
		hits = _RATE_LIMIT_BUCKETS.get(key, [])
		hits = [timestamp for timestamp in hits if now - timestamp < window_seconds]
		if len(hits) >= max_requests:
			raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")
		hits.append(now)
		_RATE_LIMIT_BUCKETS[key] = hits


def _build_frontend_link(path: str, email: str, token: str) -> str:
	settings = get_settings()
	base = settings.frontend_base_url.rstrip("/")
	query = urlencode({"email": email, "token": token})
	return f"{base}{path}?{query}"


def _send_verify_email(email: str, token: str) -> None:
	verify_link = _build_frontend_link("/verify-email", email, token)
	subject = "Verify your Nutrition AI email"
	text_body = (
		"Welcome to Nutrition AI.\n\n"
		"Verify your email by opening this link:\n"
		f"{verify_link}\n\n"
		"If you did not create this account, you can ignore this email."
	)
	html_body = (
		"<p>Welcome to Nutrition AI.</p>"
		"<p>Please verify your email by clicking the link below:</p>"
		f"<p><a href=\"{verify_link}\">Verify Email</a></p>"
		"<p>If you did not create this account, you can ignore this email.</p>"
	)
	send_email(to_email=email, subject=subject, text_body=text_body, html_body=html_body)


def _send_reset_email(email: str, token: str) -> None:
	reset_link = _build_frontend_link("/forgot-password", email, token)
	subject = "Reset your Nutrition AI password"
	text_body = (
		"We received a request to reset your password.\n\n"
		"Use this link to set a new password:\n"
		f"{reset_link}\n\n"
		"If you did not request this, you can ignore this email."
	)
	html_body = (
		"<p>We received a request to reset your password.</p>"
		"<p>Use this link to set a new password:</p>"
		f"<p><a href=\"{reset_link}\">Reset Password</a></p>"
		"<p>If you did not request this, you can ignore this email.</p>"
	)
	send_email(to_email=email, subject=subject, text_body=text_body, html_body=html_body)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register_user(payload: RegisterRequest) -> UserResponse:
	users = _users_collection()
	existing = users.find_one({"email": payload.email.lower()})
	if existing:
		audit_event(event="auth.register", success=False, email=payload.email.lower(), detail="email_already_registered")
		raise HTTPException(status_code=409, detail="Email is already registered.")

	now = datetime.now(timezone.utc).isoformat()
	raw_verify_token, verify_hash = _new_token_pair()
	user_doc = {
		"full_name": payload.full_name.strip(),
		"email": payload.email.lower(),
		"password": get_password_hash(payload.password),
		"created_at": now,
		"is_verified": False,
		"verification_token_hash": verify_hash,
		"verification_token_expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
		"profile": {},
	}
	inserted_user = users.insert_one(user_doc)

	try:
		_send_verify_email(user_doc["email"], raw_verify_token)
	except Exception as error:
		logger.warning("Failed to send verification email for %s: %s", user_doc["email"], error)
		users.delete_one({"_id": inserted_user.inserted_id})
		audit_event(event="auth.register", success=False, email=user_doc["email"], detail="verification_email_send_failed")
		raise HTTPException(status_code=503, detail="Failed to send verification email. Please try again later.") from error

	audit_event(event="auth.register", success=True, email=user_doc["email"])

	return UserResponse(
		full_name=user_doc["full_name"],
		email=user_doc["email"],
		created_at=user_doc["created_at"],
		is_verified=user_doc["is_verified"],
	)


@router.post("/login", response_model=TokenResponse)
def login_user(payload: LoginRequest, request: Request) -> TokenResponse:
	users = _users_collection()
	user = users.find_one({"email": payload.email.lower()})
	if not user or not verify_password(payload.password, user.get("password", "")):
		audit_event(event="auth.login", success=False, email=payload.email.lower(), ip=_request_ip(request), detail="invalid_credentials")
		raise HTTPException(status_code=401, detail="Invalid email or password.")
	if not user.get("is_verified", False):
		audit_event(event="auth.login", success=False, email=payload.email.lower(), ip=_request_ip(request), detail="email_not_verified")
		raise HTTPException(status_code=403, detail="Please verify your email before logging in.")

	token = create_access_token(subject=user["email"])
	audit_event(event="auth.login", success=True, email=user["email"], ip=_request_ip(request))
	return TokenResponse(
		access_token=token,
		user=UserResponse(
			full_name=user["full_name"],
			email=user["email"],
			created_at=user["created_at"],
			is_verified=bool(user.get("is_verified", False)),
		),
	)


@router.post("/token", response_model=TokenResponse)
def login_token(request: Request, form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
	users = _users_collection()
	user = users.find_one({"email": form_data.username.lower()})
	if not user or not verify_password(form_data.password, user.get("password", "")):
		audit_event(event="auth.login_token", success=False, email=form_data.username.lower(), ip=_request_ip(request), detail="invalid_credentials")
		raise HTTPException(status_code=401, detail="Invalid email or password.")
	if not user.get("is_verified", False):
		audit_event(event="auth.login_token", success=False, email=form_data.username.lower(), ip=_request_ip(request), detail="email_not_verified")
		raise HTTPException(status_code=403, detail="Please verify your email before logging in.")

	token = create_access_token(subject=user["email"])
	audit_event(event="auth.login_token", success=True, email=user["email"], ip=_request_ip(request))
	return TokenResponse(
		access_token=token,
		user=UserResponse(
			full_name=user["full_name"],
			email=user["email"],
			created_at=user["created_at"],
			is_verified=bool(user.get("is_verified", False)),
		),
	)


@router.get("/me", response_model=UserResponse)
def get_me(current_user: dict = Depends(get_current_user)) -> UserResponse:
	return UserResponse(**current_user)


@router.get("/profile", response_model=UserProfileResponse)
def get_profile(current_user: dict = Depends(get_current_user)) -> UserProfileResponse:
	return UserProfileResponse(profile=current_user.get("profile", {}))


@router.put("/profile", response_model=UserProfileResponse)
def update_profile(payload: UpdateProfileRequest, current_user: dict = Depends(get_current_user)) -> UserProfileResponse:
	users = _users_collection()
	incoming = payload.model_dump()
	profile_updates = {k: v for k, v in incoming.items() if k != "full_name" and v is not None}

	existing_profile = current_user.get("profile", {}) or {}
	merged_profile = {**existing_profile, **profile_updates}
	update_fields: dict = {"profile": merged_profile}
	if payload.full_name:
		update_fields["full_name"] = payload.full_name.strip()

	users.update_one({"email": current_user["email"]}, {"$set": update_fields})
	return UserProfileResponse(profile=merged_profile)


@router.delete("/me", response_model=ActionResponse)
def delete_me(current_user: dict = Depends(get_current_user)) -> ActionResponse:
	users = _users_collection()
	users.delete_one({"email": current_user["email"]})
	audit_event(event="auth.delete_account", success=True, email=current_user["email"])
	return ActionResponse(message="Account deleted successfully.")


@router.put("/groq-key", response_model=GroqKeyStatusResponse)
def set_groq_key(payload: GroqKeyRequest, current_user: dict = Depends(get_current_user)) -> GroqKeyStatusResponse:
	users = _users_collection()
	users.update_one(
		{"email": current_user["email"]},
		{"$set": {"groq_api_key": payload.api_key.strip()}},
	)
	return GroqKeyStatusResponse(configured=True)


@router.get("/groq-key", response_model=GroqKeyStatusResponse)
def get_groq_key_status(current_user: dict = Depends(get_current_user)) -> GroqKeyStatusResponse:
	users = _users_collection()
	user = users.find_one({"email": current_user["email"]}, {"_id": 0, "groq_api_key": 1}) or {}
	return GroqKeyStatusResponse(configured=bool((user.get("groq_api_key") or "").strip()))


@router.post("/verify/request", response_model=ActionResponse)
def request_email_verification(payload: VerifyRequest, request: Request) -> ActionResponse:
	users = _users_collection()
	settings = get_settings()
	client_ip = _request_ip(request)
	_enforce_rate_limit("verify_request_ip", client_ip, settings.auth_verify_request_limit, settings.auth_rate_limit_window_seconds)
	_enforce_rate_limit("verify_request_email", payload.email.lower(), settings.auth_verify_request_limit, settings.auth_rate_limit_window_seconds)

	user = users.find_one({"email": payload.email.lower()})
	if not user:
		audit_event(event="auth.verify_request", success=False, email=payload.email.lower(), ip=client_ip, detail="user_not_found")
		return ActionResponse(message="If the account exists, a verification email has been sent.")

	if user.get("is_verified", False):
		audit_event(event="auth.verify_request", success=True, email=payload.email.lower(), ip=client_ip, detail="already_verified")
		return ActionResponse(message="If the account exists, a verification email has been sent.")

	raw_verify_token, verify_hash = _new_token_pair()
	users.update_one(
		{"email": payload.email.lower()},
		{
			"$set": {
				"verification_token_hash": verify_hash,
				"verification_token_expires_at": (datetime.now(timezone.utc) + timedelta(hours=24)).isoformat(),
			}
		},
	)

	try:
		_send_verify_email(payload.email.lower(), raw_verify_token)
	except Exception as error:
		logger.warning("Failed to send verification email for %s: %s", payload.email.lower(), error)
		audit_event(event="auth.verify_request", success=False, email=payload.email.lower(), ip=client_ip, detail="email_send_failed")
		raise HTTPException(status_code=503, detail="Failed to send verification email. Please try again later.") from error

	audit_event(event="auth.verify_request", success=True, email=payload.email.lower(), ip=client_ip)
	return ActionResponse(message="If the account exists, a verification email has been sent.")


@router.post("/verify/status", response_model=VerifyStatusResponse)
def get_email_verification_status(payload: VerifyRequest, request: Request) -> VerifyStatusResponse:
	users = _users_collection()
	client_ip = _request_ip(request)
	user = users.find_one({"email": payload.email.lower()}, {"_id": 0, "is_verified": 1})
	verified = bool((user or {}).get("is_verified", False))
	audit_event(event="auth.verify_status", success=True, email=payload.email.lower(), ip=client_ip, metadata={"verified": verified})
	return VerifyStatusResponse(verified=verified)


@router.post("/verify/confirm", response_model=ActionResponse)
def confirm_email_verification(payload: VerifyConfirmRequest, request: Request) -> ActionResponse:
	users = _users_collection()
	settings = get_settings()
	client_ip = _request_ip(request)
	_enforce_rate_limit("verify_confirm_ip", client_ip, settings.auth_verify_confirm_limit, settings.auth_rate_limit_window_seconds)
	_enforce_rate_limit("verify_confirm_email", payload.email.lower(), settings.auth_verify_confirm_limit, settings.auth_rate_limit_window_seconds)

	user = users.find_one({"email": payload.email.lower()})
	if not user:
		audit_event(event="auth.verify_confirm", success=False, email=payload.email.lower(), ip=client_ip, detail="user_not_found")
		raise HTTPException(status_code=404, detail="User not found.")
	if user.get("is_verified", False):
		audit_event(event="auth.verify_confirm", success=True, email=payload.email.lower(), ip=client_ip, detail="already_verified")
		return ActionResponse(message="Email verified successfully.")

	expires_at = _parse_expiry(user.get("verification_token_expires_at"))
	stored_hash = user.get("verification_token_hash") or ""
	provided = payload.token.strip()
	if not stored_hash or not _token_matches(provided, stored_hash):
		audit_event(event="auth.verify_confirm", success=False, email=payload.email.lower(), ip=client_ip, detail="invalid_token")
		raise HTTPException(status_code=400, detail="Invalid verification token.")
	if expires_at and datetime.now(timezone.utc) > expires_at:
		audit_event(event="auth.verify_confirm", success=False, email=payload.email.lower(), ip=client_ip, detail="token_expired")
		raise HTTPException(status_code=400, detail="Verification token expired.")

	users.update_one(
		{"email": payload.email.lower()},
		{
			"$set": {"is_verified": True},
			"$unset": {"verification_token_hash": "", "verification_token_expires_at": ""},
		},
	)
	audit_event(event="auth.verify_confirm", success=True, email=payload.email.lower(), ip=client_ip)
	return ActionResponse(message="Email verified successfully.")


@router.post("/forgot-password", response_model=ActionResponse)
def forgot_password(payload: ForgotPasswordRequest, request: Request) -> ActionResponse:
	users = _users_collection()
	settings = get_settings()
	client_ip = _request_ip(request)
	_enforce_rate_limit("forgot_request_ip", client_ip, settings.auth_forgot_request_limit, settings.auth_rate_limit_window_seconds)
	_enforce_rate_limit("forgot_request_email", payload.email.lower(), settings.auth_forgot_request_limit, settings.auth_rate_limit_window_seconds)

	user = users.find_one({"email": payload.email.lower()})
	if not user:
		audit_event(event="auth.forgot_password", success=False, email=payload.email.lower(), ip=client_ip, detail="user_not_found")
		return ActionResponse(message="If the account exists, a reset email has been sent.")

	raw_reset_token, reset_hash = _new_token_pair()
	users.update_one(
		{"email": payload.email.lower()},
		{
			"$set": {
				"reset_token_hash": reset_hash,
				"reset_token_expires_at": (datetime.now(timezone.utc) + timedelta(minutes=30)).isoformat(),
			}
		},
	)

	try:
		_send_reset_email(payload.email.lower(), raw_reset_token)
	except Exception as error:
		logger.warning("Failed to send reset email for %s: %s", payload.email.lower(), error)
		audit_event(event="auth.forgot_password", success=False, email=payload.email.lower(), ip=client_ip, detail="email_send_failed")
		raise HTTPException(status_code=503, detail="Failed to send reset email. Please try again later.") from error

	audit_event(event="auth.forgot_password", success=True, email=payload.email.lower(), ip=client_ip)
	return ActionResponse(message="If the account exists, a reset email has been sent.")


@router.post("/reset-password", response_model=ActionResponse)
def reset_password(payload: ResetPasswordRequest, request: Request) -> ActionResponse:
	users = _users_collection()
	settings = get_settings()
	client_ip = _request_ip(request)
	_enforce_rate_limit("reset_password_ip", client_ip, settings.auth_reset_password_limit, settings.auth_rate_limit_window_seconds)
	_enforce_rate_limit("reset_password_email", payload.email.lower(), settings.auth_reset_password_limit, settings.auth_rate_limit_window_seconds)

	user = users.find_one({"email": payload.email.lower()})
	if not user:
		audit_event(event="auth.reset_password", success=False, email=payload.email.lower(), ip=client_ip, detail="user_not_found")
		raise HTTPException(status_code=404, detail="User not found.")

	expires_at = _parse_expiry(user.get("reset_token_expires_at"))
	stored_hash = user.get("reset_token_hash") or ""
	provided = payload.token.strip()
	if not stored_hash or not _token_matches(provided, stored_hash):
		audit_event(event="auth.reset_password", success=False, email=payload.email.lower(), ip=client_ip, detail="invalid_token")
		raise HTTPException(status_code=400, detail="Invalid reset token.")
	if expires_at and datetime.now(timezone.utc) > expires_at:
		audit_event(event="auth.reset_password", success=False, email=payload.email.lower(), ip=client_ip, detail="token_expired")
		raise HTTPException(status_code=400, detail="Reset token expired.")

	users.update_one(
		{"email": payload.email.lower()},
		{
			"$set": {"password": get_password_hash(payload.new_password)},
			"$unset": {"reset_token_hash": "", "reset_token_expires_at": ""},
		},
	)
	audit_event(event="auth.reset_password", success=True, email=payload.email.lower(), ip=client_ip)
	return ActionResponse(message="Password reset successful. You can now log in.")
