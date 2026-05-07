"""SplitPro sensors for Home Assistant."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorEntity,
    SensorStateClass,
)
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .coordinator import SplitProCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up SplitPro sensors."""
    coordinator: SplitProCoordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]

    entities: list[SensorEntity] = [
        # ── Summary sensors ────────────────────────────────────────────────────
        SplitProSummarySensor(
            coordinator=coordinator,
            entry=entry,
            key="total_balance",
            name="SplitPro Total Balance",
            icon="mdi:scale-balance",
            unit="",   # currency depends on user; we store it in attributes
        ),
        SplitProSummarySensor(
            coordinator=coordinator,
            entry=entry,
            key="you_are_owed",
            name="SplitPro You Are Owed",
            icon="mdi:cash-plus",
            unit="",
        ),
        SplitProSummarySensor(
            coordinator=coordinator,
            entry=entry,
            key="you_owe",
            name="SplitPro You Owe",
            icon="mdi:cash-minus",
            unit="",
        ),
        # ── Activity sensors ───────────────────────────────────────────────────
        SplitProLastExpenseSensor(coordinator=coordinator, entry=entry),
        SplitProRecentExpenseCountSensor(coordinator=coordinator, entry=entry),
        # ── Friend balance sensors (created dynamically) ───────────────────────
        # (created below after first data fetch)
    ]

    # Dynamically add one sensor per friend balance
    data = coordinator.data or {}
    for fb in data.get("friend_balances", []):
        entities.append(
            SplitProFriendBalanceSensor(
                coordinator=coordinator,
                entry=entry,
                friend_id=fb["friend_id"],
                friend_name=fb["friend_name"] or fb["friend_email"],
            )
        )

    # Dynamically add one sensor per group balance
    for gb in data.get("group_balances", []):
        entities.append(
            SplitProGroupBalanceSensor(
                coordinator=coordinator,
                entry=entry,
                group_id=gb["group_id"],
                group_name=gb["group_name"],
            )
        )

    async_add_entities(entities, True)


# ── Base class ─────────────────────────────────────────────────────────────────

class SplitProEntity(CoordinatorEntity[SplitProCoordinator], SensorEntity):
    """Base class for all SplitPro sensor entities."""

    def __init__(
        self,
        coordinator: SplitProCoordinator,
        entry: ConfigEntry,
        unique_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_{unique_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="SplitPro",
            manufacturer="SplitPro / oss-apps",
            model="Expense Tracker",
            entry_type=DeviceEntryType.SERVICE,
        )


# ── Summary sensors ────────────────────────────────────────────────────────────

class SplitProSummarySensor(SplitProEntity):
    """Sensor for a top-level summary value (total balance, you owe, you are owed)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self,
        coordinator: SplitProCoordinator,
        entry: ConfigEntry,
        key: str,
        name: str,
        icon: str,
        unit: str,
    ) -> None:
        super().__init__(coordinator, entry, key)
        self._key = key
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_unit_of_measurement = unit or None

    @property
    def native_value(self) -> float | None:
        data = self.coordinator.data
        if not data:
            return None
        return data.get("summary", {}).get(self._key)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        data = self.coordinator.data or {}
        return {
            "user": data.get("user", {}),
            "full_summary": data.get("summary", {}),
        }


# ── Last expense sensor ────────────────────────────────────────────────────────

class SplitProLastExpenseSensor(SplitProEntity):
    """Shows the most recent expense name as state, with full details in attributes."""

    _attr_icon = "mdi:receipt-text"
    _attr_name = "SplitPro Last Expense"

    def __init__(self, coordinator: SplitProCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "last_expense")

    @property
    def native_value(self) -> str | None:
        expenses = (self.coordinator.data or {}).get("recent_expenses", [])
        if not expenses:
            return None
        return expenses[0]["name"]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        expenses = (self.coordinator.data or {}).get("recent_expenses", [])
        if not expenses:
            return {}
        exp = expenses[0]
        return {
            "expense_id": exp["id"],
            "amount": exp["amount"],
            "currency": exp["currency"],
            "my_share": exp["my_share"],
            "i_paid": exp["i_paid"],
            "net_effect": exp["net_effect"],
            "category": exp["category"],
            "group": exp.get("group"),
            "paid_by": exp["paid_by"],
            "date": exp["date"],
        }


# ── Recent expense count sensor ───────────────────────────────────────────────

class SplitProRecentExpenseCountSensor(SplitProEntity):
    """How many expenses are in the recent window (useful for dashboards)."""

    _attr_icon = "mdi:format-list-numbered"
    _attr_name = "SplitPro Recent Expense Count"
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = "expenses"

    def __init__(self, coordinator: SplitProCoordinator, entry: ConfigEntry) -> None:
        super().__init__(coordinator, entry, "recent_expense_count")

    @property
    def native_value(self) -> int:
        expenses = (self.coordinator.data or {}).get("recent_expenses", [])
        return len(expenses)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        expenses = (self.coordinator.data or {}).get("recent_expenses", [])
        return {
            "expenses": [
                {
                    "id": e["id"],
                    "name": e["name"],
                    "amount": e["amount"],
                    "currency": e["currency"],
                    "my_share": e["my_share"],
                    "category": e["category"],
                    "date": e["date"],
                    "group": e.get("group"),
                }
                for e in expenses
            ]
        }


# ── Per-friend balance sensor ──────────────────────────────────────────────────

class SplitProFriendBalanceSensor(SplitProEntity):
    """Balance with a specific friend. Positive = they owe you."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:account-cash"

    def __init__(
        self,
        coordinator: SplitProCoordinator,
        entry: ConfigEntry,
        friend_id: int,
        friend_name: str,
    ) -> None:
        super().__init__(coordinator, entry, f"friend_{friend_id}")
        self._friend_id = friend_id
        self._attr_name = f"SplitPro Balance with {friend_name}"

    @property
    def native_value(self) -> float | None:
        for fb in (self.coordinator.data or {}).get("friend_balances", []):
            if fb["friend_id"] == self._friend_id:
                return fb["net"]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        for fb in (self.coordinator.data or {}).get("friend_balances", []):
            if fb["friend_id"] == self._friend_id:
                return {
                    "friend_id": fb["friend_id"],
                    "friend_name": fb["friend_name"],
                    "friend_email": fb["friend_email"],
                    "net": fb["net"],
                    "direction": "they_owe_you" if fb["net"] > 0 else "you_owe_them",
                }
        return {}


# ── Per-group balance sensor ───────────────────────────────────────────────────

class SplitProGroupBalanceSensor(SplitProEntity):
    """Balance within a specific group."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:account-group"

    def __init__(
        self,
        coordinator: SplitProCoordinator,
        entry: ConfigEntry,
        group_id: int,
        group_name: str,
    ) -> None:
        super().__init__(coordinator, entry, f"group_{group_id}")
        self._group_id = group_id
        self._attr_name = f"SplitPro Group {group_name}"

    @property
    def native_value(self) -> float | None:
        for gb in (self.coordinator.data or {}).get("group_balances", []):
            if gb["group_id"] == self._group_id:
                return gb["net"]
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        for gb in (self.coordinator.data or {}).get("group_balances", []):
            if gb["group_id"] == self._group_id:
                return {
                    "group_id": gb["group_id"],
                    "group_name": gb["group_name"],
                    "net": gb["net"],
                }
        return {}
