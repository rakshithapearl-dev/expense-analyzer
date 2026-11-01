"""Module 2: expense categorization (rules first, optional LLM fallback)."""
import json

from llm import MODEL, get_client

CATEGORIES = ["Food", "Travel", "Shopping", "Bills", "Entertainment", "Healthcare", "Others"]

KEYWORDS = {
    "Food": ["swiggy", "zomato", "restaurant", "cafe", "coffee", "tea", "lunch", "dinner", "breakfast",
             "biryani", "pizza", "burger", "grocery", "groceries", "supermarket", "bigbasket",
             "blinkit", "zepto", "snack", "bakery", "mess", "canteen", "food", "starbucks", "dominos"],
    "Travel": ["uber", "ola", "rapido", "metro", "bus", "train", "irctc", "flight", "indigo", "petrol",
               "fuel", "diesel", "cab", "auto", "taxi", "toll", "parking", "redbus", "ticket"],
    "Shopping": ["amazon", "flipkart", "myntra", "ajio", "mall", "clothes", "shoes", "shirt", "meesho",
                 "nykaa", "decathlon", "electronics", "headphones", "gadget", "shopping"],
    "Bills": ["electricity", "water bill", "recharge", "airtel", "jio", "vodafone", "broadband", "wifi",
              "rent", "gas", "insurance", "emi", "fees", "tuition", "subscription fee", "bill", "dth"],
    "Entertainment": ["netflix", "prime video", "hotstar", "spotify", "movie", "cinema", "pvr", "inox",
                      "bookmyshow", "game", "steam", "concert", "youtube premium", "gaming"],
    "Healthcare": ["pharmacy", "medical", "medicine", "hospital", "doctor", "clinic", "apollo", "lab test",
                   "dental", "gym", "health", "diagnostic", "1mg", "pharmeasy"],
}


def categorize(description: str) -> str:
    text = str(description).lower()
    best, best_len = "Others", 0
    for cat, words in KEYWORDS.items():
        for w in words:
            if w in text and len(w) > best_len:
                best, best_len = cat, len(w)
    return best


def llm_categorize(descriptions: list) -> dict:
    """Classify unclear descriptions with the LLM. Returns {description: category}; {} on failure."""
    client = get_client()
    descriptions = list(dict.fromkeys(descriptions))
    if client is None or not descriptions:
        return {}
    try:
        resp = client.chat.completions.create(
            model=MODEL,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": (
                    "Classify each expense description into exactly one of: "
                    f"{', '.join(CATEGORIES)}. Reply with a JSON object mapping each description "
                    "to its category.")},
                {"role": "user", "content": json.dumps(descriptions)},
            ],
        )
        data = json.loads(resp.choices[0].message.content)
        return {d: c for d, c in data.items() if c in CATEGORIES}
    except Exception:
        return {}


def categorize_df(df, use_llm: bool = False):
    """Fill the 'category' column: keep valid user-supplied values, rule-based otherwise."""
    df = df.copy()
    if "category" not in df.columns:
        df["category"] = None
    valid = df["category"].isin(CATEGORIES)
    df.loc[~valid, "category"] = df.loc[~valid, "description"].map(categorize)
    if use_llm:
        unclear = df[(~valid) & (df["category"] == "Others")]["description"].tolist()
        mapping = llm_categorize(unclear)
        if mapping:
            mask = (~valid) & (df["category"] == "Others")
            df.loc[mask, "category"] = df.loc[mask, "description"].map(mapping).fillna("Others")
    return df
