# debats_store.py — débats terminés, sauvegardés pour un lien permanent (/d/?id=…).
import json
import re
import secrets
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DOSSIER = BASE_DIR / "debats"
TAILLE_MAX = 200_000
ID_RE = re.compile(r"^[A-Za-z0-9_-]{6,12}$")


def _candidats_connus() -> set:
    try:
        return {c["id"] for c in json.loads((BASE_DIR / "candidats.json").read_text(encoding="utf-8"))}
    except Exception:
        return set()


def valider(doc: dict, max_tours: int = 5) -> str:
    """Retourne '' si le document est acceptable, sinon le motif de refus."""
    if not isinstance(doc, dict):
        return "document invalide"
    cands = doc.get("candidats")
    if not isinstance(cands, list) or not (2 <= len(cands) <= 5):
        return "2 à 5 candidats requis"
    connus = _candidats_connus()
    if connus and any(c not in connus for c in cands):
        return "candidat inconnu"
    sujet = str(doc.get("sujet", "")).strip()
    if not sujet or len(sujet) > 500:
        return "sujet manquant ou trop long"
    if doc.get("mode") not in ("standard", "arene"):
        return "mode invalide"
    tours = doc.get("tours")
    if not isinstance(tours, list) or not (1 <= len(tours) <= max_tours):
        return f"1 à {max_tours} tours requis"
    for t in tours:
        if not isinstance(t, dict) or not isinstance(t.get("interventions"), list):
            return "tour invalide"
        for i in t["interventions"]:
            if not isinstance(i, dict) or i.get("candidat_id") not in cands:
                return "intervention invalide"
            if len(str(i.get("texte", ""))) > 2000:
                return "intervention trop longue"
            if len(i.get("preuves") or []) > 12:
                return "trop de preuves"
    if len(json.dumps(doc, ensure_ascii=False)) > TAILLE_MAX:
        return "document trop volumineux"
    return ""


def sauver(doc: dict, moteur: str = "") -> str:
    """Enregistre et retourne l'identifiant public."""
    DOSSIER.mkdir(exist_ok=True)
    for _ in range(5):
        did = secrets.token_urlsafe(6).replace("-", "a").replace("_", "b")
        if not (DOSSIER / f"{did}.json").exists():
            break
    propre = {
        "version": 1, "id": did, "cree_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sujet": str(doc["sujet"]).strip(), "mode": doc["mode"], "candidats": list(doc["candidats"]),
        "tours": [{
            "tour": int(t.get("tour", n + 1)), "type": str(t.get("type", "")),
            "question_moderateur": (str(t["question_moderateur"])[:300] if t.get("question_moderateur") else None),
            "candidat_interpelle_id": t.get("candidat_interpelle_id"),
            "interventions": [{
                "candidat_id": i["candidat_id"], "texte": str(i.get("texte", "")),
                "preuves": [{k: v for k, v in p.items() if k in ("type", "candidat_id", "titre", "page", "theme", "extrait", "url", "orateur", "date_lisible")}
                            for p in (i.get("preuves") or [])[:12] if isinstance(p, dict)],
                "revisions": [{k: str(v)[:300] for k, v in r.items() if k in ("type", "phrase", "cible", "raison")} for r in (i.get("revisions") or [])[:10] if isinstance(r, dict)],
            } for i in t["interventions"]],
        } for n, t in enumerate(doc["tours"])],
        "moteur": moteur, "site_version": "refonte-plateau",
    }
    (DOSSIER / f"{did}.json").write_text(json.dumps(propre, ensure_ascii=False, indent=1), encoding="utf-8")
    return did


def lire(did: str):
    if not ID_RE.match(did or ""):
        return None
    p = DOSSIER / f"{did}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None
