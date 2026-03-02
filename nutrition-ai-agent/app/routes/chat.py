import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Literal
from uuid import uuid4
from pypdf import PdfReader

from app.agents.nutrition_agent import get_nutrition_agent
from app.config import get_settings
from app.security import get_current_user
from app.utils.chat_store import get_chat_store
from app.utils.pdf_report import build_plan_pdf_bytes


router = APIRouter(prefix="/chat", tags=["chat"])


class DietPlanRequest(BaseModel):
	age: int | None = Field(default=None, ge=1, le=120)
	sex: Literal["male", "female", "other"] | None = None
	height_cm: float | None = Field(default=None, gt=0)
	height_in: float | None = Field(default=None, gt=0)
	weight_kg: float | None = Field(default=None, gt=0)
	activity_level: Literal["sedentary", "light", "moderate", "active", "very_active"] = "moderate"
	goal: str = Field(..., min_length=3)
	locality: str = "Global"
	diet_preference: Literal["balanced", "vegetarian", "vegan", "keto", "paleo", "mediterranean", "high_protein"] = "balanced"
	allergies: list[str] = Field(default_factory=list)
	medical_conditions: list[str] = Field(default_factory=list)
	budget_level: Literal["low", "medium", "high"] = "medium"
	cooking_time_minutes: int = Field(default=45, ge=5, le=240)
	disliked_foods: list[str] = Field(default_factory=list)
	constraints: list[str] = Field(default_factory=list)


class DietPlanResponse(BaseModel):
	plan: str
	cache_hit: bool = False
	latency_ms: int | None = None
	sources: list[str]
	evidence_notes: list[dict] = Field(default_factory=list)
	section_attribution: dict[str, list[dict]] = Field(default_factory=dict)
	section_confidence: dict[str, float] = Field(default_factory=dict)
	model: str
	calculated_targets: dict
	debug: dict
	profile_warnings: list[str]
	general_suggestions: list[str]


class ChatMessageRequest(BaseModel):
	session_id: str | None = None
	mode: Literal["health", "suggestions", "debug", "plan", "recipe"] = "health"
	message: str = Field(..., min_length=1)
	profile: DietPlanRequest | None = None
	plan_text: str | None = None


class ChatMessageResponse(BaseModel):
	session_id: str
	mode: str
	assistant_message: str


class RecipeRequest(BaseModel):
	dish_request: str = Field(..., min_length=2, max_length=200)
	servings: int = Field(default=2, ge=1, le=12)
	cuisine: str = Field(default="Any", min_length=1, max_length=80)
	notes: str | None = Field(default=None, max_length=500)
	profile: DietPlanRequest | None = None


class RecipeResponse(BaseModel):
	recipe: str


class SessionSummary(BaseModel):
	session_id: str
	mode: str
	updated_at: str
	last_message: str
	last_role: str
	message_count: int


class SessionListResponse(BaseModel):
	sessions: list[SessionSummary]


class ChatHistoryResponse(BaseModel):
	session_id: str
	history: list[dict]


class DebugModifyRequest(BaseModel):
	profile: DietPlanRequest
	current_plan_text: str = Field(..., min_length=20)
	instruction: str = Field(..., min_length=3)


class DebugModifyResponse(BaseModel):
	updated_plan: str
	plan_debug: dict
	calculated_targets: dict
	warnings: list[str]
	suggestions: list[str]


class PlanPdfRequest(BaseModel):
	plan_text: str = Field(..., min_length=20)
	payload: DietPlanRequest
	calculated_targets: dict = Field(default_factory=dict)
	sources: list[str] = Field(default_factory=list)
	model: str = "unknown"


def _normalize_payload(payload: dict) -> dict:
	if not payload.get("height_cm") and payload.get("height_in"):
		payload["height_cm"] = round(float(payload["height_in"]) * 2.54, 2)
	payload["locality"] = payload.get("locality") or "Global"
	return payload


def _resolve_user_groq_key(current_user: dict) -> str:
	return (current_user.get("groq_api_key") or "").strip()


@router.get("/health")
def health(current_user: dict = Depends(get_current_user)) -> dict[str, str | bool]:
	settings = get_settings()
	user_key_configured = bool(_resolve_user_groq_key(current_user))
	env_key_configured = bool(settings.groq_api_key)
	return {
		"status": "ok",
		"groq_key_configured": user_key_configured or env_key_configured,
		"user_groq_key_configured": user_key_configured,
		"env_groq_key_configured": env_key_configured,
	}


@router.post("/plan", response_model=DietPlanResponse)
def create_diet_plan(payload: DietPlanRequest, _current_user: dict = Depends(get_current_user)) -> DietPlanResponse:
	try:
		user_groq_key = _resolve_user_groq_key(_current_user)
		agent = get_nutrition_agent(user_groq_key)
		normalized_payload = _normalize_payload(payload.model_dump())
		result = agent.generate_plan(normalized_payload)
		return DietPlanResponse(**result)
	except ValueError as error:
		raise HTTPException(status_code=503, detail=str(error)) from error
	except Exception as error:
		raise HTTPException(status_code=500, detail="Failed to generate a diet plan.") from error


@router.post("/message", response_model=ChatMessageResponse)
def chat_message(payload: ChatMessageRequest, current_user: dict = Depends(get_current_user)) -> ChatMessageResponse:
	try:
		user_groq_key = _resolve_user_groq_key(current_user)
		agent = get_nutrition_agent(user_groq_key)
		store = get_chat_store()
		session_id = payload.session_id or str(uuid4())
		history = store.get_history(current_user["email"], session_id)

		profile_dict = payload.profile.model_dump() if payload.profile else {}
		profile_dict = _normalize_payload(profile_dict) if profile_dict else {}
		result = agent.chat_message(
			mode=payload.mode,
			message=payload.message,
			history=history,
			profile=profile_dict,
			plan_text=payload.plan_text,
		)

		store.add_message(current_user["email"], session_id, payload.mode, "user", payload.message)
		store.add_message(current_user["email"], session_id, payload.mode, "assistant", result["assistant_message"])

		return ChatMessageResponse(
			session_id=session_id,
			mode=result["mode"],
			assistant_message=result["assistant_message"],
		)
	except ValueError as error:
		detail = str(error)
		status_code = 503 if "GROQ_API_KEY" in detail else 400
		raise HTTPException(status_code=status_code, detail=detail) from error
	except Exception as error:
		raise HTTPException(status_code=500, detail="Failed to process chat message.") from error


@router.post("/debug/modify", response_model=DebugModifyResponse)
def modify_debug_plan(payload: DebugModifyRequest, _current_user: dict = Depends(get_current_user)) -> DebugModifyResponse:
	try:
		user_groq_key = _resolve_user_groq_key(_current_user)
		agent = get_nutrition_agent(user_groq_key)
		normalized_profile = _normalize_payload(payload.profile.model_dump())
		result = agent.modify_plan(
			payload=normalized_profile,
			current_plan_text=payload.current_plan_text,
			instruction=payload.instruction,
		)
		return DebugModifyResponse(**result)
	except ValueError as error:
		raise HTTPException(status_code=503, detail=str(error)) from error
	except Exception as error:
		raise HTTPException(status_code=500, detail="Failed to modify diet plan.") from error


@router.post("/plan/pdf")
def generate_plan_pdf(payload: PlanPdfRequest, _current_user: dict = Depends(get_current_user)) -> StreamingResponse:
	try:
		normalized_payload = _normalize_payload(payload.payload.model_dump())
		pdf_bytes = build_plan_pdf_bytes(
			plan_text=payload.plan_text,
			payload=normalized_payload,
			targets=payload.calculated_targets,
			sources=payload.sources,
			model=payload.model,
		)
		stream = io.BytesIO(pdf_bytes)
		return StreamingResponse(
			stream,
			media_type="application/pdf",
			headers={"Content-Disposition": 'attachment; filename="diet_plan.pdf"'},
		)
	except Exception as error:
		raise HTTPException(status_code=500, detail="Failed to generate PDF.") from error


@router.post("/debug/extract-plan")
async def extract_plan_from_pdf(
	file: UploadFile = File(...),
	_current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
	if not file.filename or not file.filename.lower().endswith(".pdf"):
		raise HTTPException(status_code=400, detail="Please upload a valid PDF file.")

	content = await file.read()
	if not content:
		raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")

	try:
		reader = PdfReader(io.BytesIO(content))
		plan_text = "\n".join((page.extract_text() or "") for page in reader.pages).strip()
	except Exception as error:
		raise HTTPException(status_code=400, detail="Unable to read text from PDF.") from error

	if not plan_text:
		raise HTTPException(status_code=400, detail="Uploaded PDF has no readable text.")

	return {"plan_text": plan_text}


@router.get("/history/{session_id}", response_model=ChatHistoryResponse)
def chat_history(session_id: str, current_user: dict = Depends(get_current_user)) -> ChatHistoryResponse:
	store = get_chat_store()
	return ChatHistoryResponse(session_id=session_id, history=store.get_history(current_user["email"], session_id))


@router.get("/sessions", response_model=SessionListResponse)
def list_chat_sessions(mode: Literal["health", "suggestions", "debug", "plan", "recipe"] | None = None, current_user: dict = Depends(get_current_user)) -> SessionListResponse:
	store = get_chat_store()
	return SessionListResponse(sessions=store.list_sessions(current_user["email"], mode=mode))


@router.post("/reset/{session_id}")
def reset_chat(session_id: str, current_user: dict = Depends(get_current_user)) -> dict[str, str | int]:
	store = get_chat_store()
	deleted_count = store.reset_session(current_user["email"], session_id)
	return {"session_id": session_id, "deleted_messages": deleted_count, "status": "reset"}


@router.post("/recipe", response_model=RecipeResponse)
def generate_recipe(payload: RecipeRequest, current_user: dict = Depends(get_current_user)) -> RecipeResponse:
	try:
		user_groq_key = _resolve_user_groq_key(current_user)
		agent = get_nutrition_agent(user_groq_key)
		profile_dict = payload.profile.model_dump() if payload.profile else {}
		profile_dict = _normalize_payload(profile_dict) if profile_dict else {}
		result = agent.generate_recipe(
			dish_request=payload.dish_request,
			profile=profile_dict,
			cuisine=payload.cuisine,
			servings=payload.servings,
			notes=(payload.notes or "").strip(),
		)
		return RecipeResponse(**result)
	except ValueError as error:
		detail = str(error)
		status_code = 503 if "GROQ_API_KEY" in detail else 400
		raise HTTPException(status_code=status_code, detail=detail) from error
	except Exception as error:
		raise HTTPException(status_code=500, detail="Failed to generate recipe.") from error
