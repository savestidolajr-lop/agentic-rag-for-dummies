"""
Production entry point — FastAPI + Clerk auth wrapping the Gradio app.

Run with:
    uvicorn main:app --host 0.0.0.0 --port 7860
"""

import sys
import os
import warnings

warnings.filterwarnings(
    "ignore",
    message=".*PydanticSerializationUnexpectedValue.*parsed.*",
    category=UserWarning,
)
warnings.filterwarnings(
    "ignore",
    message=".*Pydantic serializer warnings.*",
    category=UserWarning,
    module="pydantic.*",
)

sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

import gradio as gr
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from auth.clerk import verify_clerk_token, make_session_cookie, read_session_cookie
from ui.gradio_app import create_gradio_ui, _SIDEBAR_HEAD, _enter_js, _theme
from ui.admin_app import create_admin_ui, _admin_css
from ui.css import custom_css
from api.routes import router as api_router, init_routes
import config

# ── Clerk / session config ────────────────────────────────────────────────────

CLERK_PK       = os.environ.get("CLERK_PUBLISHABLE_KEY", "")
CLERK_FRONTEND = os.environ.get("CLERK_FRONTEND_API_URL", "")

# Paths that skip auth — Gradio internals + our own auth endpoints + API routes
# (API routes handle their own Bearer auth via the get_current_user dependency)
_OPEN_PATHS    = {"/login", "/auth/verify", "/auth/logout", "/auth/callback", "/health"}
_OPEN_PREFIXES = ("/_", "/static/", "/queue/", "/assets/", "/info", "/config",
                  "/upload", "/gradio/", "/gradio_api/", "/run/", "/file=", "/api/")

# ── Login / callback HTML ─────────────────────────────────────────────────────

_LOGIN_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Sign In — Case Agent</title>
  <style>
    * {{ box-sizing: border-box; }}
    body {{ margin:0; background:#0d0d0d; color:#e8e8e8;
           font-family: Inter, sans-serif;
           display:flex; align-items:center; justify-content:center; height:100vh; }}
    .card {{ text-align:center; }}
    h1 {{ font-size:1.5rem; margin-bottom:6px; color:#fff; letter-spacing:-.02em; }}
    p  {{ color:#666; font-size:.875rem; margin:0; }}
  </style>
  <script
    async crossorigin="anonymous"
    data-clerk-publishable-key="{pk}"
    src="{frontend}/npm/@clerk/clerk-js@latest/dist/clerk.browser.js">
  </script>
</head>
<body>
  <div class="card">
    <h1>Case Agent</h1>
    <p>Redirecting to sign-in&hellip;</p>
  </div>
  <script>
    window.addEventListener('load', async () => {{
      await window.Clerk.load();
      if (window.Clerk.user) {{
        const token = await window.Clerk.session.getToken();
        const res = await fetch('/auth/verify', {{
          method: 'POST',
          headers: {{'Content-Type': 'application/json'}},
          body: JSON.stringify({{token}})
        }});
        if (res.ok) {{ window.location.href = '/'; return; }}
      }}
      window.Clerk.redirectToSignIn({{ afterSignInUrl: '/auth/callback' }});
    }});
  </script>
</body>
</html>
"""

_LOGOUT_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Signing out&hellip;</title>
  <style>
    body {{ margin:0; background:#0d0d0d; color:#e8e8e8;
           font-family: Inter, sans-serif;
           display:flex; align-items:center; justify-content:center; height:100vh; }}
    p {{ color:#666; font-size:.875rem; }}
  </style>
  <script
    async crossorigin="anonymous"
    data-clerk-publishable-key="{pk}"
    src="{frontend}/npm/@clerk/clerk-js@latest/dist/clerk.browser.js">
  </script>
</head>
<body>
  <p>Signing out&hellip;</p>
  <script>
    window.addEventListener('load', async () => {{
      await window.Clerk.load();
      await window.Clerk.signOut();
      window.location.href = '/login';
    }});
  </script>
</body>
</html>
"""

_CALLBACK_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Signing in&hellip;</title>
  <style>
    body {{ margin:0; background:#0d0d0d; color:#e8e8e8;
           font-family: Inter, sans-serif;
           display:flex; align-items:center; justify-content:center; height:100vh; }}
    p {{ color:#666; font-size:.875rem; }}
  </style>
  <script
    async crossorigin="anonymous"
    data-clerk-publishable-key="{pk}"
    src="{frontend}/npm/@clerk/clerk-js@latest/dist/clerk.browser.js">
  </script>
</head>
<body>
  <p>Completing sign-in&hellip;</p>
  <script>
    window.addEventListener('load', async () => {{
      await window.Clerk.load();
      const token = await window.Clerk.session.getToken();
      const res = await fetch('/auth/verify', {{
        method: 'POST',
        headers: {{'Content-Type': 'application/json'}},
        body: JSON.stringify({{token}})
      }});
      window.location.href = res.ok ? '/' : '/login';
    }});
  </script>
</body>
</html>
"""

# ── Build app ─────────────────────────────────────────────────────────────────

# Clear any stale indexing status files left over from a previous interrupted run
try:
    import glob as _glob
    for _f in _glob.glob(os.path.join(os.path.dirname(__file__), "indexing_status*.json")):
        os.remove(_f)
except Exception:
    pass

print("\n🔨 Creating RAG Assistant...")
_demo = create_gradio_ui()
print("✅ RAG Assistant ready.")

print("🔨 Creating Admin Panel...")
_admin_demo = create_admin_ui(_demo._rag_system, _demo._doc_manager)
print("✅ Admin Panel ready.")

# Initialise API routes with the shared service instances (same objects used by Gradio UI)
init_routes(_demo._chat_interface, _demo._doc_manager, _demo._rag_system)
print("✅ API routes initialised.")

app = FastAPI(docs_url=None, redoc_url=None)

# ── CORS (allow local Next.js / React dev server) ─────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://52.63.202.41:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Auth middleware ───────────────────────────────────────────────────────────

@app.middleware("http")
async def require_auth(request: Request, call_next):
    # Always pass OPTIONS through so CORS preflight works
    if request.method == "OPTIONS":
        return await call_next(request)
    path = request.url.path
    if path in _OPEN_PATHS or any(path.startswith(p) for p in _OPEN_PREFIXES):
        return await call_next(request)
    data = read_session_cookie(request.cookies.get("rag_uid", ""))
    if not data:
        accept = request.headers.get("accept", "")
        if "text/html" in accept:
            return RedirectResponse("/login")
        return JSONResponse({"error": "Unauthorized"}, status_code=401)
    return await call_next(request)

# ── Auth routes ───────────────────────────────────────────────────────────────

@app.get("/login")
async def login_page():
    return HTMLResponse(_LOGIN_HTML.format(pk=CLERK_PK, frontend=CLERK_FRONTEND))


@app.get("/auth/callback")
async def auth_callback():
    return HTMLResponse(_CALLBACK_HTML.format(pk=CLERK_PK, frontend=CLERK_FRONTEND))


@app.post("/auth/verify")
async def auth_verify(request: Request):
    try:
        body = await request.json()
        token = body.get("token", "")
        payload = verify_clerk_token(token)
        user_id = payload.get("sub", "")
        email = payload.get("email", "")
        signed = make_session_cookie(user_id, email)
        response = JSONResponse({"ok": True})
        response.set_cookie(
            "rag_uid", signed,
            httponly=True, samesite="lax",
            max_age=86400 * 7,
        )
        return response
    except Exception as e:
        return JSONResponse({"ok": False, "error": str(e)}, status_code=401)


@app.get("/auth/logout")
async def logout():
    response = HTMLResponse(_LOGOUT_HTML.format(pk=CLERK_PK, frontend=CLERK_FRONTEND))
    response.delete_cookie("rag_uid", path="/", samesite="lax", httponly=True)
    return response


@app.get("/admin")
async def admin_redirect():
    return RedirectResponse("/admin/", status_code=308)


@app.get("/health")
async def health():
    if hasattr(_demo, "_rag_system"):
        return _demo._rag_system.get_health(refresh=True)
    return {"ok": True}

# ── API routes (must be included BEFORE Gradio mounts) ───────────────────────
app.include_router(api_router)

# ── Mount Gradio ──────────────────────────────────────────────────────────────

# Add admin Gradio internal paths to open prefixes so queue/websocket calls work
_OPEN_PREFIXES = _OPEN_PREFIXES + ("/admin/queue/", "/admin/run/", "/admin/_", "/admin/info", "/admin/config")

# Mount admin FIRST — more specific route must come before the catch-all "/"
app = gr.mount_gradio_app(
    app, _admin_demo, path="/admin",
    allowed_paths=[config.DOCUMENTS_DIR],
    theme=_theme,
    css=_admin_css,
    footer_links=[],
)

app = gr.mount_gradio_app(
    app, _demo, path="/",
    allowed_paths=[config.DOCUMENTS_DIR],
    theme=_theme,
    css=custom_css,
    js=_enter_js,
    head=_SIDEBAR_HEAD,
    footer_links=[],
)
