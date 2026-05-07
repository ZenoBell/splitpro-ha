"""DataUpdateCoordinator for SplitPro – polls the API and caches results."""
from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import SplitProApiError, SplitProClient
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class SplitProCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinator that fetches data from SplitPro on a schedule."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: SplitProClient,
        scan_interval_minutes: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=scan_interval_minutes),
        )
        self.client = client
        # Store the last seen expense id so we can fire events on new ones
        self._last_expense_ids: set[str] = set()

    async def _async_update_data(self) -> dict[str, Any]:
        """Fetch latest data and fire events for any new expenses."""
        try:
            data = await self.client.get_summary(limit=50)
        except SplitProApiError as err:
            raise UpdateFailed(f"SplitPro API error: {err}") from err

        # ── Fire events for newly detected expenses ───────────────────────────
        recent: list[dict[str, Any]] = data.get("recent_expenses", [])
        new_ids = {exp["id"] for exp in recent}

        if self._last_expense_ids:  # skip on first poll to avoid flood
            newly_added = new_ids - self._last_expense_ids
            for exp in recent:
                if exp["id"] in newly_added:
                    self.hass.bus.async_fire(
                        f"{DOMAIN}_expense_added",
                        {
                            "expense_id": exp["id"],
                            "name": exp["name"],
                            "amount": exp["amount"],
                            "currency": exp["currency"],
                            "my_share": exp["my_share"],
                            "i_paid": exp["i_paid"],
                            "net_effect": exp["net_effect"],
                            "category": exp["category"],
                            "group": exp.get("group"),
                            "paid_by": exp["paid_by"],
                            "date": exp["date"],
                        },
                    )
                    _LOGGER.debug("Fired splitpro_expense_added for %s", exp["name"])

        self._last_expense_ids = new_ids
        return data
