# SupportAI — Local Setup & Production Deployment Guide

## 1. Prerequisites
- Python `3.14.6` (with existing `backend\.venv`)
- Node.js `20+` and `npm`
- Google Gemini API key in `backend\.env` (`GEMINI_API_KEY`, `GEMINI_MODEL=gemini-3.5-flash-lite`)

## 2. Running Locally (Windows PowerShell 5.1)

### Start the Backend API
```powershell
cd C:\Users\dell\SupportAI\backend
.\.venv\Scripts\Activate.ps1
python -m uvicorn main:app --reload
```
The FastAPI backend runs at `http://127.0.0.1:8000` (Swagger docs at `/docs`).

### Start the Frontend App
Open a second PowerShell window:
```powershell
cd C:\Users\dell\SupportAI\frontend
npm run dev
```
The Next.js frontend runs at `http://localhost:3000`.

## 3. Running Tests & Quality Checks

### Backend
```powershell
cd C:\Users\dell\SupportAI\backend
.\.venv\Scripts\python.exe -m compileall -q .
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

### Frontend
```powershell
cd C:\Users\dell\SupportAI\frontend
npm run lint
npx tsc --noEmit
npm run build
```

## 4. Testing the Embeddable Website Widget
1. Sign up or log in at `http://localhost:3000/register`.
2. Upload a document or crawl a URL under **Dashboard → Knowledge Base**.
3. Create a chatbot under **Dashboard → Chatbots** and copy its `public_id` (e.g. `cb_...`).
4. Replace `CHATBOT_ID` in `docs/widget-test.html` (or any WordPress/HTML site) and open it via a local HTTP server:
   ```powershell
   cd C:\Users\dell\SupportAI\docs
   python -m http.server 5500
   ```
   Visit `http://localhost:5500/widget-test.html` to test the floating widget.

## 5. Production Deployment Notes
- Set a strong `JWT_SECRET_KEY` and explicit `CORS_ORIGINS` (e.g., `https://app.yourdomain.com`) in `backend\.env`.
- Set `NEXT_PUBLIC_API_URL` in `frontend\.env.local` to your HTTPS backend domain.
- Keep `backend/supportai.db`, `backend/data/chroma/`, and `backend/uploads/` on persistent storage with scheduled backups.
- To promote a registered user to platform administrator (`admin`), run a one-time SQL update on `supportai.db`:
  ```sql
  UPDATE users SET role = 'admin' WHERE email = 'admin@yourdomain.com';
  ```
  Then sign out and sign back in to issue an `admin` JWT token.
