"""USSD menu engine — interactive AI menus on feature phones.

USSD sessions on Africa's Talking (and compatible gateways) are
callback-driven: the gateway calls your endpoint with a session id +
user input, you return a string that is shown as one screen.

Menus are declared as YAML-like dicts (kept as plain dicts to honor the
zero-dependency rule; load from JSON or YAML-with-pyyaml if installed):

    menus = {
        "root": {
            "title": "Ask anything",
            "options": {
                "1": ("Ask a question", "ask"),
                "2": ("Weather", "weather"),
                "3": ("Health tips", "info:health"),
            },
        },
    }

Screen flow:
  - "root" shows the title + numbered options.
  - option values: "ask" -> hand off to free-text AI question flow,
    "info:<key>" -> show a static card,
    a screen name -> navigate there.
  - the "ask" flow takes raw user input until "#" or "00" ends the session.
"""

from __future__ import annotations


from typing import Any, Callable


class USSDEngine:
    def __init__(self, menus: dict[str, dict[str, Any]]):
        self.menus = menus

    def screen(self, name: str) -> str:
        menu = self.menus.get(name)
        if not menu:
            return f"END Menu unavailable: {name}"
        lines = [menu["title"]]
        for key in sorted(menu.get("options", {})):
            label = menu["options"][key][0]
            lines.append(f"{key}. {label}")
        return "CON " + "\n".join(lines)

    def handle(
        self,
        state: dict[str, Any],
        user_input: str,
        ask_fn: Callable[[str, str], str],
        cards: dict[str, str] | None = None,
    ) -> str:
        """Advance the session one screen.

        state (mutated): {"screen": str, "flow": None|"ask", "buffer": str}
        user_input: what the subscriber dialed this round ("" = session start)
        ask_fn: (sender, question) -> answer, supplied by the gateway.
        Returns the full response string ("CON ..." or "END ...").
        """
        cards = cards or {}
        screen = state.get("screen", "root")
        inp = (user_input or "").strip()

        # Free-text question flow
        if state.get("flow") == "ask":
            if inp in ("00", "#"):
                state["flow"] = None
                state["screen"] = "root"
                return self.screen("root")
            question = state.get("buffer", "") + (" " if state.get("buffer") else "") + inp
            if len(question) > 400:
                return "END Question too long. Please start a new session."
            state["buffer"] = ""
            state["flow"] = None
            answer = ask_fn(state.get("sender", "unknown"), question)
            # Offer continuation
            state["screen"] = "root"
            return "END " + answer[:320] + "\n(Reply 1 to ask again)"
            # continuation is handled by the gateway on next callback

        # Session start or navigation
        menu = self.menus.get(screen, {})
        options = menu.get("options", {})

        if not inp:
            return self.screen(screen)

        choice = options.get(inp)
        if choice is None:
            return "CON Invalid option.\n" + self.screen(screen)[4:]

        target = choice[1]
        if target == "ask":
            state["flow"] = "ask"
            state["buffer"] = ""
            return "CON Type your question (00 to cancel):"

        if target.startswith("info:"):
            key = target.split(":", 1)[1]
            card = cards.get(key)
            if card is None:
                return f"END No info available for {key}."
            state["screen"] = "root"
            return "END " + card[:320]

        # Navigate to another menu screen
        state["screen"] = target
        return self.screen(target)
