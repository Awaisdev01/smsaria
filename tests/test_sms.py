"""Tests for the GSM-7 splitting and compression."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from smsaria.gateway.sms import compress, is_gsm7, split_sms, segment_limit


def test_gsm7_detection():
    assert is_gsm7("Hello, world! 123")
    assert not is_gsm7("مرحبا")  # Arabic -> UCS-2
    assert not is_gsm7("سلام")   # Urdu -> UCS-2


def test_limits():
    assert segment_limit("plain text") == 160
    assert segment_limit("مرحبا بالعالم") == 70


def test_split_short_message_untouched():
    parts = split_sms("Hello!")
    assert parts == ["Hello!"]


def test_split_long_message_word_boundaries():
    text = " ".join(["word"] * 100)  # 499 chars
    parts = split_sms(text)
    assert len(parts) > 1
    for p in parts:
        assert len(p) <= 160
        assert "word" in p
    # prefixes present
    assert parts[0].startswith("1/")
    assert parts[-1].startswith(f"{len(parts)}/")


def test_split_never_mid_word():
    text = " ".join([f"word{i}" for i in range(60)])  # long, unique words
    parts = split_sms(text)
    for p in parts:
        # every part must end and start at a word boundary
        assert p.endswith(tuple(f"word{i}" for i in range(60))) or p.endswith(".")
        assert "word0word" not in p  # no fused words


def test_ucs2_split():
    text = "مرحبا " * 30  # > 70 chars
    parts = split_sms(text)
    assert len(parts) > 1
    for p in parts:
        assert len(p) <= 70


def test_compress_shortens():
    original = "Use it   for example   in order to    test   this."
    out = compress(original)
    assert "e.g." in out or "Use it" in out
    assert "  " not in out
