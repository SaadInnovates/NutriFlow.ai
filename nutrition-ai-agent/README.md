# NutriFlow.ai

Production-ready full-stack nutrition platform powered by FastAPI, React, MongoDB, and Groq LLMs with RAG grounding.

This project supports secure user accounts, email verification/password reset, personalized diet plan generation, recipe generation, multi-mode nutrition chat, PDF export, and session-based conversation history.

---

## Table of Contents

- [Overview](#overview)
- [Key Capabilities](#key-capabilities)
- [System Architecture](#system-architecture)
- [Repository Structure](#repository-structure)
- [Technology Stack](#technology-stack)
- [Environment Variables](#environment-variables)
- [Local Development Setup](#local-development-setup)
- [Running the Application](#running-the-application)
- [Authentication and User Flows](#authentication-and-user-flows)
- [API Reference](#api-reference)
- [Frontend Experience](#frontend-experience)
- [RAG and AI Pipeline](#rag-and-ai-pipeline)
- [Security, Reliability, and Guardrails](#security-reliability-and-guardrails)
- [Testing](#testing)
- [Deployment Notes](#deployment-notes)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)

---

## Overview

NutriFlow.ai Agent is an end-to-end nutrition assistant platform with:

- Personalized 7-day diet plan generation from user profile data.
- Evidence-aware output (sources, section confidence, attribution).
- Health and suggestions chatbot modes.
- Diet debug workflow for modifying existing plan text.
- Recipe generation endpoint focused on healthy preparation guidance.
- PDF export for generated/modified plans.
- JWT-based authentication with email verification and password reset.
- Session history management with session listing and retrieval.
- Modern animated frontend with dark mode and enhanced UX interactions.
- Optional terminal interface for backend interaction without browser UI.

---

## Key Capabilities

### Backend capabilities

- FastAPI app with modular routing (`/api/auth`, `/api/chat`).
- User auth lifecycle: register, verify email, login, profile update, delete account.
- Secure password hashing via `passlib` (`pbkdf2_sha256`).
- JWT access tokens with configurable expiry and algorithm.
- Rate limiting for sensitive auth flows:
  - verification request/confirm
  - forgot/reset password
- SMTP-driven transactional email:
  - verification links
  - password reset links
- NutriFlow.ai agent with:
  - plan generation
  - multi-mode chat
  - plan modification
  - recipe generation
- MongoDB-backed chat store:
  - add/get/reset chat history
  - list sessions by mode

### Frontend capabilities

- React + Vite SPA with protected dashboard route.
- Login/Register/Verify/Forgot auth pages with auto-redirect if already authenticated.
- Auto sign-in after successful verification (when pending signup credentials exist in session storage).
- Dashboard modules:
  - API health and key status
  - profile editor
  - plan generation + PDF
  - recipe generation
  - chat (health/suggestions)
  - debug modify workflow
  - PDF quick access
- Rich visual experience:
  - dark mode toggle and persistence
  - animated sections, tile cards, hover micro-interactions
  - staggered message/session reveal animations
  - typing/loading indicators

### Terminal capabilities

- Menu-based command-line interface in `app/terminal_interface.py`.
- Backend health check, plan generation, chat modes, debug mode, PDF open/export.
- Session switching, history retrieval, and reset commands.

---

## System Architecture

```text
React Dashboard / Terminal UI
          |
          v
    FastAPI Application (app/main.py)
          |
  +-------+------------------+
  |                          |
  v                          v
Auth Router              Chat Router
(/api/auth/*)            (/api/chat/*)
  |                          |
  v                          v
MongoDB users           NutritionAgent
SMTP mailer                 |
audit logs                  +--> Prompt builders
rate limiting               +--> RAG retriever
                            +--> Groq Chat model
                            +--> PDF/report utilities

RAG Store: FAISS + HuggingFace embeddings
Data source: data/nutrition_docs (txt/md/pdf)
```

---

## Repository Structure

```text
nutrition-ai-agent/
├── app/
│   ├── agents/
│   │   └── nutrition_agent.py
│   ├── db/
│   │   └── mongodb.py
│   ├── prompts/
│   │   ├── chat_prompts.py
│   │   └── diet_prompt.py
│   ├── rag/
│   │   ├── retriever.py
│   │   └── vectorstore.py
│   ├── routes/
│   │   ├── auth.py
│   │   └── chat.py
│   ├── utils/
│   │   ├── audit.py
│   │   ├── chat_store.py
│   │   ├── diet_debugger.py
│   │   ├── mailer.py
│   │   ├── nutrition_math.py
│   │   ├── pdf_report.py
│   │   ├── pdf_theme.py
│   │   ├── response_format.py
│   │   └── secrets_guard.py
│   ├── config.py
│   ├── main.py
│   ├── security.py
│   └── terminal_interface.py
├── data/
│   ├── generated_plans/
│   ├── nutrition_docs/
│   └── pdf_theme.json
├── frontend/
│   ├── src/
│   │   ├── api/client.js
│   │   ├── components/FormattedText.jsx
│   │   ├── context/AuthContext.jsx
│   │   ├── pages/
│   │   │   ├── DashboardPage.jsx
│   │   │   ├── ForgotPasswordPage.jsx
│   │   │   ├── LoginPage.jsx
│   │   │   ├── RegisterPage.jsx
│   │   │   └── VerifyEmailPage.jsx
│   │   ├── App.jsx
│   │   ├── main.jsx
│   │   └── styles.css
│   ├── package.json
│   ├── vite.config.js
│   └── index.html
├── tests/
│   └── test_api.py
├── requirements.txt
├── vercel.json
└── README.md
```

---

## Technology Stack

### Backend

- Python
- FastAPI
- Uvicorn
- Pydantic
- MongoDB (`pymongo`)
- JWT (`python-jose[cryptography]`)
- Password hashing (`passlib[bcrypt]`, configured to `pbkdf2_sha256`)
- Email validation (`email-validator`)
- Multipart handling (`python-multipart`)

### AI / RAG

- LangChain ecosystem
  - `langchain`
  - `langchain-core`
  - `langchain-community`
  - `langchain-text-splitters`
  - `langchain-groq`
- Groq API (`groq`)
- Vector DB: FAISS (`faiss-cpu`)
- Embeddings: `sentence-transformers`
- PDF parse: `pypdf`

### Frontend

- React 18
- Vite
- React Router
- Axios
- React Markdown + GFM rendering
- React Icons
- Bootstrap 5 + custom animated CSS theme

### Testing

- `unittest`
- `fastapi.testclient`
- `pytest` dependency included

---

## Environment Variables

Create a `.env` file in the project root.

### Application

- `APP_NAME` (default: `NutriFlow.ai Agent`)
- `APP_VERSION` (default: `0.1.0`)
- `CORS_ORIGINS` (comma-separated, default: `*`)

### LLM / Model

- `GROQ_API_KEY` (required unless user sets key in profile)
- `GROQ_MODEL` (default: `llama-3.1-8b-instant`)
- `MODEL_TEMPERATURE` (default: `0.2`)
- `MODEL_MAX_TOKENS` (default: `3200`)
- `MODEL_MAX_CONTINUATION_ATTEMPTS` (default: `2`)

### RAG / Retrieval

- `EMBEDDING_MODEL` (default: `sentence-transformers/all-MiniLM-L6-v2`)
- `CHUNK_SIZE` (default: `700`)
- `CHUNK_OVERLAP` (default: `120`)
- `RETRIEVAL_K` (default: `4`)
- `PLAN_CONTEXT_MAX_CHARS` (default: `2800`)
- `NUTRITION_DOCS_DIR` (default: `data/nutrition_docs`)

### Performance / startup

- `ENABLE_PLAN_CACHE` (default: `true`)
- `PLAN_CACHE_TTL_SECONDS` (default: `900`)
- `PRELOAD_VECTORSTORE_ON_STARTUP` (default: `false`)
- `PRELOAD_AGENT_ON_STARTUP` (default: `false`)
- `ENABLE_STARTUP_SECRET_SCAN` (default: `false`)

### Database

- `MONGODB_URI` (default: `mongodb://127.0.0.1:27017`)
- `MONGODB_DB_NAME` (default: `nutrition_ai`)

### JWT / Auth

- `JWT_SECRET_KEY` (required in production)
- `JWT_ALGORITHM` (default: `HS256`)
- `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` (default: `120`)

### Auth rate limits

- `AUTH_RATE_LIMIT_WINDOW_SECONDS` (default: `900`)
- `AUTH_VERIFY_REQUEST_LIMIT` (default: `5`)
- `AUTH_FORGOT_REQUEST_LIMIT` (default: `5`)
- `AUTH_VERIFY_CONFIRM_LIMIT` (default: `10`)
- `AUTH_RESET_PASSWORD_LIMIT` (default: `10`)

### Frontend links

- `FRONTEND_BASE_URL` (default: `http://127.0.0.1:5173`)

### SMTP / Email

- `SMTP_HOST`
- `SMTP_PORT` (default: `587`)
- `SMTP_USERNAME` (if empty, backend falls back to `SMTP_FROM_EMAIL`)
- `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL`
- `SMTP_FROM_NAME` (default: `NutriFlow.ai`)
- `SMTP_USE_TLS` (default: `true`)
- `SMTP_USE_SSL` (default: `false`)

> Important: never commit real API keys, JWT secrets, or SMTP credentials.

---

## Local Development Setup

### 1) Clone repository

```bash
git clone <your-repo-url>
cd nutrition-ai-agent
```

### 2) Python environment + backend dependencies

```bash
python -m venv .venv
```

Windows (PowerShell):

```powershell
.\.venv\Scripts\Activate.ps1
```

Windows (CMD):

```cmd
.venv\Scripts\activate.bat
```

Install:

```bash
pip install -r requirements.txt
```

### 3) Frontend dependencies

```bash
cd frontend
npm install
cd ..
```

### 4) Configure `.env`

Add all required variables from the [Environment Variables](#environment-variables) section.

---

## Running the Application

### Backend (FastAPI)

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8001
```

- Root endpoint: `http://127.0.0.1:8001/`
- Swagger docs: `http://127.0.0.1:8001/docs`

### Frontend (Vite)

```bash
cd frontend
npm run dev
```

Optional `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8001/api
```

### Terminal Interface (optional)

```bash
python app/terminal_interface.py
```

---

## Authentication and User Flows

### Registration + verification

1. User registers (`POST /api/auth/register`).
2. Backend creates unverified user and sends verification email.
3. If email send fails, user creation is rolled back and API returns `503`.
4. User verifies token (`POST /api/auth/verify/confirm`).
5. Frontend auto-signs in when verification succeeds and pending credentials exist.

### Login

- Login requires verified email.
- Unverified users receive `403` with guidance to verify email first.

### Password reset

1. Request reset email (`POST /api/auth/forgot-password`).
2. Confirm reset token and new password (`POST /api/auth/reset-password`).

### Frontend auth UX behavior

- Auth pages redirect to dashboard automatically when user is already authenticated.
- Protected dashboard route redirects unauthenticated users to login.

---

## API Reference

Base prefix: `/api`

### Auth Router (`/api/auth`)

- `POST /register` — create account + send verify email
- `POST /login` — login with JSON credentials
- `POST /token` — OAuth2 password flow token endpoint
- `GET /me` — current user profile (JWT)
- `GET /profile` — custom nutrition profile (JWT)
- `PUT /profile` — update nutrition profile (JWT)
- `DELETE /me` — delete account (JWT)
- `GET /groq-key` — check if user-level Groq key exists (JWT)
- `PUT /groq-key` — set user-level Groq key (JWT)
- `POST /verify/request` — send/re-send verification email
- `POST /verify/status` — check whether email is verified
- `POST /verify/confirm` — verify email using token
- `POST /forgot-password` — request password reset email
- `POST /reset-password` — reset password with token

### Chat Router (`/api/chat`)

- `GET /health` — backend+key status
- `POST /plan` — generate diet plan
- `POST /message` — send chat message (`health|suggestions|debug|plan|recipe`)
- `POST /recipe` — generate a nutrition-oriented recipe
- `POST /debug/modify` — modify existing plan text
- `POST /plan/pdf` — generate downloadable plan PDF
- `POST /debug/extract-plan` — extract text from uploaded PDF
- `GET /history/{session_id}` — get chat history for session
- `GET /sessions` — list user sessions, optional mode filter
- `POST /reset/{session_id}` — clear session history

---

## Frontend Experience

Routes in `frontend/src/App.jsx`:

- `/login`
- `/register`
- `/verify-email`
- `/forgot-password`
- `/` (protected dashboard)

Dashboard tabs include:

- Check API
- Generate Plan
- Recipe
- Health Chat
- Suggestions Chat
- Diet Debug
- Last PDF
- Profile Settings

UI includes:

- persistent dark mode
- animated panels/tabs/cards
- staggered chat/session reveals
- typing indicators during requests
- profile-driven controls and session explorer

---

## RAG and AI Pipeline

### Data ingestion

- Source folder: `data/nutrition_docs`
- Supported types: `.txt`, `.md`, `.pdf`
- Fallback knowledge is used if no docs are available.

### Chunking and indexing

- Recursive chunk splitting (`CHUNK_SIZE`, `CHUNK_OVERLAP`)
- Embeddings via HuggingFace model
- FAISS index build/load

### Cache strategy

- FAISS index cache stored under `data/.faiss_cache`
- Corpus signature hashing (file metadata + config) triggers rebuild only when needed
- In-memory plan response cache with TTL
- Optional startup preloading of vectorstore and agent

---

## Security, Reliability, and Guardrails

- JWT authorization for protected routes.
- Password hashing with secure algorithm.
- Email verification required before login.
- Token hashes stored in DB (not raw reset/verify tokens).
- Auth rate limits (IP + email based).
- Structured JSON audit events via `app/utils/audit.py`.
- Optional startup hardcoded secret scanning.
- SMTP misconfiguration guardrails (partial auth detection).
- Chat scope constraints for nutrition-only safety behavior.

---

## Testing

Current tests (`tests/test_api.py`) cover:

- root/docs/openapi health checks
- plan generation route behavior (mocked agent)
- chat message flow
- chat history + reset
- debug modify route

Run tests:

```bash
python -m unittest -q tests.test_api
```

---

## Deployment Notes

### Vercel backend config

`vercel.json` maps all routes to `app/main.py` using `@vercel/python`.

### Typical production recommendations

- set strong `JWT_SECRET_KEY`
- use dedicated managed MongoDB
- use dedicated SMTP service account
- set restrictive `CORS_ORIGINS`
- disable debug defaults and rotate secrets regularly

---

## Troubleshooting

### `503 Failed to send verification email`

- Verify SMTP credentials and app password.
- Confirm `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, `SMTP_PASSWORD`.
- For Gmail, ensure app passwords/2FA are configured correctly.

### `403 Please verify your email before logging in`

- Complete `/verify-email` flow first.
- Request a new token via `POST /api/auth/verify/request`.

### `503 GROQ_API_KEY is missing`

- Set `GROQ_API_KEY` in `.env`, or
- Save a user-scoped key from dashboard settings.

### Slow first request

- Enable preloading:
  - `PRELOAD_VECTORSTORE_ON_STARTUP=true`
  - `PRELOAD_AGENT_ON_STARTUP=true`

---

## Roadmap

- Add role-aware experiences (coach/admin).
- Add richer API metrics and observability.
- Add background jobs for long-running generation tasks.
- Expand test coverage for auth/email and frontend integration.

---

## Maintainer

Muhammad Saad

---
