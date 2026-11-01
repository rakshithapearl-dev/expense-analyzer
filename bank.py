"""Bank connection layer (provider pattern).

Real bank linking in India goes through a regulated Account Aggregator (AA) such as
Setu or Finvu: the user gives consent via OTP, then the AA returns read-only transactions.
This project ships a simulated sandbox provider so the full flow works offline and in a demo.
To go live, implement `AccountAggregatorProvider` and set BANK_PROVIDER=aa.
"""
import hashlib
import os
import random
from abc import ABC, abstractmethod
from datetime import date, timedelta

import pandas as pd

BANKS = ["State Bank of India", "HDFC Bank", "ICICI Bank", "Axis Bank", "Canara Bank", "Indian Bank"]
COLUMNS = ["date", "description", "amount"]


class BankProvider(ABC):
    name: str = "provider"
    demo: bool = False

    @abstractmethod
    def send_otp(self, bank: str, mobile: str) -> None:
        """Start the consent flow (sends an OTP to the registered mobile)."""

    @abstractmethod
    def verify_otp(self, bank: str, mobile: str, otp: str) -> dict | None:
        """Return {'account_mask': ...} on success, None if the OTP is wrong."""

    @abstractmethod
    def fetch_transactions(self, bank: str, account_mask: str, since: date | None) -> pd.DataFrame:
        """Return debit transactions with columns: date, description, amount."""


# Recurring bank-style narrations: (template, min, max)
_DAILY = [
    ("UPI/SWIGGY/{ref}", 150, 450), ("UPI/ZOMATO/{ref}", 150, 500), ("UPI/STARBUCKS/{ref}", 200, 420),
    ("UPI/BIGBASKET/{ref}", 500, 2000), ("UPI/UBER/{ref}", 100, 400), ("UPI/RAPIDO/{ref}", 60, 250),
    ("POS/PETROL PUMP/{ref}", 500, 1500), ("POS/AMAZON/{ref}", 300, 6000), ("POS/MYNTRA/{ref}", 600, 2500),
    ("UPI/APOLLO PHARMACY/{ref}", 120, 800), ("UPI/PVR CINEMAS/{ref}", 350, 900),
]
_MONTHLY = {1: ("NEFT/RENT/{ref}", 8000, 8000), 3: ("ECOM/NETFLIX/{ref}", 649, 649),
            5: ("NEFT/ELECTRICITY BILL/{ref}", 900, 1500), 7: ("ECOM/JIO RECHARGE/{ref}", 299, 299)}


class MockBankProvider(BankProvider):
    """Deterministic simulated bank. Demo OTP is 123456."""
    name = "Demo bank sandbox"
    demo = True
    DEMO_OTP = "123456"

    def send_otp(self, bank, mobile):
        return None

    def verify_otp(self, bank, mobile, otp):
        if otp.strip() != self.DEMO_OTP:
            return None
        h = int(hashlib.sha256(f"{bank}|{mobile}".encode()).hexdigest()[:8], 16)
        return {"account_mask": f"XXXXXX{h % 10000:04d}"}

    def fetch_transactions(self, bank, account_mask, since=None):
        end = date.today()
        d = since or end - timedelta(days=60)
        rows = []
        while d <= end:
            rng = random.Random(f"{bank}|{account_mask}|{d.isoformat()}")  # stable per day -> safe re-sync
            picks = [rng.choice(_DAILY) for _ in range(rng.choice([0, 1, 1, 2, 2, 3]))]
            if d.day in _MONTHLY:
                picks.append(_MONTHLY[d.day])
            for tmpl, lo, hi in picks:
                rows.append({"date": d, "description": tmpl.format(ref=rng.randint(100000, 999999)),
                             "amount": float(round(rng.uniform(lo, hi)))})
            d += timedelta(days=1)
        return pd.DataFrame(rows, columns=COLUMNS)


class AccountAggregatorProvider(BankProvider):
    """Placeholder for a real RBI Account Aggregator integration (e.g. Setu, Finvu)."""
    name = "Account Aggregator"

    def _todo(self):
        raise NotImplementedError("Add your AA provider credentials and API calls here.")

    def send_otp(self, bank, mobile): self._todo()
    def verify_otp(self, bank, mobile, otp): self._todo()
    def fetch_transactions(self, bank, account_mask, since=None): self._todo()


def get_provider() -> BankProvider:
    return AccountAggregatorProvider() if os.getenv("BANK_PROVIDER") == "aa" else MockBankProvider()
