# Smart Expense Analyzer Agent

Streamlit web app that records, categorizes and analyzes expenses, and uses an LLM agent (OpenAI tool calling) to give personalized budgeting advice.

## Run
```bash
pip install -r requirements.txt
export OPENAI_API_KEY=sk-...      # optional; Windows: set OPENAI_API_KEY=sk-...
streamlit run app.py
```
Without an API key the app still works (rule-based categorization and insights).
Try it with `sample_expenses.csv` via **Add Expenses → Upload CSV**.

## Structure (maps to the 6 modules)
| File | Module |
|---|---|
| `app.py` | 1 Data collection (manual entry, CSV upload, bank connection), 6 Dashboard & visualization |
| `bank.py` | 1 Bank connection layer: demo sandbox now, Account Aggregator (Setu/Finvu) pluggable |
| `categorizer.py` | 2 Expense categorization (keyword rules + LLM fallback) |
| `preprocess.py`, `db.py` | 3 Data processing & SQLite storage |
| `analysis.py` | 4 Expense analysis (summaries, budgets, unusual expenses) |
| `agent.py`, `llm.py` | 5 AI agent: LLM chooses tools, then writes insights |
