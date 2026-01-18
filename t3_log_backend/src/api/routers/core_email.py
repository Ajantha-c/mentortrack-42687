from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, EmailStr, Field

from src.api.core.config import get_env
from src.api.integrations.resend_client import ResendClient

router = APIRouter(prefix="/notifications/email", tags=["Email"])


class CoreSendEmailRequest(BaseModel):
    """Request payload for sending an email via the server-side Resend integration."""

    to_email: EmailStr = Field(..., description="Recipient email address.")
    subject: str = Field(..., min_length=1, description="Email subject.")
    body: str = Field(..., min_length=1, description="Plain text / main body content.")


class CoreSendEmailResponse(BaseModel):
    """Response payload for the core email send endpoint."""

    resend_id: str = Field(..., description="Resend email id.")
    to: list[EmailStr] = Field(..., description="Recipient(s) the email was sent to.")


def _render_steel_cyan_email(*, subject: str, body: str) -> tuple[str, str]:
    """Render a minimal Steel Cyan branded email.

    Returns:
        Tuple of (text, html).
    """
    # Keep text clean and readable for clients that prefer plain text.
    text = f"{body}\n\n— Sent by T3 Log notifications"

    # Lightweight HTML with Steel Cyan (#67e8f9) accents.
    html = f"""
<!doctype html>
<html>
  <body style="margin:0;font-family:Arial,Helvetica,sans-serif;background:#0b0b0b;color:#ffffff;">
    <div style="max-width:640px;margin:0 auto;padding:24px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
        <div style="width:10px;height:10px;border-radius:999px;background:#67e8f9;"></div>
        <h2 style="margin:0;color:#67e8f9;font-size:18px;line-height:1.2;">T3 Log Update</h2>
      </div>

      <div style="border:1px solid #1f2937;background:#111827;border-radius:14px;padding:16px;">
        <p style="margin:0 0 10px 0;color:#e5e7eb;font-weight:700;">{subject}</p>
        <pre style="white-space:pre-wrap;margin:0;background:#0b1220;padding:12px;border-radius:12px;border:1px solid #1f2937;color:#d1d5db;">{body}</pre>
      </div>

      <p style="margin:16px 0 0 0;color:#9ca3af;font-size:12px;">
        Sent by T3 Log notifications.
      </p>
    </div>
  </body>
</html>
""".strip()

    return text, html


@router.post(
    "/send",
    summary="Core server-side email send (Resend)",
    description=(
        "Core server-side route to send a single email using Resend. "
        "Uses server-side RESEND_API_KEY only (frontend must never access it). "
        "Subject line should follow: 'T3 Log Update: [Action Name]'. "
        "Requires RESEND_API_KEY (or legacy RESEND_API-KEY) and RESEND_FROM_EMAIL."
    ),
    operation_id="core_send_email",
)
# PUBLIC_INTERFACE
async def core_send_email(payload: CoreSendEmailRequest) -> CoreSendEmailResponse:
    """Send an email via Resend using server-side secrets.

    Parameters:
        payload: CoreSendEmailRequest containing recipient, subject, and body.

    Returns:
        CoreSendEmailResponse containing Resend message id and resolved recipients.
    """
    resend = ResendClient()

    # IMPORTANT: For Resend, this must be a verified sender/domain.
    from_email = get_env("RESEND_FROM_EMAIL", "T3 Log <no-reply@t3log.example>")

    subject = payload.subject.strip()
    if not subject.lower().startswith("t3 log update:"):
        # Enforce the requested subject style, but don't fail hard — prepend.
        subject = f"T3 Log Update: {subject}"

    text, html = _render_steel_cyan_email(subject=subject, body=payload.body)

    try:
        resp = await resend.send_email(
            from_email=from_email,
            to_emails=[str(payload.to_email)],
            subject=subject,
            text=text,
            html=html,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email via Resend: {e}") from e

    return CoreSendEmailResponse(resend_id=str(resp.get("id", "")), to=[payload.to_email])
