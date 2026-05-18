"""Map publisher-specific rating strings to the project's 4-class scheme.

Targets `config.VERDICT_OPTIONS`:
  Supported · Refuted · Not Enough Evidence · Conflicting Evidence

Rule-based maps cover 7 of the 8 curated publishers. Full Fact uses
free-text ratings and is handled by an LLM call against Groq.
"""
from __future__ import annotations

import json

import requests

from config import (
    EXTRACTION_API_KEY as GROQ_API_KEY,
    EXTRACTION_BASE_URL as GROQ_BASE_URL,
    EXTRACTION_MODEL as GROQ_MODEL,
    VERDICT_OPTIONS,
)

SUPPORTED, REFUTED, NEI, CE = VERDICT_OPTIONS  # for readability

# Per-publisher mappings. Keys are lowercased stripped rating strings.
# Anything not in the map falls through to None → handled by caller.
RULES: dict[str, dict[str, str]] = {
    "politifact.com": {
        "true": SUPPORTED,
        "mostly true": SUPPORTED,
        "half true": CE,
        "mostly false": REFUTED,
        "false": REFUTED,
        "pants on fire": REFUTED,
        "pants on fire!": REFUTED,
    },
    "snopes.com": {
        "true": SUPPORTED,
        "mostly true": SUPPORTED,
        "mixture": CE,
        "mostly false": REFUTED,
        "false": REFUTED,
        "unproven": NEI,
        "outdated": NEI,
        "fake": REFUTED,
        "correct attribution": SUPPORTED,
        "incorrect attribution": REFUTED,
        "miscaptioned": REFUTED,
        "originated as satire": REFUTED,
        "labeled satire": REFUTED,
        "scam": REFUTED,
    },
    "factcheck.afp.com": {
        "true": SUPPORTED,
        "false": REFUTED,
        "partly false": CE,
        "misleading": CE,
        "missing context": CE,
        "unsubstantiated": NEI,
        "satire": REFUTED,
        "ai-generated": REFUTED,
        "altered picture": REFUTED,
        "altered video": REFUTED,
    },
    "newschecker.in": {
        "false": REFUTED,
        "altered photo/video": REFUTED,
        "altered media": REFUTED,
        "misleading": CE,
        "missing context": CE,
        "partly false": CE,
        "satire": REFUTED,
        "true": SUPPORTED,
    },
    "verafiles.org": {
        "fake": REFUTED,
        "false": REFUTED,
        "misleading": CE,
        "needs context": CE,
        "satire": REFUTED,
    },
    "rumorscanner.com": {
        "false": REFUTED,
        "misleading": CE,
        "ai-generated": REFUTED,
        "altered": REFUTED,
    },
    "factcheck.org": {
        # Looser scheme — most labels indicate falsity or misleadingness.
        "false": REFUTED,
        "misleading": CE,
        "unsupported": NEI,
        "no evidence": NEI,
        "exaggerated": CE,
        "exaggerates": CE,
        "distorts the facts": CE,
        "not the whole story": CE,
        "disputed": NEI,
        "outdated": NEI,
        "true": SUPPORTED,
    },
}


def rule_map(publisher_site: str, rating: str | None) -> str | None:
    """Return the harmonised label via lookup, or None if no rule applies."""
    if not rating:
        return None
    key = rating.strip().lower().rstrip(".")
    return RULES.get(publisher_site, {}).get(key)


# --- LLM-based harmonisation (Full Fact + any fall-through) -------------

_VERDICT_SET = set(VERDICT_OPTIONS)
_VERDICT_LIST = " | ".join(f'"{v}"' for v in VERDICT_OPTIONS)

LLM_SYSTEM = (
    "You are classifying fact-check verdicts into a 4-class scheme used by an "
    "academic fact-checking evaluation pipeline.\n\n"
    f"The four classes are: {_VERDICT_LIST}.\n\n"
    "Definitions:\n"
    "- Supported: the claim is true / correct.\n"
    "- Refuted: the claim is false / fabricated / altered / wrong.\n"
    "- Not Enough Evidence: the claim cannot be verified either way.\n"
    "- Conflicting Evidence: the claim is literally true but misleading, "
    "exaggerated, missing context, partly true / partly false, or a mixture.\n\n"
    "You will be given a fact-checker's free-text verdict. Map it to exactly "
    "one of the four classes. Respond with JSON: "
    '{"label": "<one of the four exact strings>"}'
)


def llm_map(model: str, rating: str, timeout: int = 30) -> str:
    """LLM classification via Groq REST. Returns one of VERDICT_OPTIONS."""
    r = requests.post(
        f"{GROQ_BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {GROQ_API_KEY}"},
        json={
            "model": model,
            "messages": [
                {"role": "system", "content": LLM_SYSTEM},
                {"role": "user", "content": f"Fact-checker verdict:\n{rating}"},
            ],
            "temperature": 0,
            "response_format": {"type": "json_object"},
        },
        timeout=timeout,
    )
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"] or ""
    obj = json.loads(text)
    label = obj.get("label", "").strip()
    if label not in _VERDICT_SET:
        for v in VERDICT_OPTIONS:
            if v.lower() in label.lower():
                return v
        raise ValueError(f"LLM returned non-canonical label: {label!r} for rating {rating!r}")
    return label
