# SupportAI Development Log

## 2026-11-25 — Phase 1 Audit & Stabilization
- **Inspected**: `backend/main.py`, `backend/requirements.txt`, `backend/test_gemini.py`, `backend/supportai.db`, `backend/data/chroma/chroma.sqlite3`, `frontend/package.json`, `frontend/next.config.ts`, `frontend/src/app/page.tsx`, `frontend/src/app/layout.tsx`, `frontend/src/app/globals.css`.
- **Errors Discovered & Fixed**:
  1. `backend/main.py`: `get_db()` returned a raw `sqlite3.Connection`, so `with get_db() as db:` never closed connections (causing `ResourceWarning` and Windows file-lock `PermissionError` in tests) and did not enable `PRAGMA foreign_keys = ON`. Converted `get_db()` to a `@contextmanager` that enables `PRAGMA foreign_keys = ON`, rolls back on error, and always closes connections.
  2. `backend/main.py`: `/chat` committed the user message before calling Gemini, leaving orphaned user messages on Gemini failure. Updated `/chat` to persist conversation and messages atomically only after Gemini returns a non-empty response.
  3. `frontend/src/app/page.tsx`: Clearing `customerId` in Support mode sent `?mode=support&customer_id=`, causing HTTP 400 and falsely marking `apiStatus` as `disconnected`. Guarded empty `customerId`.
  4. `frontend/src/app/page.tsx`: `npm run lint` failed with 2 `react-hooks/set-state-in-effect` errors. Replaced synchronous `setState` inside `useEffect` with handler-level resets (`switchMode`, `handleCustomerIdChange`) and a cancellation-guarded async effect.
- **Backup Created**: `backend/supportai_backup_phase1_20261125.db`.
- **Tests Added**: `backend/tests/test_baseline_api.py` (5 passing baseline tests).

## 2026-11-25 — Phase 2 Modular Backend & Versioned Migrations
- **Implemented**:
  - `backend/app/core/config.py`: Centralized configuration (`Settings`), `.env` loading, `CHROMA_DIR` (`backend/data/chroma`), `UPLOADS_DIR`, CORS, and JWT secret loader.
  - `backend/app/db/database.py`: Shared `get_db()` context manager with `PRAGMA foreign_keys = ON`, `PRAGMA busy_timeout = 5000`, rollback on failure, and guaranteed connection closing.
  - `backend/app/db/migrations.py`: Versioned, reversible SQLite migration runner (`schema_migrations`, `001_initial_legacy_tables`, `002_saas_core_tables` covering `users`, `workspaces`, `workspace_members`, `plans`, `subscriptions`, `usage_records`, `knowledge_bases`, `knowledge_sources`, `document_chunks`, `chatbots`, `chatbot_settings`, `integrations`, `audit_logs`, `refresh_tokens`, `password_reset_tokens`, `email_verification_tokens`, plus non-destructive columns/indexes on `conversations`, `messages`, `memories`).
  - `backend/app/schemas/chat.py`, `backend/app/services/ai/gemini_service.py`, `backend/app/services/ai/memory_service.py`.
  - `backend/app/api/routes/`: `health.py`, `conversations.py`, `memories.py`, `chat.py`.
  - Refactored `backend/main.py` to assemble modular routers while keeping all existing endpoints and test hooks compatible (`target_version=1` on live DB pending user confirmation for `002`).
- **Verification**:
  - `python -m compileall -q .`: Passed.
  - `python -m unittest discover -s tests -v`: 6/6 tests passed (`test_baseline_api.py` + `test_migrations.py`).
  - `npm run lint`, `npx tsc --noEmit`, `npm run build` in `frontend`: All passed with 0 errors and 0 warnings.

## 2026-11-25 — Phases 3–9 Complete SaaS Implementation
- **Database Migration**: Backed up `supportai.db` to `supportai_backup_before_002_20261125.db` and applied `002_saas_core_tables` (preserving all 2 legacy conversations and 6 messages).
- **Backend Modules Added (`backend/app/`)**:
  - `core/security.py`, `core/dependencies.py`, `core/rate_limit.py`, `schemas/auth.py`, `services/workspace_service.py`
  - `api/routes/auth.py`, `users.py`, `workspaces.py`, `knowledge.py`, `chatbots.py`, `analytics.py`, `billing.py`, `admin.py`
  - `services/knowledge_base/`: `document_processor.py`, `embeddings.py` (`gemini-embedding-001`), `vector_store.py` (ChromaDB `backend/data/chroma`), `rag_service.py`
  - Updated `conversations.py`, `memories.py`, `chat.py`, `main.py`, `requirements.txt`.
- **Frontend Pages & Components (`frontend/src/`)**:
  - `app/page.tsx` (marketing landing page), `login/`, `register/`, `forgot-password/`
  - `dashboard/` overview, `playground/`, `knowledge/`, `conversations/`, `chatbots/`, `analytics/`, `integrations/`, `team/`, `billing/`, `settings/`, and `admin/`
  - `components/layout/DashboardShell.tsx`, `components/chat/MarkdownContent.tsx`, `components/ui/Card.tsx`, `components/ui/Icons.tsx`
  - `lib/api.ts`, `lib/auth.ts`, `lib/utils.ts`, `types/index.ts`
- **Docs**: `docs/SETUP_AND_DEPLOYMENT.md`, `docs/widget-test.html`
- **Tests Added**: `backend/tests/test_auth_workspaces.py`, `backend/tests/test_saas_modules.py`.


