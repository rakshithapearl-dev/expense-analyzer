"""Module 3: cleaning, standardization and validation of incoming data."""
import pandas as pd

ALIASES = {
    "date": ["date", "transaction date", "txn date", "value date", "day"],
    "description": ["description", "details", "narration", "particulars", "merchant", "item", "remarks"],
    "amount": ["amount", "debit", "withdrawal", "withdrawal amt.", "cost", "price", "value"],
    "category": ["category", "type", "group"],
}


def _standardize_columns(df: pd.DataFrame) -> pd.DataFrame:
    lookup = {a: std for std, names in ALIASES.items() for a in names}
    renamed, used = {}, set()
    for col in df.columns:
        std = lookup.get(str(col).strip().lower())
        if std and std not in used:
            renamed[col] = std
            used.add(std)
    return df.rename(columns=renamed)


def clean(df: pd.DataFrame):
    """Return (clean_df, issues). clean_df has: date, description, amount, category(optional)."""
    issues = []
    df = _standardize_columns(df.copy())
    missing = [c for c in ("date", "description", "amount") if c not in df.columns]
    if missing:
        return pd.DataFrame(columns=["date", "description", "amount"]), [
            f"Missing required column(s): {', '.join(missing)}. "
            "Expected columns: date, description, amount (category optional)."
        ]

    n0 = len(df)
    df["description"] = df["description"].astype(str).str.strip()
    df["amount"] = pd.to_numeric(
        df["amount"].astype(str).str.replace(r"[^\d.\-]", "", regex=True), errors="coerce"
    )
    raw_dates = df["date"].astype(str).str.strip()
    df["date"] = pd.to_datetime(raw_dates, format="ISO8601", errors="coerce")  # 2026-09-12
    rest = df["date"].isna()
    if rest.any():  # bank-style dates such as 12/09/2026 are read day-first
        df.loc[rest, "date"] = pd.to_datetime(raw_dates[rest], errors="coerce", dayfirst=True)

    bad = df["date"].isna() | df["amount"].isna() | (df["amount"] <= 0) | (df["description"] == "")
    if bad.sum():
        issues.append(f"Dropped {int(bad.sum())} invalid row(s) (bad date, amount or empty description).")
    df = df[~bad]

    before = len(df)
    df = df.drop_duplicates(subset=["date", "description", "amount"])
    if before - len(df):
        issues.append(f"Removed {before - len(df)} duplicate row(s).")

    if "category" in df.columns:
        df["category"] = df["category"].astype(str).str.strip().str.title()
    cols = ["date", "description", "amount"] + (["category"] if "category" in df.columns else [])
    return df[cols].reset_index(drop=True), issues
