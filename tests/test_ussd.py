import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from smsaria.ussd.engine import USSDEngine


MENUS = {
    "root": {
        "title": "Welcome",
        "options": {
            "1": ("Ask", "ask"),
            "2": ("Info", "info:tip"),
            "3": ("More", "more"),
        },
    },
    "more": {"title": "More", "options": {"1": ("Back", "root")}},
}


def test_start_screen():
    e = USSDEngine(MENUS)
    state = {"screen": "root", "flow": None, "buffer": "", "sender": "+1"}
    out = e.handle(state, "", ask_fn=lambda s, q: "ans")
    assert out.startswith("CON Welcome")
    assert "1. Ask" in out


def test_navigate():
    e = USSDEngine(MENUS)
    state = {"screen": "root", "flow": None, "buffer": "", "sender": "+1"}
    out = e.handle(state, "3", ask_fn=lambda s, q: "ans")
    assert "More" in out
    assert state["screen"] == "more"


def test_invalid_option():
    e = USSDEngine(MENUS)
    state = {"screen": "root", "flow": None, "buffer": "", "sender": "+1"}
    out = e.handle(state, "9", ask_fn=lambda s, q: "ans")
    assert "Invalid" in out


def test_ask_flow_calls_ai():
    e = USSDEngine(MENUS)
    state = {"screen": "root", "flow": None, "buffer": "", "sender": "+1"}
    e.handle(state, "1", ask_fn=lambda s, q: "ans")  # enter ask flow
    assert state["flow"] == "ask"
    out = e.handle(state, "what is malaria", ask_fn=lambda s, q: f"AI:{q}")
    assert "AI:what is malaria" in out
    assert state["flow"] is None


def test_ask_cancel():
    e = USSDEngine(MENUS)
    state = {"screen": "root", "flow": None, "buffer": "", "sender": "+1"}
    e.handle(state, "1", ask_fn=lambda s, q: "ans")
    out = e.handle(state, "00", ask_fn=lambda s, q: "ans")
    assert "Welcome" in out
    assert state["flow"] is None


def test_info_card():
    e = USSDEngine(MENUS)
    state = {"screen": "root", "flow": None, "buffer": "", "sender": "+1"}
    out = e.handle(state, "2", ask_fn=lambda s, q: "ans", cards={"tip": "Drink water."})
    assert "Drink water." in out
    assert out.startswith("END")
