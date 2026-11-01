"""Module 4: spending analysis."""
import pandas as pd

PERIOD_CODES = {"day": "D", "week": "W", "month": "M"}


def period_summary(df: pd.DataFrame, period: str = "month") -> pd.Series:
    code = PERIOD_CODES[period]
    return df.groupby(df["date"].dt.to_period(code))["amount"].sum().sort_index()


def category_breakdown(df: pd.DataFrame) -> pd.Series:
    return df.groupby("category")["amount"].sum().sort_values(ascending=False)


def filter_month(df: pd.DataFrame, month: str | None) -> pd.DataFrame:
    """month as 'YYYY-MM'; None returns everything."""
    if not month:
        return df
    return df[df["date"].dt.strftime("%Y-%m") == month]


def budget_status(df: pd.DataFrame, budgets: dict, month: str | None = None) -> pd.DataFrame:
    spent = category_breakdown(filter_month(df, month))
    rows = []
    for cat, limit in budgets.items():
        s = float(spent.get(cat, 0.0))
        pct = s / limit * 100 if limit else 0
        status = "Over budget" if pct > 100 else ("Near limit" if pct >= 80 else "On track")
        rows.append({"category": cat, "budget": limit, "spent": round(s, 2),
                     "remaining": round(limit - s, 2), "used_pct": round(pct, 1), "status": status})
    return pd.DataFrame(rows)


def detect_unusual(df: pd.DataFrame) -> pd.DataFrame:
    """Flag expenses far above the norm for their category (or overall when data is sparse)."""
    if df.empty:
        return df.iloc[0:0]
    flagged = []
    overall_median = df["amount"].median()
    for cat, g in df.groupby("category"):
        if len(g) >= 5:
            thr = g["amount"].mean() + 2 * g["amount"].std()
        else:
            thr = max(3 * overall_median, g["amount"].median() * 3)
        flagged.append(g[g["amount"] > thr])
    out = pd.concat(flagged) if flagged else df.iloc[0:0]
    return out.sort_values("amount", ascending=False)


def overview(df: pd.DataFrame, month: str | None = None) -> dict:
    m = filter_month(df, month)
    if m.empty:
        return {"total": 0, "count": 0}
    days = max((m["date"].max() - m["date"].min()).days + 1, 1)
    cats = category_breakdown(m)
    return {
        "total": round(float(m["amount"].sum()), 2),
        "count": int(len(m)),
        "avg_per_day": round(float(m["amount"].sum()) / days, 2),
        "top_category": cats.index[0],
        "top_category_amount": round(float(cats.iloc[0]), 2),
    }
