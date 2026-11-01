"""Smart Expense Analyzer Agent — Streamlit web app (Module 1 & 6: input and dashboard)."""
import os
from datetime import date

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

import analysis
import db
import preprocess
from bank import BANKS, get_provider
from agent import ask_agent, offline_insights, spending_review
from categorizer import CATEGORIES, categorize_df
from llm import get_client

st.set_page_config(page_title="Smart Expense Analyzer", page_icon="💸", layout="wide")
db.init_db()

PALETTE = ["#4C78A8", "#F58518", "#54A24B", "#E45756", "#B279A2", "#72B7B2", "#9D9DA3"]


def fig_ax(w=6, h=3.4):
    fig, ax = plt.subplots(figsize=(w, h))
    ax.spines[["top", "right"]].set_visible(False)
    return fig, ax


# ---------------- Sidebar ----------------
with st.sidebar:
    st.title("💸 Expense Analyzer")
    st.caption("Smart Expense Analyzer Agent")
    key = st.text_input("OpenAI API key (optional)", type="password",
                        value=os.getenv("OPENAI_API_KEY", ""),
                        help="Enables the AI agent and AI categorization. Without it, rule-based insights are used.")
    if key:
        os.environ["OPENAI_API_KEY"] = key
    ai_on = get_client() is not None
    st.write("AI agent:", "🟢 online" if ai_on else "⚪ offline (rule-based)")

df = db.get_expenses()
budgets = db.get_budgets()

tab_dash, tab_add, tab_data, tab_budget, tab_agent = st.tabs(
    ["📊 Dashboard", "➕ Add Expenses", "🧾 Transactions", "🎯 Budgets", "🤖 AI Agent"])

# ---------------- Dashboard ----------------
with tab_dash:
    if df.empty:
        st.info("No data yet. Add expenses or upload a CSV in the **Add Expenses** tab "
                "(a sample file is included: `sample_expenses.csv`).")
    else:
        months = sorted(df["date"].dt.strftime("%Y-%m").unique(), reverse=True)
        month = st.selectbox("Month", months)
        m = analysis.filter_month(df, month)
        ov = analysis.overview(df, month)

        prev = None
        idx = months.index(month)
        if idx + 1 < len(months):
            prev = analysis.filter_month(df, months[idx + 1])["amount"].sum()
        delta = None
        if prev:
            delta = f"{(ov['total'] - prev) / prev:+.0%} vs {months[idx + 1]}"

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Total spent", f"₹{ov['total']:,.0f}", delta, delta_color="inverse")
        c2.metric("Transactions", ov["count"])
        c3.metric("Avg / day", f"₹{ov['avg_per_day']:,.0f}")
        c4.metric("Top category", ov["top_category"], f"₹{ov['top_category_amount']:,.0f}", delta_color="off")

        # Alerts
        if budgets:
            bs = analysis.budget_status(df, budgets, month)
            for r in bs.itertuples():
                if r.status == "Over budget":
                    st.error(f"**{r.category}** is over budget: ₹{r.spent:,.0f} of ₹{r.budget:,.0f}")
                elif r.status == "Near limit":
                    st.warning(f"**{r.category}** is at {r.used_pct:.0f}% of its ₹{r.budget:,.0f} budget")

        left, right = st.columns(2)
        with left:
            st.subheader("By category")
            cats = analysis.category_breakdown(m)
            fig, ax = fig_ax()
            ax.pie(cats.values, labels=cats.index, autopct="%1.0f%%", startangle=90,
                   colors=PALETTE[:len(cats)], wedgeprops={"width": 0.45})
            st.pyplot(fig); plt.close(fig)
        with right:
            st.subheader("Daily spending")
            daily = m.groupby(m["date"].dt.date)["amount"].sum()
            fig, ax = fig_ax()
            ax.plot(daily.index, daily.values, marker="o", color=PALETTE[0])
            ax.set_ylabel("₹"); fig.autofmt_xdate()
            st.pyplot(fig); plt.close(fig)

        left, right = st.columns(2)
        with left:
            st.subheader("Weekly totals")
            wk = analysis.period_summary(m, "week")
            fig, ax = fig_ax()
            ax.bar([str(p.start_time.date()) for p in wk.index], wk.values, color=PALETTE[2])
            ax.set_ylabel("₹"); fig.autofmt_xdate()
            st.pyplot(fig); plt.close(fig)
        with right:
            st.subheader("Monthly trend")
            mo = analysis.period_summary(df, "month")
            fig, ax = fig_ax()
            ax.bar([str(p) for p in mo.index], mo.values, color=PALETTE[1])
            ax.set_ylabel("₹")
            st.pyplot(fig); plt.close(fig)

        st.subheader("Unusual expenses")
        unusual = analysis.detect_unusual(m)
        if unusual.empty:
            st.success("Nothing unusual this month.")
        else:
            st.dataframe(unusual[["date", "description", "category", "amount"]],
                         hide_index=True, width="stretch")

        st.subheader("Quick insights")
        for tip in offline_insights(df, budgets):
            st.write("•", tip)

# ---------------- Add expenses ----------------
with tab_add:
    sub_manual, sub_bank = st.tabs(["📝 Manual entry / Upload file", "🏦 Connect bank account"])

    with sub_manual:
        left, right = st.columns(2)
        with left:
            st.subheader("Manual entry")
            with st.form("add_form", clear_on_submit=True):
                d = st.date_input("Date", value=date.today())
                desc = st.text_input("Description", placeholder="e.g. Swiggy dinner")
                amt = st.number_input("Amount (₹)", min_value=0.0, step=10.0)
                cat = st.selectbox("Category", ["Auto-detect"] + CATEGORIES)
                if st.form_submit_button("Add expense"):
                    if not desc.strip() or amt <= 0:
                        st.error("Enter a description and an amount greater than 0.")
                    else:
                        row = pd.DataFrame([{"date": pd.Timestamp(d), "description": desc.strip(), "amount": amt,
                                             "category": None if cat == "Auto-detect" else cat}])
                        row = categorize_df(row, use_llm=ai_on)
                        n = db.add_expenses(row, source="manual")
                        st.success(f"Saved under **{row.iloc[0]['category']}**." if n else "Duplicate, not saved.")
                        st.rerun()
        with right:
            st.subheader("Upload CSV")
            st.caption("Columns: date, description, amount (category optional). Bank-style headers are recognised.")
            up = st.file_uploader("CSV file", type="csv")
            use_ai = st.checkbox("Use AI for unclear descriptions", value=ai_on, disabled=not ai_on)
            if up:
                try:
                    raw = pd.read_csv(up)
                except Exception as e:
                    st.error(f"Could not read file: {e}")
                    raw = None
                if raw is not None:
                    clean_df, issues = preprocess.clean(raw)
                    for i in issues:
                        st.warning(i)
                    if not clean_df.empty:
                        clean_df = categorize_df(clean_df, use_llm=use_ai)
                        st.write(f"{len(clean_df)} valid rows ready:")
                        st.dataframe(clean_df, hide_index=True, width="stretch", height=240)
                        if st.button("Save to database", type="primary"):
                            n = db.add_expenses(clean_df, source="csv")
                            st.success(f"Saved {n} new expense(s).")
                            st.rerun()

    with sub_bank:
        provider = get_provider()
        if provider.demo:
            st.info("**Demo mode:** a simulated bank sandbox is used (OTP `123456`). "
                    "A live setup would use an RBI Account Aggregator such as Setu or Finvu.")
        st.caption("Read-only access: the app only imports debit transactions and cannot move money.")

        conns = db.get_connections()
        if not conns.empty:
            st.subheader("Linked accounts")
            for r in conns.itertuples():
                c1, c2, c3 = st.columns([4, 1.2, 1.2])
                c1.write(f"**{r.bank}** · {r.account_mask}  \nLast synced: {r.last_synced or 'never'}")
                if c2.button("Sync now", key=f"sync_{r.id}"):
                    since = pd.to_datetime(r.last_synced).date() if r.last_synced else None
                    try:
                        raw = provider.fetch_transactions(r.bank, r.account_mask, since)
                        clean_df, _ = preprocess.clean(raw)
                        clean_df = categorize_df(clean_df, use_llm=ai_on)
                        n = db.add_expenses(clean_df, source="bank")
                        db.mark_synced(r.id)
                        st.session_state.bank_msg = f"Imported {n} new transaction(s) from {r.bank}."
                    except Exception as e:
                        st.session_state.bank_msg = f"Sync failed: {e}"
                    st.rerun()
                if c3.button("Disconnect", key=f"rm_{r.id}"):
                    db.remove_connection(r.id)
                    st.rerun()
        if st.session_state.get("bank_msg"):
            st.success(st.session_state.pop("bank_msg"))

        st.subheader("Link a new account")
        step = st.session_state.get("bank_step", 1)
        if step == 1:
            bank = st.selectbox("Bank", BANKS)
            mobile = st.text_input("Mobile number registered with the bank", max_chars=10)
            consent = st.checkbox("I consent to share my transaction data (read-only) with this app.")
            if st.button("Send OTP", disabled=not consent):
                if not (mobile.isdigit() and len(mobile) == 10):
                    st.error("Enter a valid 10-digit mobile number.")
                else:
                    try:
                        provider.send_otp(bank, mobile)
                        st.session_state.update(bank_step=2, bank_pending=(bank, mobile))
                        st.rerun()
                    except Exception as e:
                        st.error(f"Could not start linking: {e}")
        else:
            bank, mobile = st.session_state.bank_pending
            st.write(f"OTP sent to ******{mobile[-4:]} for **{bank}**.")
            otp = st.text_input("Enter OTP", max_chars=6)
            c1, c2 = st.columns(2)
            if c1.button("Verify and link", type="primary"):
                res = provider.verify_otp(bank, mobile, otp)
                if res is None:
                    st.error("Incorrect OTP.")
                else:
                    cid = db.add_connection(bank, res["account_mask"])
                    raw = provider.fetch_transactions(bank, res["account_mask"], None)
                    clean_df, _ = preprocess.clean(raw)
                    clean_df = categorize_df(clean_df, use_llm=ai_on)
                    n = db.add_expenses(clean_df, source="bank")
                    db.mark_synced(cid)
                    st.session_state.bank_msg = f"Linked {bank} and imported {n} transaction(s)."
                    st.session_state.bank_step = 1
                    st.rerun()
            if c2.button("Cancel"):
                st.session_state.bank_step = 1
                st.rerun()

# ---------------- Transactions ----------------
with tab_data:
    if df.empty:
        st.info("No transactions yet.")
    else:
        f = st.multiselect("Filter by category", CATEGORIES)
        view = df[df["category"].isin(f)] if f else df
        st.dataframe(view, hide_index=True, width="stretch")
        st.download_button("Download CSV", view.to_csv(index=False), "expenses.csv", "text/csv")
        with st.expander("Delete a transaction"):
            del_id = st.number_input("Transaction id", min_value=1, step=1)
            if st.button("Delete"):
                db.delete_expense(int(del_id))
                st.rerun()

# ---------------- Budgets ----------------
with tab_budget:
    st.subheader("Monthly budgets")
    st.caption("Set a limit per category (0 = no budget).")
    cols = st.columns(3)
    new = {}
    for i, c in enumerate(CATEGORIES):
        new[c] = cols[i % 3].number_input(c, min_value=0.0, step=500.0, value=float(budgets.get(c, 0.0)),
                                          key=f"b_{c}")
    if st.button("Save budgets", type="primary"):
        db.set_budgets(new)
        st.success("Budgets saved.")
        st.rerun()
    if budgets and not df.empty:
        latest = df["date"].max().strftime("%Y-%m")
        st.subheader(f"Status for {latest}")
        st.dataframe(analysis.budget_status(df, budgets, latest), hide_index=True, width="stretch")

# ---------------- AI agent ----------------
with tab_agent:
    st.subheader("Ask the agent")
    if not ai_on:
        st.info("Add an OpenAI API key in the sidebar for the full agent. Offline mode shows rule-based insights.")
    if st.button("Generate spending review"):
        with st.spinner("Analyzing..."):
            st.markdown(spending_review(df, budgets))
    st.divider()
    if "chat" not in st.session_state:
        st.session_state.chat = []
    for role, text in st.session_state.chat:
        st.chat_message(role).write(text)
    q = st.chat_input("e.g. Why was my spending high last week? Where can I cut costs?")
    if q:
        st.chat_message("user").write(q)
        hist = [{"role": r, "content": t} for r, t in st.session_state.chat[-6:]]
        with st.spinner("Thinking..."):
            ans = ask_agent(q, df, budgets, history=hist)
        st.chat_message("assistant").write(ans)
        st.session_state.chat += [("user", q), ("assistant", ans)]
