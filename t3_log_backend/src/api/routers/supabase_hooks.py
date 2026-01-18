from __future__ import annotations

import hmac
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from src.api.core.config import get_env
from src.api.routers.notifications_email import (
    InternNewTaskRequest,
    MentorUpdateRequest,
    send_intern_new_task_email,
    send_mentor_update_email,
)

router = APIRouter(prefix="/hooks/supabase", tags=["Supabase Hooks"])


def _constant_time_equals(a: str, b: str) -> bool:
    """Constant-time string comparison to avoid timing attacks."""
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


async def _verify_supabase_hook_secret(request: Request) -> None:
    """Verify request contains correct shared secret for Supabase -> backend calls."""
    expected = get_env("SUPABASE_HOOK_SECRET")
    provided = (
        request.headers.get("x-supabase-hook-secret")
        or request.headers.get("x-webhook-secret")
        or request.headers.get("authorization")
        or ""
    ).strip()

    # Allow "Bearer <secret>" as well.
    if provided.lower().startswith("bearer "):
        provided = provided.split(" ", 1)[1].strip()

    if not provided or not _constant_time_equals(provided, expected):
        raise HTTPException(status_code=401, detail="Unauthorized Supabase hook call.")


class SupabaseWebhookPayload(BaseModel):
    """Generic payload shape for Supabase Database Webhooks (table change events)."""

    type: str = Field(..., description="Event type, e.g. INSERT/UPDATE/DELETE.")
    table: str = Field(..., description="Table name that triggered the event.")
    schema: str | None = Field(None, description="Schema name (usually 'public').")
    record: dict[str, Any] | None = Field(
        None, description="New row state for INSERT/UPDATE (if provided)."
    )
    old_record: dict[str, Any] | None = Field(
        None, description="Old row state for UPDATE/DELETE (if provided)."
    )


def _as_str(v: Any) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def _records_differ(old: dict[str, Any] | None, new: dict[str, Any] | None, key: str) -> bool:
    """Return True when a particular column changed between old/new."""
    if not old or not new:
        # If webhook doesn't include old_record, we can't diff reliably.
        return True
    return old.get(key) != new.get(key)


def _extract_task_fields(record: dict[str, Any] | None) -> dict[str, Any]:
    """Extract common task fields from a Supabase webhook record.

    Expected task columns (best effort; supports common variants):
      - intern_id / owner_id / user_id
      - mentor_id
      - title / task_title
      - status
      - mentor_remarks / remarks
      - meeting_datetime / meeting_time / meeting_at
      - created_at
    """
    record = record or {}
    intern_id = _as_str(record.get("intern_id") or record.get("owner_id") or record.get("user_id"))
    mentor_id = _as_str(record.get("mentor_id"))
    task_title = _as_str(record.get("task_title") or record.get("title") or record.get("name"))
    status = _as_str(record.get("status"))
    remarks = _as_str(record.get("mentor_remarks") or record.get("remarks"))
    meeting_datetime = _as_str(
        record.get("meeting_datetime") or record.get("meeting_time") or record.get("meeting_at")
    )
    created_at = _as_str(record.get("created_at"))
    return {
        "intern_id": intern_id,
        "mentor_id": mentor_id,
        "task_title": task_title,
        "status": status,
        "remarks": remarks,
        "meeting_datetime": meeting_datetime,
        "created_at": created_at,
    }


@router.post(
    "/tasks",
    summary="Supabase DB webhook: tasks table change handler",
    description=(
        "Endpoint intended to be called by Supabase Database Webhooks on INSERT/UPDATE events "
        "for the `tasks` table. It triggers the existing server-side email notification routes.\n\n"
        "Security: caller must include header `x-supabase-hook-secret: <SUPABASE_HOOK_SECRET>` "
        "(or Authorization: Bearer <SUPABASE_HOOK_SECRET>)."
    ),
    operation_id="supabase_tasks_webhook",
)
# PUBLIC_INTERFACE
async def supabase_tasks_webhook(
    payload: SupabaseWebhookPayload,
    request: Request,
    _auth: None = Depends(_verify_supabase_hook_secret),
) -> dict[str, Any]:
    """Handle Supabase `tasks` table events and trigger notification emails.

    Parameters:
        payload: Supabase webhook payload including event type and record(s).
        request: FastAPI request (used for shared-secret verification).

    Returns:
        JSON object describing whether an email trigger was executed and why.

    Raises:
        HTTPException: On auth failure or invalid payload for required notifications.
    """
    # Only handle tasks table; ignore if misconfigured.
    if payload.table.lower() != "tasks":
        return {"ok": True, "ignored": True, "reason": f"Unhandled table: {payload.table}"}

    event_type = payload.type.upper().strip()

    # INSERT -> Intern -> Mentor new task email
    if event_type == "INSERT":
        fields = _extract_task_fields(payload.record)

        if not fields["intern_id"] or not fields["mentor_id"] or not fields["task_title"]:
            raise HTTPException(
                status_code=422,
                detail=(
                    "tasks INSERT webhook missing required fields. "
                    "Need intern_id (or owner_id/user_id), mentor_id, and task_title (or title/name)."
                ),
            )

        req = InternNewTaskRequest(
            intern_id=fields["intern_id"],
            mentor_id=fields["mentor_id"],
            task_title=fields["task_title"],
            created_at=fields["created_at"],
        )
        resp = await send_intern_new_task_email(req)
        return {"ok": True, "action": "intern-new-task", "email": resp.model_dump()}

    # UPDATE -> Mentor -> Intern status/remarks email (only if status or mentor remarks changed)
    if event_type == "UPDATE":
        new_fields = _extract_task_fields(payload.record)

        if not new_fields["intern_id"] or not new_fields["mentor_id"] or not new_fields["task_title"]:
            raise HTTPException(
                status_code=422,
                detail=(
                    "tasks UPDATE webhook missing required fields. "
                    "Need intern_id (or owner_id/user_id), mentor_id, and task_title (or title/name)."
                ),
            )

        # Only trigger when these fields change. If old_record is missing, we conservatively trigger.
        status_changed = _records_differ(payload.old_record, payload.record, "status")
        remarks_changed = _records_differ(payload.old_record, payload.record, "mentor_remarks") or _records_differ(
            payload.old_record, payload.record, "remarks"
        )
        meeting_changed = _records_differ(payload.old_record, payload.record, "meeting_datetime") or _records_differ(
            payload.old_record, payload.record, "meeting_time"
        )

        if not (status_changed or remarks_changed or meeting_changed):
            return {"ok": True, "ignored": True, "reason": "No relevant field changes."}

        req = MentorUpdateRequest(
            intern_id=new_fields["intern_id"],
            mentor_id=new_fields["mentor_id"],
            task_title=new_fields["task_title"],
            status=new_fields["status"],
            remarks=new_fields["remarks"],
            meeting_datetime=new_fields["meeting_datetime"],
        )
        resp = await send_mentor_update_email(req)
        return {
            "ok": True,
            "action": "mentor-update",
            "triggered_by": {
                "status_changed": status_changed,
                "remarks_changed": remarks_changed,
                "meeting_changed": meeting_changed,
            },
            "email": resp.model_dump(),
            "processed_at": datetime.utcnow().isoformat() + "Z",
        }

    # Ignore other events
    return {"ok": True, "ignored": True, "reason": f"Unhandled event type: {payload.type}"}
