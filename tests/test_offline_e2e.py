import sys, os, json, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

os.environ.update({
    "SMSARIA_PROVIDER_BASE": "http://127.0.0.1:9999", "SMSARIA_PROVIDER_KEY": "t",
    "SMSARIA_MODEL": "t", "SMSARIA_ADAPTERS": "raw",
    "SMSARIA_CACHE_DB": tempfile.mktemp(suffix=".db"),
})

from smsaria.server import Gateway
from smsaria.providers.openai_compat import ProviderError


def test_offline_fallback_end_to_end():
    gw = Gateway()
    def flaky(sender, text, history=None):
        if gw.cache.size() == 0:
            return "Malaria is spread by mosquitoes, prevented with bed nets.", 15
        raise ProviderError("provider down")
    gw.provider.chat = flaky
    r1 = gw.handle_sms("raw", json.dumps({"sender": "+1", "text": "what is malaria"}).encode())
    r2 = gw.handle_sms("raw", json.dumps({"sender": "+2", "text": "what is malaria"}).encode())
    a1 = json.loads(r1["body"])["reply"]
    a2 = json.loads(r2["body"])["reply"]
    assert "mosquitoes" in a1 and not a1.startswith("(offline")
    assert a2.startswith("(offline answer)") and "mosquitoes" in a2
    # Budget-exhausted path also serves the cache:
    gw.budget._global = gw.budget.global_daily
    gw.provider.chat = flaky
    r3 = gw.handle_sms("raw", json.dumps({"sender": "+3", "text": "what is malaria"}).encode())
    a3 = json.loads(r3["body"])["reply"]
    assert a3.startswith("(offline answer)")

def test_no_cache_error_message():
    gw = Gateway()
    def dead(sender, text, history=None):
        raise ProviderError("down")
    gw.provider.chat = dead
    r = gw.handle_sms("raw", json.dumps({"sender": "+1", "text": "how to bake bread"}).encode())
    a = json.loads(r["body"])["reply"]
    assert "try again" in a.lower()
