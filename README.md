

## Connect to Claude

Server URL: **https://sparkling-amber-spoonbill.fastmcp.app/mcp**

1. Open **claude.ai** and go to **Settings → Connectors**.
2. Click **Add custom connector**.
3. Paste the server URL above into the **URL** field.
4. Give it a name (e.g. `Expense Tracker`) and click **Add**.
5. Open a new chat, click the tools/connector icon, and enable **Expense Tracker** for that chat.
6. Start using it — e.g. *"Add a ₹250 grocery expense for today"* or *"Summarize my spending this month by category."*

> Same steps work in **Claude Desktop** and **Claude Code** — just add it as an MCP server pointing to the same URL instead of via the web Settings page.

## Tools

| Tool | Description |
|---|---|
| `add_expense(date, amount, category, subcategory="", note="")` | Add a new expense. Category/subcategory validated against `categories.json`. |
| `update_expense(id, date=None, amount=None, category=None, subcategory=None, note=None)` | Partial update — only provided fields change. |
| `delete_expense(id)` | Delete an expense by ID. |
| `list_expenses(start_date, end_date)` | List all expenses in an inclusive date range. |
| `summarize(start_date, end_date, category=None)` | Total spend per category (optionally filtered to one category). |
| `summarize_by_subcategory(start_date, end_date, category=None)` | Total spend broken down by category + subcategory. |

## Resources

| Resource | Description |
|---|---|
| `expense://categories` | Returns the full category/subcategory taxonomy as JSON. |

## Categories

Categories and subcategories live in `categories.json` — edit that file to add/rename categories; no code changes or restart needed. Current top-level categories:

`food`, `transport`, `housing`, `utilities`, `health`, `education`, `family_kids`, `entertainment`, `shopping`, `subscriptions`, `personal_care`, `gifts_donations`, `finance_fees`, `business`, `travel`, `home`, `pet`, `taxes`, `investments`, `misc`



## Setup

**1. Install deps**
```bash
uv sync
# or: pip install -e .
```

**2. Set up a Turso database**
```bash
turso db create expense-tracker
turso db show expense-tracker --url
turso db tokens create expense-tracker
```

**3. Configure environment**

Create a `.env` file in the project root:
```env
TURSO_DATABASE_URL=libsql://<your-db>.turso.io
TURSO_AUTH_TOKEN=<your-auth-token>
```

**4. Run the server**
```bash
fastmcp run
# or directly:
python main.py
```

Server starts on `http://0.0.0.0:8000` (HTTP transport).

## Notes

- Amounts must be `> 0` — validated on both `add` and `update`.
- All category/subcategory strings are lowercased + trimmed before storage.
- The `expenses` table auto-creates on first DB connection (`get_db()`), no separate migration step.
