"""
core/langtrace/pricing.py
━━━━━━━━━━━━━━━━━━━━━━━━━
Pricing schemas and token counting engine for LangTrace.
"""

import tiktoken

# ── MODEL PRICING DICT (per 1 Million tokens, in USD) ────────────────────────
MODEL_PRICING = {
    "kimi-k2.5": {"input": 1.00 / 1e6, "output": 2.00 / 1e6},
    "gemini-2.5-pro": {"input": 1.25 / 1e6, "output": 5.00 / 1e6},
    "gemini-2.5-flash": {"input": 0.075 / 1e6, "output": 0.30 / 1e6},
    "gpt-4o-mini": {"input": 0.15 / 1e6, "output": 0.60 / 1e6},
}


def get_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Calculates USD cost of an LLM call based on token usage and model type."""
    model_name_lower = model_name.lower()
    matched_key = None
    for key in MODEL_PRICING:
        if key in model_name_lower:
            matched_key = key
            break

    pricing = MODEL_PRICING.get(matched_key, {"input": 1.00 / 1e6, "output": 3.00 / 1e6})
    return (input_tokens * pricing["input"]) + (output_tokens * pricing["output"])


def count_tokens(text: str, model_name: str = "gpt-4") -> int:
    """Estimates token count of a given string using tiktoken."""
    if not text:
        return 0
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except Exception:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))
