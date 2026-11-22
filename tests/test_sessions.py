import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from smsaria.gateway.sessions import SessionStore


def test_session_ttl_expiry():
    store = SessionStore(ttl_seconds=1)
    sess = store.start("+254700000001")
    time.sleep(1.1)
    assert store.get("+254700000001") is None


def test_history_bounded():
    store = SessionStore(max_turns=2)
    sess = store.start("+254700000002")
    for i in range(10):
        store.append_history("+254700000002", sess, "user", f"m{i}")
    assert len(sess["history"]) <= 4


def test_active_count():
    store = SessionStore()
    store.start("+1")
    store.start("+2")
    assert store.active_count() == 2
