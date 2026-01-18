from __future__ import annotations

from typing import Any

import httpx

from src.api.core.config import get_env


class SupabaseClient:
    """Minimal Supabase REST client.

    Uses PostgREST endpoints to query tables. This keeps the backend lightweight
    and avoids requiring the full supabase-py dependency for simple lookups.
    """

    def __init__(self) -> None:
        self.supabase_url = get_env("SUPABASE_URL").rstrip("/")
        self.supabase_anon_key = get_env("SUPABASE_ANON_KEY")

    def _headers(self) -> dict[str, str]:
        # Supabase PostgREST expects both apikey and Authorization header.
        return {
            "apikey": self.supabase_anon_key,
            "Authorization": f"Bearer {self.supabase_anon_key}",
            "Content-Type": "application/json",
        }

    async def select_single(
        self,
        table: str,
        filters: dict[str, str],
        columns: str = "*",
    ) -> dict[str, Any] | None:
        """Select a single row from a Supabase table.

        Args:
            table: Table name.
            filters: Simple equality filters {column: value}.
            columns: PostgREST select clause.

        Returns:
            Row dict if found, else None.

        Raises:
            httpx.HTTPStatusError: If Supabase returns a non-2xx response.
        """
        url = f"{self.supabase_url}/rest/v1/{table}"
        params: dict[str, str] = {"select": columns, "limit": "1"}
        for k, v in filters.items():
            params[k] = f"eq.{v}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, headers=self._headers(), params=params)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list) and len(data) > 0:
                return data[0]
            return None
