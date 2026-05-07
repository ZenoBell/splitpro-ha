"""HTTP client for the SplitPro HA API endpoints."""
from __future__ import annotations

import logging
from typing import Any

import aiohttp

_LOGGER = logging.getLogger(__name__)


class SplitProApiError(Exception):
    """Raised when the SplitPro API returns an error."""


class SplitProClient:
    """Async HTTP client for /api/ha/* endpoints."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        base_url: str,
        api_key: str,
        user_email: str,
    ) -> None:
        self._session = session
        # Strip trailing slash
        self._base = base_url.rstrip("/")
        self._headers = {"X-HA-Api-Key": api_key, "Content-Type": "application/json"}
        self._user_email = user_email

    # ── Read endpoints ────────────────────────────────────────────────────────

    async def get_summary(self, limit: int = 20) -> dict[str, Any]:
        """Fetch full balance + recent expense summary for the configured user."""
        url = f"{self._base}/api/ha/summary"
        params = {"user_email": self._user_email, "limit": str(limit)}
        return await self._get(url, params)

    async def get_groups(self) -> list[dict[str, Any]]:
        """Fetch all groups the user belongs to."""
        url = f"{self._base}/api/ha/groups"
        params = {"user_email": self._user_email}
        data = await self._get(url, params)
        return data.get("groups", [])

    # ── Write endpoints ───────────────────────────────────────────────────────

    async def add_expense(
        self,
        name: str,
        amount: float,
        participants: list[str],
        currency: str = "USD",
        category: str = "general",
        split_equally: bool = True,
        group_id: str | None = None,
        paid_by_email: str | None = None,
        expense_date: str | None = None,
    ) -> dict[str, Any]:
        """Create a new expense."""
        url = f"{self._base}/api/ha/expenses"
        payload: dict[str, Any] = {
            "user_email": self._user_email,
            "name": name,
            "amount": amount,
            "currency": currency,
            "category": category,
            "split_equally": split_equally,
            "participants": participants,
        }
        if group_id:
            payload["group_id"] = group_id
        if paid_by_email:
            payload["paid_by_email"] = paid_by_email
        if expense_date:
            payload["expense_date"] = expense_date

        return await self._post(url, payload)

    async def delete_expense(self, expense_id: str) -> dict[str, Any]:
        """Soft-delete an expense by ID."""
        url = f"{self._base}/api/ha/expenses/{expense_id}"
        return await self._delete(url, {"user_email": self._user_email})

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _get(
        self, url: str, params: dict[str, str] | None = None
    ) -> dict[str, Any]:
        try:
            async with self._session.get(
                url, headers=self._headers, params=params, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                return await self._handle(resp)
        except aiohttp.ClientError as err:
            raise SplitProApiError(f"Network error reaching SplitPro: {err}") from err

    async def _post(self, url: str, json: dict[str, Any]) -> dict[str, Any]:
        try:
            async with self._session.post(
                url, headers=self._headers, json=json, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                return await self._handle(resp)
        except aiohttp.ClientError as err:
            raise SplitProApiError(f"Network error reaching SplitPro: {err}") from err

    async def _delete(self, url: str, params: dict[str, str]) -> dict[str, Any]:
        try:
            async with self._session.delete(
                url, headers=self._headers, params=params, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                return await self._handle(resp)
        except aiohttp.ClientError as err:
            raise SplitProApiError(f"Network error reaching SplitPro: {err}") from err

    @staticmethod
    async def _handle(resp: aiohttp.ClientResponse) -> dict[str, Any]:
        if resp.status == 401:
            raise SplitProApiError("Invalid API key (401)")
        if resp.status == 404:
            raise SplitProApiError("Resource not found (404)")
        if resp.status >= 400:
            body = await resp.text()
            raise SplitProApiError(f"SplitPro API error {resp.status}: {body}")
        return await resp.json()
