"""SQLite storage layer."""
import sqlite3
from contextlib import closing
from pathlib import Path

import pandas as pd

DB_PATH = Path(__file__).parent / "expenses.db"


def _conn():
    return sqlite3.connect(DB_PATH)


def init_db():
    with closing(_conn()) as c:
        c.execute(
            """CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'manual'
            )"""
        )
        cols = [r[1] for r in c.execute("PRAGMA table_info(expenses)")]
        if "source" not in cols:  # migrate databases created by an earlier version
            c.execute("ALTER TABLE expenses ADD COLUMN source TEXT NOT NULL DEFAULT 'manual'")
        c.execute(
            """CREATE TABLE IF NOT EXISTS bank_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bank TEXT NOT NULL,
                account_mask TEXT NOT NULL,
                linked_at TEXT NOT NULL,
                last_synced TEXT,
                UNIQUE (bank, account_mask)
            )"""
        )
        c.execute(
            """CREATE TABLE IF NOT EXISTS budgets (
                category TEXT PRIMARY KEY,
                monthly_limit REAL NOT NULL
            )"""
        )
        c.commit()


def add_expenses(df: pd.DataFrame, source: str = "manual") -> int:
    """Insert rows (date, description, amount, category); skips exact duplicates."""
    if df.empty:
        return 0
    existing = get_expenses()
    seen = set()
    if not existing.empty:
        seen = set(zip(existing["date"].dt.strftime("%Y-%m-%d"),
                       existing["description"], existing["amount"].round(2)))
    rows = []
    for r in df.itertuples():
        key = (r.date.strftime("%Y-%m-%d"), r.description, round(float(r.amount), 2))
        if key in seen:
            continue
        seen.add(key)
        rows.append((key[0], r.description, float(r.amount), r.category, source))
    with closing(_conn()) as c:
        c.executemany(
            "INSERT INTO expenses (date, description, amount, category, source) VALUES (?,?,?,?,?)", rows
        )
        c.commit()
    return len(rows)


def get_expenses() -> pd.DataFrame:
    with closing(_conn()) as c:
        df = pd.read_sql_query("SELECT * FROM expenses ORDER BY date DESC, id DESC", c)
    df["date"] = pd.to_datetime(df["date"])
    return df


def delete_expense(expense_id: int):
    with closing(_conn()) as c:
        c.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        c.commit()


def set_budgets(budgets: dict):
    with closing(_conn()) as c:
        for cat, limit in budgets.items():
            if limit and limit > 0:
                c.execute(
                    "INSERT INTO budgets (category, monthly_limit) VALUES (?, ?) "
                    "ON CONFLICT(category) DO UPDATE SET monthly_limit = excluded.monthly_limit",
                    (cat, float(limit)),
                )
            else:
                c.execute("DELETE FROM budgets WHERE category = ?", (cat,))
        c.commit()


def get_budgets() -> dict:
    with closing(_conn()) as c:
        rows = c.execute("SELECT category, monthly_limit FROM budgets").fetchall()
    return dict(rows)


# ---------- bank connections ----------
def add_connection(bank: str, account_mask: str) -> int:
    with closing(_conn()) as c:
        c.execute("INSERT OR IGNORE INTO bank_connections (bank, account_mask, linked_at) "
                  "VALUES (?, ?, datetime('now'))", (bank, account_mask))
        c.commit()
        return c.execute("SELECT id FROM bank_connections WHERE bank=? AND account_mask=?",
                         (bank, account_mask)).fetchone()[0]


def get_connections() -> pd.DataFrame:
    with closing(_conn()) as c:
        return pd.read_sql_query("SELECT * FROM bank_connections ORDER BY id", c)


def mark_synced(conn_id: int):
    with closing(_conn()) as c:
        c.execute("UPDATE bank_connections SET last_synced = datetime('now') WHERE id = ?", (conn_id,))
        c.commit()


def remove_connection(conn_id: int):
    with closing(_conn()) as c:
        c.execute("DELETE FROM bank_connections WHERE id = ?", (conn_id,))
        c.commit()
