from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.core_email import router as core_email_router
from src.api.routers.notifications_email import router as notifications_email_router

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
