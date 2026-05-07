"""SplitPro Home Assistant Integration."""
from __future__ import annotations

import logging

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .api import SplitProApiError, SplitProClient
from .const import (
    ATTR_EXPENSE_AMOUNT,
    ATTR_EXPENSE_CATEGORY,
    ATTR_EXPENSE_CURRENCY,
    ATTR_EXPENSE_DATE,
    ATTR_EXPENSE_GROUP_ID,
    ATTR_EXPENSE_ID,
    ATTR_EXPENSE_NAME,
    ATTR_EXPENSE_PAID_BY,
    ATTR_EXPENSE_PARTICIPANTS,
    ATTR_SPLIT_EQUALLY,
    CONF_API_KEY,
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_USER_EMAIL,
    DATA_COORDINATOR,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_ADD_EXPENSE,
    SERVICE_DELETE_EXPENSE,
)
from .coordinator import SplitProCoordinator

_LOGGER = logging.getLogger(__name__)

# ── Service schemas ────────────────────────────────────────────────────────────

ADD_EXPENSE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_EXPENSE_NAME): cv.string,
        vol.Required(ATTR_EXPENSE_AMOUNT): vol.Coerce(float),
        vol.Required(ATTR_EXPENSE_PARTICIPANTS): vol.All(
            cv.ensure_list, [cv.string]
        ),
        vol.Optional(ATTR_EXPENSE_CURRENCY, default="USD"): cv.string,
        vol.Optional(ATTR_EXPENSE_CATEGORY, default="general"): cv.string,
        vol.Optional(ATTR_SPLIT_EQUALLY, default=True): cv.boolean,
        vol.Optional(ATTR_EXPENSE_GROUP_ID): cv.string,
        vol.Optional(ATTR_EXPENSE_PAID_BY): cv.string,
        vol.Optional(ATTR_EXPENSE_DATE): cv.string,
    }
)

DELETE_EXPENSE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_EXPENSE_ID): cv.string,
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up SplitPro from a config entry."""
    session = async_get_clientsession(hass)

    client = SplitProClient(
        session=session,
        base_url=entry.data[CONF_URL],
        api_key=entry.data[CONF_API_KEY],
        user_email=entry.data[CONF_USER_EMAIL],
    )

    coordinator = SplitProCoordinator(
        hass=hass,
        client=client,
        scan_interval_minutes=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )

    # Do the first refresh so sensors have data immediately
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        DATA_COORDINATOR: coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # ── Register services ──────────────────────────────────────────────────────

    async def handle_add_expense(call: ServiceCall) -> None:
        """Handle the splitpro.add_expense service call."""
        try:
            result = await client.add_expense(
                name=call.data[ATTR_EXPENSE_NAME],
                amount=call.data[ATTR_EXPENSE_AMOUNT],
                participants=call.data[ATTR_EXPENSE_PARTICIPANTS],
                currency=call.data.get(ATTR_EXPENSE_CURRENCY, "USD"),
                category=call.data.get(ATTR_EXPENSE_CATEGORY, "general"),
                split_equally=call.data.get(ATTR_SPLIT_EQUALLY, True),
                group_id=call.data.get(ATTR_EXPENSE_GROUP_ID),
                paid_by_email=call.data.get(ATTR_EXPENSE_PAID_BY),
                expense_date=call.data.get(ATTR_EXPENSE_DATE),
            )
            _LOGGER.info("SplitPro expense created: %s (id=%s)", result["name"], result["id"])
            # Fire event so automations can react
            hass.bus.async_fire(
                f"{DOMAIN}_expense_added",
                {
                    "expense_id": result["id"],
                    "name": result["name"],
                    "amount": result["amount"],
                    "currency": result["currency"],
                    "source": "service_call",
                },
            )
            # Refresh sensors immediately
            await coordinator.async_request_refresh()
        except SplitProApiError as err:
            _LOGGER.error("Failed to add SplitPro expense: %s", err)

    async def handle_delete_expense(call: ServiceCall) -> None:
        """Handle the splitpro.delete_expense service call."""
        expense_id: str = call.data[ATTR_EXPENSE_ID]
        try:
            await client.delete_expense(expense_id)
            _LOGGER.info("SplitPro expense deleted: %s", expense_id)
            hass.bus.async_fire(
                f"{DOMAIN}_expense_deleted",
                {"expense_id": expense_id, "source": "service_call"},
            )
            await coordinator.async_request_refresh()
        except SplitProApiError as err:
            _LOGGER.error("Failed to delete SplitPro expense %s: %s", expense_id, err)

    hass.services.async_register(
        DOMAIN, SERVICE_ADD_EXPENSE, handle_add_expense, schema=ADD_EXPENSE_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DELETE_EXPENSE, handle_delete_expense, schema=DELETE_EXPENSE_SCHEMA
    )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)

    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
        # Remove services when last entry unloaded
        if not hass.data[DOMAIN]:
            hass.services.async_remove(DOMAIN, SERVICE_ADD_EXPENSE)
            hass.services.async_remove(DOMAIN, SERVICE_DELETE_EXPENSE)

    return unload_ok
