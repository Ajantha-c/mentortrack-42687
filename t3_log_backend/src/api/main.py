import os

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

openapi_tags = [
    {
        "name": "System",
        "description": "Health and system endpoints.",
    },
]

app = FastAPI(
    title="T3 Log Backend API",
    description="API layer for T3 Log: mentorship workflows and tasks.",
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
        # Kavia preview frontend origin(s) (MUST match exactly; scheme/host/port)
        "https://vscode-internal-35884-beta.beta01.cloud.kavia.ai:3000",
        # User-specified allowed origin
        "https://vscode-internal-41480-beta.beta01.cloud.kavia.ai:3000",
    ]
)

# CORS requirements for frontend -> backend calls:
# - Ensure POST routes work (preflight uses OPTIONS)
# - Ensure requested headers are allowed (Authorization/Content-Type)
# - Allow common browser preflight request headers so middleware can respond properly.
_allowed_methods = ["GET", "POST", "OPTIONS"]
_allowed_headers = [
    "Content-Type",
    "Authorization",
    # Common preflight request headers sent by browsers / fetch:
    "Access-Control-Request-Method",
    "Access-Control-Request-Headers",
]

# Mount middleware BEFORE routers (required so it applies to all routes).
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allow_origins,
    allow_credentials=True,
    allow_methods=_allowed_methods,
    allow_headers=_allowed_headers,
)

# PUBLIC_INTERFACE
@app.options("/{full_path:path}", include_in_schema=False)
async def cors_preflight(full_path: str, request: Request) -> Response:
    """Catch-all OPTIONS handler to guarantee CORS preflight works.

    Some deployments / proxies can behave unexpectedly with implicit preflight handling.
    This endpoint ensures the application always has an OPTIONS route, while still
    relying on CORSMiddleware to set the Access-Control-Allow-* headers.

    Parameters:
        full_path: Requested path (captured).
        request: FastAPI request.

    Returns:
        Empty 204 response; CORSMiddleware should attach CORS headers based on Origin.
    """
    return Response(status_code=204)


@app.get("/", tags=["System"], summary="Health Check", operation_id="health_check")
# PUBLIC_INTERFACE
def health_check():
    """Health check endpoint.

    Returns:
        JSON payload indicating service is alive.
    """
    return {"message": "Healthy"}
