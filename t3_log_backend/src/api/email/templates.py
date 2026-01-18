from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text: str
    html: str


def _escape(s: str) -> str:
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def intern_submission_to_mentor(
    *,
    mentor_name: str,
    intern_name: str,
    task_title: str,
    submission_text: str | None,
) -> RenderedEmail:
    subject = f"New task submission from {intern_name}: {task_title}"
    safe_mentor = _escape(mentor_name)
    safe_intern = _escape(intern_name)
    safe_task = _escape(task_title)
    safe_body = _escape(submission_text or "(No additional details provided)")

    text = (
        f"Hi {mentor_name},\n\n"
        f"{intern_name} submitted a task update.\n\n"
        f"Task: {task_title}\n\n"
        f"Submission:\n{submission_text or '(No additional details provided)'}\n"
    )

    html = f"""
<!doctype html>
<html>
  <body style="margin:0;font-family:Arial,Helvetica,sans-serif;background:#0b0b0b;color:#ffffff;">
    <div style="max-width:640px;margin:0 auto;padding:24px;">
      <h2 style="margin:0 0 12px 0;color:#F97316;">New Task Submission</h2>
      <p style="margin:0 0 16px 0;color:#e5e7eb;">Hi {safe_mentor},</p>

      <div style="border:1px solid #1f2937;background:#111827;border-radius:14px;padding:16px;">
        <p style="margin:0 0 8px 0;color:#e5e7eb;">
          <strong>{safe_intern}</strong> submitted an update for:
        </p>
        <p style="margin:0 0 12px 0;font-size:16px;"><strong>{safe_task}</strong></p>
        <pre style="white-space:pre-wrap;margin:0;background:#0b1220;padding:12px;border-radius:12px;border:1px solid #1f2937;color:#d1d5db;">{safe_body}</pre>
      </div>

      <p style="margin:16px 0 0 0;color:#9ca3af;font-size:12px;">
        Sent by T3 Log notifications.
      </p>
    </div>
  </body>
</html>
""".strip()

    return RenderedEmail(subject=subject, text=text, html=html)


def mentor_update_to_intern(
    *,
    intern_name: str,
    mentor_name: str,
    task_title: str,
    status: str | None,
    remarks: str | None,
) -> RenderedEmail:
    subject = f"Mentor update: {task_title}"
    safe_intern = _escape(intern_name)
    safe_mentor = _escape(mentor_name)
    safe_task = _escape(task_title)
    safe_status = _escape(status or "Updated")
    safe_remarks = _escape(remarks or "(No remarks provided)")

    text = (
        f"Hi {intern_name},\n\n"
        f"{mentor_name} left an update on your task.\n\n"
        f"Task: {task_title}\n"
        f"Status: {status or 'Updated'}\n\n"
        f"Remarks:\n{remarks or '(No remarks provided)'}\n"
    )

    html = f"""
<!doctype html>
<html>
  <body style="margin:0;font-family:Arial,Helvetica,sans-serif;background:#0b0b0b;color:#ffffff;">
    <div style="max-width:640px;margin:0 auto;padding:24px;">
      <h2 style="margin:0 0 12px 0;color:#10B981;">Mentor Update</h2>
      <p style="margin:0 0 16px 0;color:#e5e7eb;">Hi {safe_intern},</p>

      <div style="border:1px solid #1f2937;background:#111827;border-radius:14px;padding:16px;">
        <p style="margin:0 0 8px 0;color:#e5e7eb;">
          <strong>{safe_mentor}</strong> updated your task:
        </p>
        <p style="margin:0 0 6px 0;font-size:16px;"><strong>{safe_task}</strong></p>
        <p style="margin:0 0 12px 0;color:#d1d5db;"><strong>Status:</strong> {safe_status}</p>
        <pre style="white-space:pre-wrap;margin:0;background:#0b1220;padding:12px;border-radius:12px;border:1px solid #1f2937;color:#d1d5db;">{safe_remarks}</pre>
      </div>

      <p style="margin:16px 0 0 0;color:#9ca3af;font-size:12px;">
        Sent by T3 Log notifications.
      </p>
    </div>
  </body>
</html>
""".strip()

    return RenderedEmail(subject=subject, text=text, html=html)
