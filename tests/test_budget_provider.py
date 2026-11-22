import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from smsaria.providers.openai_compat import Budget


def test_per_sender_cap():
    b = Budget(per_sender_daily=2, global_daily=100)
    ok, _ = b.allow("+1")
    assert ok
    b.record("+1", 2)
    ok, msg = b.allow("+1")
    assert not ok
    assert "limit" in msg.lower()
    # other sender unaffected
    ok, _ = b.allow("+2")
    assert ok


def test_global_cap():
    b = Budget(per_sender_daily=100, global_daily=3)
    b.record("+1", 3)
    ok, msg = b.allow("+2")
    assert not ok
    assert "capacity" in msg.lower()


def test_daily_roll():
    b = Budget(per_sender_daily=1, global_daily=100)
    b.record("+1", 1)
    ok, _ = b.allow("+1")
    assert not ok
    # simulate a day change
    b._day = "2000-01-01"
    ok, _ = b.allow("+1")
    assert ok
