"""Module 5: the AI agent. The LLM decides which analysis tools to call, then answers."""
import json

import pandas as pd

import analysis
from llm import MODEL, get_client

SYSTEM_PROMPT = (
    "You are a Smart Expense Analyzer Agent for personal finance. Amounts are in rupees (₹). "
    "Always use the tools to get real numbers before answering; never invent figures. "
    "Be concise and practical: point out high-spending categories, unusual expenses, budget "
    "issues, and give specific, actionable suggestions."
)

TOOLS = [
    {"type": "function", "function": {
        "name": "get_spending_summary",
        "description": "Total spending per day, week or month.",
        "parameters": {"type": "object", "properties": {
            "period": {"type": "string", "enum": ["day", "week", "month"]},
            "last_n": {"type": "integer", "description": "Only the most recent N periods (default 6)"}},
            "required": ["period"]}}},
    {"type": "function", "function": {
        "name": "get_category_breakdown",
        "description": "Spending per category, optionally for one month (YYYY-MM).",
        "parameters": {"type": "object", "properties": {"month": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "check_budgets",
        "description": "Compare spending with the user's monthly budgets, optionally for one month (YYYY-MM).",
        "parameters": {"type": "object", "properties": {"month": {"type": "string"}}}}},
    {"type": "function", "function": {
        "name": "find_unusual_expenses",
        "description": "List expenses that are unusually high for their category.",
        "parameters": {"type": "object", "properties": {}}}},
    {"type": "function", "function": {
        "name": "search_expenses",
        "description": "Search transactions by keyword, category or minimum amount.",
        "parameters": {"type": "object", "properties": {
            "keyword": {"type": "string"}, "category": {"type": "string"},
            "min_amount": {"type": "number"}}}}},
]


def _records(df: pd.DataFrame, limit: int = 20) -> list:
    out = df.head(limit).copy()
    out["date"] = out["date"].dt.strftime("%Y-%m-%d")
    return out[["date", "description", "amount", "category"]].to_dict("records")


def run_tool(name: str, args: dict, df: pd.DataFrame, budgets: dict):
    if name == "get_spending_summary":
        s = analysis.period_summary(df, args.get("period", "month")).tail(args.get("last_n", 6))
        return {str(k): round(float(v), 2) for k, v in s.items()}
    if name == "get_category_breakdown":
        s = analysis.category_breakdown(analysis.filter_month(df, args.get("month")))
        return {k: round(float(v), 2) for k, v in s.items()}
    if name == "check_budgets":
        if not budgets:
            return {"note": "No budgets set by the user."}
        return analysis.budget_status(df, budgets, args.get("month")).to_dict("records")
    if name == "find_unusual_expenses":
        return _records(analysis.detect_unusual(df))
    if name == "search_expenses":
        m = df
        if args.get("keyword"):
            m = m[m["description"].str.contains(args["keyword"], case=False, na=False)]
        if args.get("category"):
            m = m[m["category"].str.lower() == args["category"].lower()]
        if args.get("min_amount") is not None:
            m = m[m["amount"] >= args["min_amount"]]
        return _records(m)
    return {"error": f"unknown tool {name}"}


def ask_agent(question: str, df: pd.DataFrame, budgets: dict, history: list | None = None,
              max_steps: int = 6) -> str:
    client = get_client()
    if client is None:
        return "AI agent is offline (no OpenAI API key set).\n\n" + "\n".join(
            f"- {x}" for x in offline_insights(df, budgets))
    if df.empty:
        return "No expenses recorded yet. Add some expenses first."

    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + (history or []) + [
        {"role": "user", "content": question}]
    try:
        for _ in range(max_steps):
            resp = client.chat.completions.create(model=MODEL, messages=messages, tools=TOOLS)
            msg = resp.choices[0].message
            if not msg.tool_calls:
                return msg.content or ""
            messages.append(msg)
            for call in msg.tool_calls:
                args = json.loads(call.function.arguments or "{}")
                result = run_tool(call.function.name, args, df, budgets)
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": json.dumps(result, default=str)})
        return "I couldn't finish the analysis in the allowed number of steps. Try a narrower question."
    except Exception as e:
        return f"AI agent error: {e}\n\n" + "\n".join(f"- {x}" for x in offline_insights(df, budgets))


def spending_review(df: pd.DataFrame, budgets: dict) -> str:
    return ask_agent(
        "Review my spending. Cover: where most money goes, how this month compares with last month, "
        "any budget problems, any unusual expenses, and 3-5 specific actions to save money.",
        df, budgets)


def offline_insights(df: pd.DataFrame, budgets: dict) -> list:
    """Rule-based fallback so the app works without an API key."""
    if df.empty:
        return ["No expenses recorded yet."]
    tips = []
    cats = analysis.category_breakdown(df)
    total = cats.sum()
    tips.append(f"Highest spending: {cats.index[0]} (₹{cats.iloc[0]:,.0f}, {cats.iloc[0] / total:.0%} of total).")
    months = analysis.period_summary(df, "month")
    if len(months) >= 2 and months.iloc[-2] > 0:
        ch = (months.iloc[-1] - months.iloc[-2]) / months.iloc[-2]
        tips.append(f"Spending {'rose' if ch > 0 else 'fell'} {abs(ch):.0%} versus the previous month.")
    for r in analysis.detect_unusual(df).head(3).itertuples():
        tips.append(f"Unusual expense: {r.description} (₹{r.amount:,.0f}) on {r.date:%d %b}.")
    if budgets:
        latest = df["date"].max().strftime("%Y-%m")
        for r in analysis.budget_status(df, budgets, latest).itertuples():
            if r.status != "On track":
                tips.append(f"{r.category}: {r.status.lower()} ({r.used_pct:.0f}% of ₹{r.budget:,.0f}).")
    return tips
