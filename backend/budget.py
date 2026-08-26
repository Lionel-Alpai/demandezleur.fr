# budget.py — disjoncteur de coût : compteur journalier en euros, paliers de dégradation.
"""
Tarif DeepSeek flash (api-docs, lu le 22/08/2026), $ par million de tokens : cache hit 0,007 · miss 0,22 · sortie 0,66 — ×2 en pointe.
Plafond : DL_BUDGET_JOUR_EUR (défaut 3,00). Paliers :
  < 80 %   normal
  ≥ 80 %   DÉGRADÉ  : l'Arène tourne sans juge (−40 %), dossier conservé
  ≥ 100 %  FERMÉ    : plus de débat jusqu'à demain ; le chat reste (bon marché) jusqu'à 200 %
Fichier : backend/budget/AAAA-MM-JJ.json (gitignoré).
"""
import json
import os
import threading
from datetime import datetime, timezone
from pathlib import Path

DOSSIER = Path(__file__).resolve().parent / "budget"
PRIX_USD_PAR_M = {"hit": 0.007, "miss": 0.22, "out": 0.66}
USD_EUR = float(os.environ.get("DL_USD_EUR", "0.92"))
_verrou = threading.Lock()


def plafond_eur() -> float:
    try:
        return float(os.environ.get("DL_BUDGET_JOUR_EUR", "3.0"))
    except ValueError:
        return 3.0


def _chemin(jour=None) -> Path:
    DOSSIER.mkdir(exist_ok=True)
    return DOSSIER / f"{(jour or datetime.now(timezone.utc).date()).isoformat()}.json"


def lire(jour=None) -> dict:
    p = _chemin(jour)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"jour": p.stem, "eur": 0.0, "hit": 0, "miss": 0, "out": 0, "appels": 0, "par_usage": {}}


def enregistrer(hit: int, miss: int, out: int, usage: str = "", pointe: bool = False) -> dict:
    """Ajoute un appel au compteur du jour ; retourne l'état."""
    coef = 2.0 if pointe else 1.0
    eur = coef * USD_EUR * (hit * PRIX_USD_PAR_M["hit"] + miss * PRIX_USD_PAR_M["miss"] + out * PRIX_USD_PAR_M["out"]) / 1_000_000
    with _verrou:
        d = lire()
        d["eur"] = round(d["eur"] + eur, 6); d["hit"] += hit; d["miss"] += miss; d["out"] += out; d["appels"] += 1
        u = d["par_usage"].setdefault(usage or "autre", {"eur": 0.0, "appels": 0})
        u["eur"] = round(u["eur"] + eur, 6); u["appels"] += 1
        d["maj"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        _chemin().write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    return d


def etat() -> dict:
    d = lire(); p = plafond_eur(); ratio = d["eur"] / p if p > 0 else 0.0
    palier = "normal" if ratio < 0.8 else ("degrade" if ratio < 1.0 else ("ferme" if ratio < 2.0 else "ferme_total"))
    return {"jour": d["jour"], "eur": round(d["eur"], 4), "plafond_eur": p, "ratio": round(ratio, 3), "palier": palier,
            "hit": d["hit"], "miss": d["miss"], "out": d["out"], "appels": d["appels"], "par_usage": d.get("par_usage", {})}


def debats_ouverts() -> bool:
    return etat()["palier"] == "normal" or etat()["palier"] == "degrade"


def juge_actif() -> bool:
    return etat()["palier"] == "normal"


def chat_ouvert() -> bool:
    return etat()["palier"] != "ferme_total"
