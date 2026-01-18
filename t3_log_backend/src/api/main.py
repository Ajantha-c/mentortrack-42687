import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.core_email import router as core_email_router
from src.api.routers.notifications_email import router as notifications_email_router
from src.api.routers.supabase_hooks import router as supabase_hooks_router

openapi_tags = [
    {
        "name": "System",
        "description": "Health and system endpoints.",
    },
    {
        "name": "Notifications",
        "description": "Server-side notification endpoints (email, etc.).",
    },
    {
        "name": "Email",
        "description": "Core server-side email send endpoints (Resend).",
    },
    {
        "name": "Supabase Hooks",
        "description": "Endpoints intended to be called by Supabase Database Webhooks / triggers.",
    },
]

app = FastAPI(
    title="T3 Log Backend API",
    description=(
        "API layer for T3 Log: mentorship workflows, tasks, and server-side notifications.\n\n"
        "Email notifications are sent server-side via Resend. Frontend should never "
        "ship or access RESEND_API_KEY."
    ),
    version="0.1.0",
    openapi_tags=openapi_tags,
)

# CORS:
# - Frontend runs on :3000 and calls backend on :3001.
# - Origins are configurable via env var `CORS_ALLOW_ORIGINS` to support different preview/deploy URLs.
#
# IMPORTANT:
# - Allowing the *exact* frontend preview origin is required (scheme/host/port must match).
# - Preflight requests use OPTIONS and must not be redirected or missing CORS headers.
_raw_origins = (os.getenv("CORS_ALLOW_ORIGINS") or "").strip()
_allow_origins = (
    [o.strip() for o in _raw_origins.split(",") if o.strip()]
    if _raw_origins
    else [
        # Local dev
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        # Kavia preview frontend origins (MUST match exactly; scheme/host/port)
        "https://vscode-internal-35884-beta.beta01.cloud.kavia.ai:3000",
        # Previous preview origin (kept to avoid regressions when port changes)
        "https://vscode-internal-41480-beta.beta01.cloud.kavia.ai:3000",
    ]
)

# Mount middleware BEFORE routers (required so it applies to all routes).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    # Explicit methods for clearer preflight behavior
    allow_methods=["OPTIONS", "POST", "GET"],
    # Explicit headers requested
    allow_headers=["Content-Type", "Authorization"],
)

@app.get("/", tags=["System"], summary="Health Check", operation_id="health_check")
# PUBLIC_INTERFACE
def health_check():
    """Health check endpoint.

    Returns:
        JSON payload indicating service is alive.
    """
    return {"message": "Healthy"}


app.include_router(notifications_email_router)
app.include_router(core_email_router)
app.include_router(supabase_hooks_router)
