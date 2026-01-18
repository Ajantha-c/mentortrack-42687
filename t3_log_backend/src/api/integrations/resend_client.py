from __future__ import annotations

from typing import Any

import httpx

from src.api.core.config import get_env


class ResendClient:
    """Minimal Resend API client for sending emails.

    Note:
        The canonical env var is `RESEND_API_KEY`. However, some environments may
        mistakenly store it as `RESEND_API-KEY` (hyphen). We support that as a
        fallback to reduce configuration friction while keeping the canonical
        name in docs.
    """

    def __init__(self) -> None:
        # Prefer canonical env var name.
        api_key = None
        try:
            api_key = get_env("RESEND_API_KEY")
        except RuntimeError:
            # Fallback to the (common) mis-typed env var name from user input.
            api_key = get_env("RESEND_API-KEY")
        self.api_key = api_key

    async def send_email(
        self,
        *,
        from_email: str,
        to_emails: list[str],
        subject: str,
        text: str,
        html: str | None = None,
        reply_to: str | None = None,
    ) -> dict[str, Any]:
        """Send an email using Resend.

        Args:
            from_email: Sender (must be configured/verified in Resend).
            to_emails: Recipients.
            subject: Email subject.
            text: Plain text body.
            html: Optional HTML body.
            reply_to: Optional reply-to.

        Returns:
            Resend API response JSON.

        Raises:
            httpx.HTTPStatusError: If Resend returns a non-2xx response.
        """
        url = "https://api.resend.com/emails"
        payload: dict[str, Any] = {
            "from": from_email,
            "to": to_emails,
            "subject": subject,
            "text": text,
        }
        if html:
            payload["html"] = html
        if reply_to:
            payload["reply_to"] = reply_to

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            return resp.json()
