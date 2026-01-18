from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.core.config import get_env
from src.api.email.templates import intern_submission_to_mentor, mentor_update_to_intern
from src.api.integrations.resend_client import ResendClient
from src.api.integrations.supabase_client import SupabaseClient

router = APIRouter(prefix="/notifications/email", tags=["Notifications"])


class InternSubmissionRequest(BaseModel):
    """Request payload for notifying mentor of a new intern task submission."""

    intern_id: str = Field(..., description="Intern user id (Supabase auth uid or app user id).")
    mentor_id: str = Field(..., description="Mentor user id (Supabase auth uid or app user id).")
    task_title: str = Field(..., description="Task title.")
    submission_text: str | None = Field(None, description="Intern submission notes/body.")


class InternNewTaskRequest(BaseModel):
    """Request payload for notifying mentor when an intern creates a new task."""

    intern_id: str = Field(..., description="Intern user id (Supabase auth uid or app user id).")
    mentor_id: str = Field(..., description="Mentor user id (Supabase auth uid or app user id).")
    task_title: str = Field(..., min_length=1, description="Newly created task title.")
    created_at: str | None = Field(
        None,
        description=(
            "Optional timestamp for when the task was created (ISO-8601). "
            "If omitted, server will use current UTC time."
        ),
    )


class MentorUpdateRequest(BaseModel):
    """Request payload for notifying intern of a mentor update."""

    intern_id: str = Field(..., description="Intern user id (Supabase auth uid or app user id).")
    mentor_id: str = Field(..., description="Mentor user id (Supabase auth uid or app user id).")
    task_title: str = Field(..., description="Task title.")
    status: str | None = Field(None, description="New status (e.g., Approved/Needs changes/Completed).")
    remarks: str | None = Field(None, description="Mentor remarks/body.")


class SendEmailResponse(BaseModel):
    """Response indicating whether an email was successfully sent."""

    resend_id: str = Field(..., description="Resend email id.")
    to: list[str] = Field(..., description="Resolved recipient emails.")


async def _get_user_email_and_name(client: SupabaseClient, user_id: str) -> tuple[str, str]:
    """
    Try to resolve user email/name from a Supabase table.

    Note: Table/columns can vary by project. This implementation assumes a `profiles`
    table with at least: id, email, full_name (or name). If your schema differs,
    adjust the table/columns here.
    """
    row = await client.select_single(
        "profiles",
        {"id": user_id},
        columns="id,email,full_name,name",
    )
    if not row:
        raise HTTPException(status_code=404, detail=f"User profile not found for id '{user_id}'")

    email = (row.get("email") or "").strip()
    name = (row.get("full_name") or row.get("name") or "").strip()

    if not email:
        raise HTTPException(
            status_code=422,
            detail=f"Profile for id '{user_id}' does not contain an email address.",
        )
    if not name:
        # Non-fatal; use email local-part as a fallback name.
        name = email.split("@")[0]
    return email, name


def _format_task_created_at(created_at: str | None) -> str:
    """Format an ISO timestamp (or now) into a friendly UTC string."""
    if created_at:
        try:
            # Handle the common "Z" UTC suffix.
            parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        except ValueError:
            raise HTTPException(
                status_code=422,
                detail="created_at must be ISO-8601 (e.g. 2026-01-18T06:31:24Z).",
            )
    else:
        parsed = datetime.now(timezone.utc)

    # Normalize into UTC for consistency in notifications.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    parsed_utc = parsed.astimezone(timezone.utc)

    return parsed_utc.strftime("%Y-%m-%d %H:%M UTC")


@router.post(
    "/intern-new-task",
    summary="Send email to mentor when intern creates a new task",
    description=(
        "Looks up mentor and intern recipients via Supabase and sends a new-task notification email via Resend. "
        "Requires RESEND_API_KEY (or legacy RESEND_API-KEY), SUPABASE_URL, SUPABASE_ANON_KEY."
    ),
    operation_id="send_intern_new_task_email",
)
# PUBLIC_INTERFACE
async def send_intern_new_task_email(payload: InternNewTaskRequest) -> SendEmailResponse:
    """Send email notification to mentor when an intern creates a new task.

    Parameters:
        payload: InternNewTaskRequest containing intern/mentor ids, task title, and optional created_at.

    Returns:
        SendEmailResponse with Resend message id and resolved mentor recipient list.
    """
    sb = SupabaseClient()
    resend = ResendClient()

    mentor_email, mentor_name = await _get_user_email_and_name(sb, payload.mentor_id)
    intern_email, intern_name = await _get_user_email_and_name(sb, payload.intern_id)

    when_str = _format_task_created_at(payload.created_at)

    # Subject per user request, but keep consistent with broader system guidance ("T3 Log Update: ...").
    subject = f"T3 Log Update: New Task Submitted: {payload.task_title.strip()}"

    body = (
        f"Hi {mentor_name},\n\n"
        f"{intern_name} has submitted a task titled \"{payload.task_title.strip()}\" on {when_str}.\n"
        "Please check the Mentor Dashboard.\n\n"
        "— Sent by T3 Log notifications"
    )

    # IMPORTANT: For Resend, this must be a verified sender/domain.
    from_email = get_env("RESEND_FROM_EMAIL", "T3 Log <no-reply@t3log.example>")

    # Reuse the existing “Steel Cyan” capable route? Here we send plain text + minimal HTML-ish fallback
    # through the templates used elsewhere. To keep it simple and consistent with existing code,
    # send a lightweight HTML wrapper with the same dark/clean aesthetic.
    html = f"""
<!doctype html>
<html>
  <body style="margin:0;font-family:Arial,Helvetica,sans-serif;background:#0b0b0b;color:#ffffff;">
    <div style="max-width:640px;margin:0 auto;padding:24px;">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:14px;">
        <div style="width:10px;height:10px;border-radius:999px;background:#67e8f9;"></div>
        <h2 style="margin:0;color:#67e8f9;font-size:18px;line-height:1.2;">New Task Submitted</h2>
      </div>

      <div style="border:1px solid #1f2937;background:#111827;border-radius:14px;padding:16px;">
        <p style="margin:0 0 10px 0;color:#e5e7eb;">
          Hi <strong>{mentor_name}</strong>,
        </p>
        <p style="margin:0 0 8px 0;color:#e5e7eb;">
          <strong>{intern_name}</strong> has submitted a task titled
          <strong>“{payload.task_title.strip()}”</strong> on <strong>{when_str}</strong>.
        </p>
        <p style="margin:0;color:#d1d5db;">Please check the Mentor Dashboard.</p>
      </div>

      <p style="margin:16px 0 0 0;color:#9ca3af;font-size:12px;">
        Sent by T3 Log notifications.
      </p>
    </div>
  </body>
</html>
""".strip()

    try:
        resp = await resend.send_email(
            from_email=from_email,
            to_emails=[mentor_email],
            subject=subject,
            text=body,
            html=html,
            reply_to=intern_email,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email via Resend: {e}") from e

    return SendEmailResponse(resend_id=str(resp.get("id", "")), to=[mentor_email])


@router.post(
    "/intern-submission",
    summary="Send email to mentor when intern submits a task update",
    description=(
        "Looks up mentor and intern recipients via Supabase and sends a notification email via Resend. "
        "Requires RESEND_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY."
    ),
    operation_id="send_intern_submission_email",
)
# PUBLIC_INTERFACE
async def send_intern_submission_email(payload: InternSubmissionRequest) -> SendEmailResponse:
    """Send email notification to mentor for a new intern submission.

    Parameters:
        payload: InternSubmissionRequest with intern/mentor ids and task details.

    Returns:
        SendEmailResponse with Resend message id and resolved recipient list.
    """
    sb = SupabaseClient()
    resend = ResendClient()

    mentor_email, mentor_name = await _get_user_email_and_name(sb, payload.mentor_id)
    intern_email, intern_name = await _get_user_email_and_name(sb, payload.intern_id)

    rendered = intern_submission_to_mentor(
        mentor_name=mentor_name,
        intern_name=intern_name,
        task_title=payload.task_title,
        submission_text=payload.submission_text,
    )

    # Configure a default "from" that can be overridden by env.
    # IMPORTANT: For Resend, this must be a verified sender/domain.
    from_email = get_env("RESEND_FROM_EMAIL", "T3 Log <no-reply@t3log.example>")

    try:
        resp = await resend.send_email(
            from_email=from_email,
            to_emails=[mentor_email],
            subject=rendered.subject,
            text=rendered.text,
            html=rendered.html,
            reply_to=intern_email,  # useful for mentors replying directly to interns
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email via Resend: {e}") from e

    return SendEmailResponse(resend_id=str(resp.get("id", "")), to=[mentor_email])


@router.post(
    "/mentor-update",
    summary="Send email to intern when mentor updates task status/remarks",
    description=(
        "Looks up mentor and intern recipients via Supabase and sends a notification email via Resend. "
        "Requires RESEND_API_KEY, SUPABASE_URL, SUPABASE_ANON_KEY."
    ),
    operation_id="send_mentor_update_email",
)
# PUBLIC_INTERFACE
async def send_mentor_update_email(payload: MentorUpdateRequest) -> SendEmailResponse:
    """Send email notification to intern for a mentor update.

    Parameters:
        payload: MentorUpdateRequest with intern/mentor ids and update details.

    Returns:
        SendEmailResponse with Resend message id and resolved recipient list.
    """
    sb = SupabaseClient()
    resend = ResendClient()

    intern_email, intern_name = await _get_user_email_and_name(sb, payload.intern_id)
    mentor_email, mentor_name = await _get_user_email_and_name(sb, payload.mentor_id)

    rendered = mentor_update_to_intern(
        intern_name=intern_name,
        mentor_name=mentor_name,
        task_title=payload.task_title,
        status=payload.status,
        remarks=payload.remarks,
    )

    from_email = get_env("RESEND_FROM_EMAIL", "T3 Log <no-reply@t3log.example>")

    try:
        resp = await resend.send_email(
            from_email=from_email,
            to_emails=[intern_email],
            subject=rendered.subject,
            text=rendered.text,
            html=rendered.html,
            reply_to=mentor_email,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Failed to send email via Resend: {e}") from e

    return SendEmailResponse(resend_id=str(resp.get("id", "")), to=[intern_email])
