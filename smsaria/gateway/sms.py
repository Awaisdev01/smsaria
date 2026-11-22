"""GSM-7 aware SMS message splitting and compression.

A single SMS segment holds 160 characters in GSM-7 encoding (or 70 in
UCS-2 when any non-GSM-7 character is present — e.g. Urdu, Hindi,
Arabic). Longer replies cost money per segment and arrive out of order
on some networks, so replies are:

1. Compressed to remove avoidable bulk,
2. Split at sentence/word boundaries, never mid-word,
3. Kept segment-aware: each part is a readable unit.
"""

from __future__ import annotations


import re
import unicodedata

GSM7SegmentLimit = 160
UCS2SegmentLimit = 70
# GSM 7-bit default alphabet extension table (chars that cost 2)
GSM7_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)
GSM7_EXT = "^{}\\[~]|€"


def is_gsm7(text: str) -> bool:
    for ch in text:
        if ch not in GSM7_BASIC and ch not in GSM7_EXT:
            return False
    return True


def segment_limit(text: str) -> int:
    """Characters available per segment for this text's encoding."""
    if is_gsm7(text):
        return GSM7SegmentLimit
    return UCS2SegmentLimit


def compress(text: str, keep_newlines: bool = True) -> str:
    """Lossless-ish compression that keeps text readable on a 2G screen."""
    out = re.sub(r"[ \t]+", " ", text)
    out = re.sub(r" ?\n ?", "\n" if keep_newlines else " ", out)
    # collapse runs of blank lines
    out = re.sub(r"\n{3,}", "\n\n", out)
    # replace common verbose tokens (unchanged meaning, shorter)
    replacements = {
        " for example: ": " e.g. ",
        " for example ": " e.g. ",
        " that is: ": " i.e. ",
        " that is ": " i.e. ",
        " because of ": " due to ",
        " in order to ": " to ",
        " approximately ": " ~",
    }
    for long_, short in replacements.items():
        out = out.replace(long_, short)
    # NFKC folds fullwidth chars and some unicodedata bulk
    out = unicodedata.normalize("NFKC", out)
    return out.strip()


def split_sms(text: str, hard_limit=None) -> list[str]:
    """Split text into SMS segments at sentence/word boundaries.

    Returns a list of parts, each within the per-encoding segment limit
    (or ``hard_limit`` when given). Multi-part strings get "1/3 " prefixes
    only when there is more than one part and the limit allows room for it.
    """
    if not text:
        return []
    limit = hard_limit or segment_limit(text)
    # Leave room for the "n/m " prefix when we know we'll need it
    if len(text) > limit:
        limit -= len(f"9/9 ")

    parts: list[str] = []
    remaining = text
    while remaining:
        if len(remaining) <= limit:
            parts.append(remaining)
            break
        cut = remaining.rfind(". ", 0, limit + 1)
        if cut != -1:
            cut += 1  # keep the period
        else:
            cut = remaining.rfind("\n", 0, limit + 1)
        if cut == -1:
            cut = remaining.rfind(" ", 0, limit + 1)
        if cut == -1:
            cut = limit  # brutal cut for a single overlong word
        parts.append(remaining[:cut].rstrip())
        remaining = remaining[cut:].lstrip()

    if len(parts) > 1:
        n = len(parts)
        return [f"{i + 1}/{n} {p}" for i, p in enumerate(parts)]
    return parts
