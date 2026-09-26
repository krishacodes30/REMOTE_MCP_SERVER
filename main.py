from fastmcp import FastMCP
import os
import sqlite3
import json
from typing import Optional
from dotenv import load_dotenv
import libsql
# ============================================================
# CONFIG
# ============================================================

load_dotenv()

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


TURSO_DATABASE_URL = os.getenv("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.getenv("TURSO_AUTH_TOKEN")

if not TURSO_DATABASE_URL:
    raise RuntimeError("TURSO_DATABASE_URL is not set")

if not TURSO_AUTH_TOKEN:
    raise RuntimeError("TURSO_AUTH_TOKEN is not set")


CATEGORIES_PATH = os.path.join(BASE_DIR, "categories.json")

mcp = FastMCP("ExpenseTracker")


def get_db():
    return libsql.connect(
        database=TURSO_DATABASE_URL,
        auth_token=TURSO_AUTH_TOKEN
    )


# ============================================================
# DATABASE
# ============================================================

def init_db():
    """Create the expenses table if it doesn't already exist."""

    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses(
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                subcategory TEXT DEFAULT '',
                note TEXT DEFAULT ''
            )
        """)

        conn.commit()


init_db()


# ============================================================
# CATEGORY HELPERS
# ============================================================

def load_categories():
    """Load categories.json and return it as a Python dictionary."""

    with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_category(category: str, subcategory: str = ""):
    """
    Validate category and optional subcategory against categories.json.

    Returns:
        (True, None) if valid
        (False, error_message) if invalid
    """

    categories = load_categories()

    category = category.strip().lower()
    subcategory = subcategory.strip().lower()

    if category not in categories:
        return (
            False,
            f"Invalid category '{category}'. "
            f"Valid categories are: {', '.join(categories.keys())}"
        )

    if subcategory and subcategory not in categories[category]:
        return (
            False,
            f"Invalid subcategory '{subcategory}' for category '{category}'. "
            f"Valid subcategories are: "
            f"{', '.join(categories[category])}"
        )

    return True, None


# ============================================================
# ADD EXPENSE
# ============================================================

@mcp.tool()
def add_expense(
    date: str,
    amount: float,
    category: str,
    subcategory: str = "",
    note: str = ""
):
    """
    Add a new expense.

    Category and subcategory must exist in categories.json.
    """

    if amount <= 0:
        return {
            "status": "error",
            "message": "Amount must be greater than 0."
        }

    valid, error = validate_category(category, subcategory)

    if not valid:
        return {
            "status": "error",
            "message": error
        }

    category = category.strip().lower()
    subcategory = subcategory.strip().lower()

    with get_db() as conn:

        cur = conn.execute(
            """
            INSERT INTO expenses
            (date, amount, category, subcategory, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                date,
                amount,
                category,
                subcategory,
                note
            )
        )

        conn.commit()

        return {
            "status": "ok",
            "id": cur.lastrowid,
            "date": date,
            "amount": amount,
            "category": category,
            "subcategory": subcategory,
            "note": note
        }


# ============================================================
# UPDATE EXPENSE
# ============================================================

@mcp.tool()
def update_expense(
    id: int,
    date: Optional[str] = None,
    amount: Optional[float] = None,
    category: Optional[str] = None,
    subcategory: Optional[str] = None,
    note: Optional[str] = None
):
    """
    Update an existing expense.

    Only fields explicitly provided are updated.
    """

    fields = {}

    if date is not None:
        fields["date"] = date

    if amount is not None:

        if amount <= 0:
            return {
                "status": "error",
                "message": "Amount must be greater than 0."
            }

        fields["amount"] = amount

    if category is not None:
        category = category.strip().lower()
        fields["category"] = category

    if subcategory is not None:
        subcategory = subcategory.strip().lower()
        fields["subcategory"] = subcategory

    if note is not None:
        fields["note"] = note

    if not fields:
        return {
            "status": "error",
            "message": "No fields provided to update."
        }

    # --------------------------------------------------------
    # Get existing record if category/subcategory is changing
    # --------------------------------------------------------

    if category is not None or subcategory is not None:

        with get_db() as conn:

            cur = conn.execute(
                """
                SELECT category, subcategory
                FROM expenses
                WHERE id = ?
                """,
                (id,)
            )

            existing = cur.fetchone()

        if existing is None:
            return {
                "status": "error",
                "message": f"No expense found with id {id}"
            }

        final_category = (
            category
            if category is not None
            else existing[0]
        )

        final_subcategory = (
            subcategory
            if subcategory is not None
            else existing[1]
        )

        valid, error = validate_category(
            final_category,
            final_subcategory
        )

        if not valid:
            return {
                "status": "error",
                "message": error
            }

    # --------------------------------------------------------
    # Perform update
    # --------------------------------------------------------

    set_clause = ", ".join(
        f"{key} = ?"
        for key in fields
    )

    params = list(fields.values())
    params.append(id)

    with get_db() as conn:

        cur = conn.execute(
            f"""
            UPDATE expenses
            SET {set_clause}
            WHERE id = ?
            """,
            params
        )

        conn.commit()

        if cur.rowcount == 0:
            return {
                "status": "error",
                "message": f"No expense found with id {id}"
            }

    return {
        "status": "ok",
        "id": id,
        "updated_fields": list(fields.keys())
    }


# ============================================================
# DELETE EXPENSE
# ============================================================

@mcp.tool()
def delete_expense(id: int):
    """Delete an expense by ID."""

    with get_db() as conn:

        cur = conn.execute(
            """
            DELETE FROM expenses
            WHERE id = ?
            """,
            (id,)
        )

        conn.commit()

        if cur.rowcount == 0:
            return {
                "status": "error",
                "message": f"No expense found with id {id}"
            }

    return {
        "status": "ok",
        "id": id,
        "deleted": True
    }


# ============================================================
# LIST EXPENSES
# ============================================================

@mcp.tool()
def list_expenses(
    start_date: str,
    end_date: str
):
    """
    List expenses between start_date and end_date.

    Both dates are inclusive.
    """

    with get_db() as conn:

        cur = conn.execute(
            """
            SELECT
                id,
                date,
                amount,
                category,
                subcategory,
                note
            FROM expenses
            WHERE date BETWEEN ? AND ?
            ORDER BY date ASC, id ASC
            """,
            (
                start_date,
                end_date
            )
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        rows = cur.fetchall()

    return [
        dict(zip(columns, row))
        for row in rows
    ]


# ============================================================
# SUMMARY BY CATEGORY
# ============================================================

@mcp.tool()
def summarize(
    start_date: str,
    end_date: str,
    category: Optional[str] = None
):
    """
    Summarize total expenses by category.

    If category is provided, only that category is summarized.
    """

    query = """
        SELECT
            category,
            SUM(amount) AS total_amount
        FROM expenses
        WHERE date BETWEEN ? AND ?
    """

    params = [
        start_date,
        end_date
    ]

    if category:

        category = category.strip().lower()

        query += """
            AND category = ?
        """

        params.append(category)

    query += """
        GROUP BY category
        ORDER BY total_amount DESC
    """

    with get_db() as conn:

        cur = conn.execute(
            query,
            params
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        rows = cur.fetchall()

    return [
        dict(zip(columns, row))
        for row in rows
    ]


# ============================================================
# SUMMARY BY SUBCATEGORY
# ============================================================

@mcp.tool()
def summarize_by_subcategory(
    start_date: str,
    end_date: str,
    category: Optional[str] = None
):
    """
    Summarize expenses by category and subcategory.
    """

    query = """
        SELECT
            category,
            subcategory,
            SUM(amount) AS total_amount
        FROM expenses
        WHERE date BETWEEN ? AND ?
    """

    params = [
        start_date,
        end_date
    ]

    if category:

        category = category.strip().lower()

        query += """
            AND category = ?
        """

        params.append(category)

    query += """
        GROUP BY category, subcategory
        ORDER BY total_amount DESC
    """

    with get_db() as conn:

        cur = conn.execute(
            query,
            params
        )

        columns = [
            description[0]
            for description in cur.description
        ]

        rows = cur.fetchall()

    return [
        dict(zip(columns, row))
        for row in rows
    ]


# ============================================================
# CATEGORIES RESOURCE
# ============================================================

@mcp.resource(
    "expense://categories",
    mime_type="application/json"
)
def categories():
    """
    Return the current category/subcategory definitions.

    The file is read every time, so changes to categories.json
    are available without restarting the MCP server.
    """

    with open(
        CATEGORIES_PATH,
        "r",
        encoding="utf-8"
    ) as f:

        return f.read()


# ============================================================
# RUN SERVER
# ============================================================



# Start the server
if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8000)
    # mcp.run()
# if __name__ == "__main__":
#     mcp.run()