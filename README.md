# SplitPro Home Assistant Integration

This custom component connects Home Assistant to a self-hosted [SplitPro](https://github.com/oss-apps/split-pro) instance. It polls the `/api/ha/summary` endpoint on a configurable schedule and exposes your expense-sharing balances as sensors. It also registers two services (`splitpro.add_expense` and `splitpro.delete_expense`) so automations can create or remove expenses, and fires HA events whenever an expense is added or deleted.

---

## Prerequisites

- A **self-hosted** SplitPro instance (the integration calls private `/api/ha/*` endpoints that are not available on the hosted version).
- The `HA_API_KEY` environment variable set in your SplitPro deployment (e.g. in `.env`). All requests from HA carry this key in the `X-HA-Api-Key` header.
- Home Assistant **2024.1 or later** (uses `ConfigFlowResult` typing introduced in 2024.1).

---

## Installation

This integration is not in HACS. Install it manually:

1. Copy the `custom_components/splitpro/` directory into your Home Assistant configuration directory so the path looks like:

   ```
   <ha-config>/custom_components/splitpro/
   ```

2. Restart Home Assistant.

3. Go to **Settings → Devices & Services → Add Integration** and search for **SplitPro**.

---

## Configuration

The setup form contains the following fields:

| Field         | Key             | Required | Default | Description                                                             |
| ------------- | --------------- | -------- | ------- | ----------------------------------------------------------------------- |
| URL           | `url`           | Yes      | —       | Base URL of your SplitPro instance, e.g. `https://splitpro.example.com` |
| API Key       | `api_key`       | Yes      | —       | Value of `HA_API_KEY` in your SplitPro environment                      |
| User Email    | `user_email`    | Yes      | —       | SplitPro account email whose balances are fetched                       |
| Scan Interval | `scan_interval` | No       | `5`     | Polling interval in minutes (1–60)                                      |

During setup the integration contacts the summary endpoint to validate the credentials. If validation succeeds, a config entry is created titled `SplitPro – <display name>`.

Duplicate entries for the same URL + email combination are rejected.

---

## Sensors

All sensors belong to a single virtual device named **SplitPro** (type: service).

### Summary Sensors

Three sensors reflect the aggregate balance across all friends and groups.

| Entity name            | State                                             | State class   |
| ---------------------- | ------------------------------------------------- | ------------- |
| SplitPro Total Balance | Net balance across all friends and groups (float) | `measurement` |
| SplitPro You Are Owed  | `max(0, total_balance)` (float)                   | `measurement` |
| SplitPro You Owe       | `abs(min(0, total_balance))` (float)              | `measurement` |

**Attributes** (same for all three):

| Attribute      | Description                                                                        |
| -------------- | ---------------------------------------------------------------------------------- |
| `user`         | Object — `{ id, name, email }` for the configured account                          |
| `full_summary` | Object — `{ total_balance, friend_balance, group_balance, you_are_owed, you_owe }` |

> Note: balances sum all currencies without conversion. If you hold balances in multiple currencies the numeric total is not meaningful on its own. See [Multi-Currency](#multi-currency) for how to access per-currency breakdowns from the raw API response.

---

### Per-Friend Balance Sensors

One sensor is created per friend who has a non-zero balance with you (hidden friends and zero-balance friends are excluded).

**Entity name:** `SplitPro Balance with <friend name or email>`

**State:** `net` (float) — positive means the friend owes you, negative means you owe them.

**Attributes:**

| Attribute      | Description                                                                   |
| -------------- | ----------------------------------------------------------------------------- |
| `friend_id`    | Internal SplitPro user ID                                                     |
| `friend_name`  | Display name, or `null` for users who were invited but have not yet signed up |
| `friend_email` | Email address, or `null` for uninvited/anonymous participants                 |
| `net`          | Same as state                                                                 |
| `direction`    | `"they_owe_you"` when net > 0, `"you_owe_them"` otherwise                     |

The raw API response for each friend also contains a `currencies` array (`[{ currency, amount }]`, sorted by absolute amount descending) that gives the per-currency breakdown. This field is not currently exposed as a sensor attribute — to use it, call the `/api/ha/summary` endpoint directly or parse it from a `rest` sensor.

---

### Per-Group Balance Sensors

One sensor is created per group the configured user belongs to.

**Entity name:** `SplitPro Group <group name>`

**State:** `net` (float) — your signed balance within the group.

**Attributes:**

| Attribute    | Description                |
| ------------ | -------------------------- |
| `group_id`   | Internal SplitPro group ID |
| `group_name` | Group display name         |
| `net`        | Same as state              |

The raw API response for each group also contains a `currencies` array (`[{ currency, amount }]`, sorted by absolute amount descending) for per-currency accuracy when the group has multi-currency expenses. Like friend balances, this field is not currently exposed as a sensor attribute — access it directly from the API or via a `rest` sensor.

---

### Last Expense Sensor

**Entity name:** `SplitPro Last Expense`

**State:** Name (string) of the most recently dated expense you participated in.

**Attributes:**

| Attribute    | Description                                                        |
| ------------ | ------------------------------------------------------------------ |
| `expense_id` | Expense ID (use this with `splitpro.delete_expense`)               |
| `amount`     | Total expense amount                                               |
| `currency`   | ISO 4217 currency code                                             |
| `my_share`   | Your share of the expense                                          |
| `i_paid`     | Boolean — whether you were the payer                               |
| `net_effect` | Signed financial impact (see below)                                |
| `category`   | Expense category string                                            |
| `group`      | `{ id, name }` if the expense belongs to a group, otherwise `null` |
| `paid_by`    | `{ name, email }` of the user who paid                             |
| `date`       | ISO 8601 datetime string                                           |

**`net_effect` formula:** `i_paid ? total - my_share : -my_share`

- When `i_paid` is `true` (you paid): positive value — you are owed the total minus your own share.
- When `i_paid` is `false` (someone else paid): negative value — you owe your share.

Example: a $60 dinner split equally among 4 people. Your share is $15.

- If you paid: `net_effect = 60 - 15 = 45` (three people owe you)
- If someone else paid: `net_effect = -15` (you owe your share)

---

### Recent Expense Count Sensor

**Entity name:** `SplitPro Recent Expense Count`

**State:** Integer count of expenses in the polling window. Unit: `expenses`.

**Attributes:**

| Attribute  | Description                                                                                                                  |
| ---------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `expenses` | Array of recent expense objects, each containing `id`, `name`, `amount`, `currency`, `my_share`, `category`, `date`, `group` |

The integration fetches the 50 most recent expenses (ordered by date descending); this limit is hard-coded in the coordinator.

---

## Events

### `splitpro_expense_added`

Fired when a new expense is detected during polling, **or** immediately when `splitpro.add_expense` is called as a service.

When fired from **polling** (expense detected on refresh), the event data contains:

| Field        | Type           | Description                                                                         |
| ------------ | -------------- | ----------------------------------------------------------------------------------- |
| `expense_id` | string         | Expense ID                                                                          |
| `name`       | string         | Expense name                                                                        |
| `amount`     | float          | Total amount                                                                        |
| `currency`   | string         | ISO 4217 currency code                                                              |
| `my_share`   | float          | Your share                                                                          |
| `i_paid`     | bool           | Whether you paid                                                                    |
| `net_effect` | float          | Signed impact — negative = you owe, positive = you are owed (net of your own share) |
| `category`   | string         | Expense category                                                                    |
| `group`      | object or null | `{ id, name }` if part of a group                                                   |
| `paid_by`    | object         | `{ name, email }` of the payer                                                      |
| `date`       | string         | ISO 8601 expense date                                                               |

Example payload (polling path):

```yaml
expense_id: 'clx123abc'
name: 'Groceries'
amount: 60.00
currency: 'USD'
my_share: 20.00
i_paid: false
net_effect: -20.00
category: 'food'
group: null
paid_by:
  name: 'Alice'
  email: 'alice@example.com'
date: '2024-06-01T00:00:00.000Z'
```

When fired from a **service call**, the event data is a shorter subset:

| Field        | Type   | Description                     |
| ------------ | ------ | ------------------------------- |
| `expense_id` | string | ID of the newly created expense |
| `name`       | string | Expense name                    |
| `amount`     | float  | Total amount                    |
| `currency`   | string | ISO 4217 currency code          |
| `source`     | string | Always `"service_call"`         |

---

### `splitpro_expense_deleted`

Fired immediately when `splitpro.delete_expense` is called.

| Field        | Type   | Description               |
| ------------ | ------ | ------------------------- |
| `expense_id` | string | ID of the deleted expense |
| `source`     | string | Always `"service_call"`   |

Example payload:

```yaml
expense_id: 'clx123abc'
source: 'service_call'
```

> Deletion is a soft-delete — the expense remains visible in the SplitPro activity feed.

---

## Services

### `splitpro.add_expense`

Creates a new expense in SplitPro. After a successful API call the sensors are refreshed immediately.

| Parameter     | Key                | Required | Default   | Description                                                                                                           |
| ------------- | ------------------ | -------- | --------- | --------------------------------------------------------------------------------------------------------------------- |
| Name          | `expense_name`     | Yes      | —         | Description of the expense, e.g. `"Dinner at Mario's"`                                                                |
| Amount        | `expense_amount`   | Yes      | —         | Total amount in major units (e.g. `45.50`)                                                                            |
| Participants  | `participants`     | Yes      | —         | List of participant email addresses including yourself                                                                |
| Currency      | `expense_currency` | No       | `USD`     | ISO 4217 currency code                                                                                                |
| Category      | `expense_category` | No       | `general` | One of: `general`, `food`, `transport`, `utilities`, `entertainment`, `health`, `shopping`, `travel`, `rent`, `other` |
| Split Equally | `split_equally`    | No       | `true`    | Divide equally among all participants                                                                                 |
| Group ID      | `group_id`         | No       | —         | SplitPro group ID (find it in the group's URL)                                                                        |
| Paid By       | `paid_by_email`    | No       | —         | Email of the payer (defaults to the configured account)                                                               |
| Date          | `expense_date`     | No       | —         | Expense date in `YYYY-MM-DD` format (defaults to today)                                                               |

**Automation example — log every expense added via voice or script:**

```yaml
automation:
  - alias: 'Log new SplitPro expense'
    trigger:
      - platform: event
        event_type: splitpro_expense_added
    action:
      - service: notify.persistent_notification
        data:
          title: 'New Expense'
          message: >
            {{ trigger.event.data.name }}: {{ trigger.event.data.amount }}
            {{ trigger.event.data.currency }}

script:
  add_grocery_expense:
    alias: 'Add grocery split'
    sequence:
      - service: splitpro.add_expense
        data:
          expense_name: 'Groceries'
          expense_amount: 85.40
          participants:
            - me@example.com
            - roommate@example.com
          expense_currency: USD
          expense_category: food
          split_equally: true
```

---

### `splitpro.delete_expense`

Soft-deletes an expense. The `expense_id` can be found in the `expense_id` attribute of the **SplitPro Last Expense** sensor or in the `expenses` list of the **SplitPro Recent Expense Count** sensor.

| Parameter  | Key          | Required | Description                 |
| ---------- | ------------ | -------- | --------------------------- |
| Expense ID | `expense_id` | Yes      | ID of the expense to delete |

**Example:**

```yaml
service: splitpro.delete_expense
data:
  expense_id: 'clx123abc'
```

---

## Multi-Currency

The `net` value on all balance sensors sums amounts across all currencies as plain numbers without any currency conversion. If you and a friend share expenses in both USD and EUR, the numeric `net` will be misleading.

For accurate per-currency totals, use the `currencies` array returned by the `/api/ha/summary` endpoint for each friend and group balance. Each entry has the shape `{ currency: "EUR", amount: -30.00 }`, sorted by absolute amount descending. This field is not currently exposed as a sensor attribute; access it by calling the endpoint directly or by configuring a [`rest` sensor](https://www.home-assistant.io/integrations/rest/) pointed at the summary URL.

---

## Troubleshooting

| Symptom                                         | Likely cause                                        | Fix                                                                                                 |
| ----------------------------------------------- | --------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| Integration shows "Invalid auth" during setup   | Wrong `api_key` or `HA_API_KEY` not set in SplitPro | Verify `HA_API_KEY` is set in your SplitPro `.env` and matches what you entered                     |
| Integration shows "User not found" during setup | `user_email` does not match any account             | Use the exact email address of an existing SplitPro account                                         |
| Integration shows "Cannot connect"              | Wrong URL or SplitPro is unreachable from HA        | Check the URL (no trailing slash needed), ensure SplitPro is running and reachable from the HA host |
| Sensors are `unavailable` after setup           | API error on the first or subsequent polls          | Check HA logs (`Settings → System → Logs`) for `splitpro` entries                                   |
| Friend/group sensors do not appear              | No non-zero balances exist yet                      | Add an expense in SplitPro, then reload the integration                                             |
| `splitpro.add_expense` fails silently           | API returned an error                               | Check HA logs — errors are logged at `ERROR` level with the reason                                  |
| Duplicate config entry error                    | Same URL + email already configured                 | The integration prevents duplicate entries; remove the existing entry first                         |
