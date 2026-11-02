# [silence-electoral] Silence électoral (code électoral L49) : gel de la génération NOUVELLE.
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

PARIS = ZoneInfo("Europe/Paris")
CONFIG = Path(__file__).with_name("silence_electoral.json")
GELEES = {
    ("POST", "/api/debat/stream"),
    ("POST", "/api/ask"),
    ("POST", "/api/actu/ingest"),
}


def _maintenant():
    sim = os.environ.get("DL_DATE_SIMULEE")
    if sim:
        d = datetime.fromisoformat(sim)
        return d if d.tzinfo else d.replace(tzinfo=PARIS)
    return datetime.now(PARIS)


def fenetre_active():
    """Renvoie la fin ISO de la fenêtre de gel en cours, sinon None."""
    now = _maintenant()
    tours = json.loads(CONFIG.read_text(encoding="utf-8"))["tours"]
    for t in tours:
        if datetime.fromisoformat(t["debut"]) <= now < datetime.fromisoformat(t["fin"]):
            return t["fin"]
    return None


async def _repondre(send, statut, corps):
    octets = json.dumps(corps, ensure_ascii=False).encode("utf-8")
    await send({"type": "http.response.start", "status": statut,
                "headers": [(b"content-type", b"application/json; charset=utf-8"),
                            (b"cache-control", b"no-store")]})
    await send({"type": "http.response.body", "body": octets})


class SilenceElectoralMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        chemin = scope["path"].rstrip("/")
        if scope["method"] == "GET" and chemin == "/api/silence-electoral":
            jusqu = fenetre_active()
            return await _repondre(send, 200, {"silence_electoral": jusqu is not None, "jusqu_a": jusqu})
        if (scope["method"], chemin) in GELEES:
            jusqu = fenetre_active()
            if jusqu is not None:
                return await _repondre(send, 451, {"silence_electoral": True, "jusqu_a": jusqu})
        return await self.app(scope, receive, send)
