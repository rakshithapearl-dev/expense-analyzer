"""Shared OpenAI client helper. The app still works without an API key."""
import os

MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")


def get_client():
    """Return an OpenAI client, or None if no key / package is available."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=key)
    except Exception:
        return None
