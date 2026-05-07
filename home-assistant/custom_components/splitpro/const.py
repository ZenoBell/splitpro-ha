"""Constants for the SplitPro integration."""

DOMAIN = "splitpro"

# Config entry keys
CONF_URL = "url"                # e.g. https://splitpro.yourdomain.com
CONF_API_KEY = "api_key"        # HA_API_KEY set in SplitPro .env
CONF_USER_EMAIL = "user_email"  # the SplitPro account to scope data to
CONF_SCAN_INTERVAL = "scan_interval"  # polling interval in minutes

DEFAULT_SCAN_INTERVAL = 5  # minutes

# Data coordinator key
DATA_COORDINATOR = "coordinator"

# Platforms this integration provides
PLATFORMS = ["sensor"]

# Services the integration exposes
SERVICE_ADD_EXPENSE = "add_expense"
SERVICE_DELETE_EXPENSE = "delete_expense"

# Attribute names
ATTR_EXPENSE_ID = "expense_id"
ATTR_EXPENSE_NAME = "expense_name"
ATTR_EXPENSE_AMOUNT = "expense_amount"
ATTR_EXPENSE_CURRENCY = "expense_currency"
ATTR_EXPENSE_CATEGORY = "expense_category"
ATTR_EXPENSE_PARTICIPANTS = "participants"
ATTR_EXPENSE_GROUP_ID = "group_id"
ATTR_EXPENSE_PAID_BY = "paid_by_email"
ATTR_EXPENSE_DATE = "expense_date"
ATTR_SPLIT_EQUALLY = "split_equally"

# Events fired by this integration
EVENT_EXPENSE_ADDED = f"{DOMAIN}_expense_added"
EVENT_EXPENSE_DELETED = f"{DOMAIN}_expense_deleted"
