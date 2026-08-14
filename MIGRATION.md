# Migrating from the Streamlit app to React + FastAPI

The original Streamlit app (`app.py` + `emissions_engine.py`, `ml_engine.py`, `db.py`,
`ai_engine.py`, `themes.py`) is untouched and still works exactly as before — this is an
**addition**, not a replacement. The new stack lives in `backend/` (expanded from the
existing FastAPI skeleton) and a new `frontend/` directory (React + TypeScript + Vite).
Cut over whenever you're ready; both can run side by side since they don't share a port
or process.

## Why

1. **UX**: Streamlit re-runs the whole page on every interaction. The React app filters,
   aggregates, and re-charts client-side instantly — no round trip — and uses real routes
   (`/dashboard`, `/corridor-map`, etc.), a WebGL map (deck.gl + MapLibre) instead of a
   server-rendered image, animated transitions, and a responsive layout that works below
   desktop width (the Streamlit version didn't).
2. **Security**: the code review of the Streamlit app found a stored-XSS chain (uploaded
   CSV values rendered as raw, unescaped HTML via `unsafe_allow_html=True`), a second XSS
   path through the AI report export, plaintext-password auth with no rate limiting, and a
   one-password irreversible "wipe entire database" action. React escapes all rendered
   text by default, which eliminates the XSS class structurally; the new backend adds
   bcrypt-hashed passwords, JWTs, login rate limiting, and an admin-role + typed-confirmation
   gate on the database wipe.

The emissions math (`emissions_engine.py`) and ML models (`ml_engine.py`) are reused
**unmodified** — both are pure, framework-agnostic functions, so there's zero risk of the
new frontend/backend split producing different numbers than the Streamlit app did.

## Running it locally

### Backend

```bash
cd backend
python -m venv ../.venv        # or reuse an existing venv
../.venv/Scripts/activate      # Windows; source ../.venv/bin/activate on macOS/Linux
pip install -r requirements.txt
cp .env.example .env           # then fill in values — see below
python scripts/hash_password.py   # generates a bcrypt hash for AUTH_USERS_JSON
uvicorn main:app --reload --port 8000
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env           # VITE_API_URL, defaults to http://localhost:8000
npm run dev
```

Open the URL Vite prints (default `http://localhost:5173`).

## Environment variables (replaces `st.secrets` / `secrets.toml`)

| Streamlit secret | New env var | Notes |
|---|---|---|
| `[supabase] url` | `SUPABASE_URL` | same value, same Supabase project — schema is unchanged |
| `[supabase] service_key` | `SUPABASE_SERVICE_KEY` | same value |
| `[gemini] api_key` | `GEMINI_API_KEY` | same value |
| `[credentials]` (plaintext username=password pairs) | `AUTH_USERS_JSON` | now a JSON array of `{username, password_hash, role}` — generate each hash with `python backend/scripts/hash_password.py`. `role` is `"admin"` or `"viewer"`; only `admin` can delete uploads or wipe the database. |
| `[delete] password` | *(removed)* | replaced by the `admin` role + a typed "DELETE" confirmation in the UI — see below |
| *(none — new)* | `JWT_SECRET` | any long random string; used to sign auth tokens |
| *(none — new)* | `CORS_ORIGINS` | comma-separated list of frontend origins allowed to call the API (default `http://localhost:5173`) |

The Supabase table schema is **unchanged** — `buses`, `trips`, `emissions`, `ml_insights` —
so pointing the new backend at the same project as the Streamlit app just works.

## What changed in the delete/wipe flow

The Streamlit app gated "Delete stored items" and "Wipe Entire Database" behind a single
shared plaintext password stored in `st.secrets`. Anyone who knew (or guessed) that one
password could wipe everything. The new flow requires:

1. A valid login (JWT), **and**
2. The `admin` role on that account, **and**
3. Typing the literal word `DELETE` in the confirmation field for a full wipe.

Deleting a single upload only requires steps 1–2 (matching the original's lighter-weight
per-file delete).

## Deploying

Same options as noted in the original `SETUP.md` for the backend (Railway/Render). The
frontend is a static Vite build (`npm run build` → `frontend/dist/`) deployable to any
static host (Netlify, Vercel, Cloudflare Pages, or the same Railway/Render project via a
static site service) — just set `VITE_API_URL` to the deployed backend's URL at build
time.
