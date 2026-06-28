from __future__ import annotations

import re


POSITIVE_WORDS = {
    "amazing",
    "beautiful",
    "best",
    "brilliant",
    "enjoyed",
    "excellent",
    "favorite",
    "fun",
    "good",
    "great",
    "incredible",
    "love",
    "loved",
    "masterpiece",
    "perfect",
    "powerful",
    "recommend",
    "strong",
    "wonderful",
}

NEGATIVE_WORDS = {
    "awful",
    "bad",
    "boring",
    "disappointing",
    "dull",
    "hate",
    "hated",
    "mess",
    "poor",
    "terrible",
    "waste",
    "weak",
    "worst",
}

TOKEN_RE = re.compile(r"[a-z]+")


def label_sentiment(text: str) -> str:
    tokens = TOKEN_RE.findall(text.lower())
    positive = sum(1 for token in tokens if token in POSITIVE_WORDS)
    negative = sum(1 for token in tokens if token in NEGATIVE_WORDS)
    return "Positive" if positive >= negative else "Negative"
