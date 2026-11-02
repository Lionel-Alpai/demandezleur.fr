"""Page 1/4 du QG : GET /api/qg/bilan?j=<jeton> -> vue_qg du candidat du jeton, rien d'autre.
Logique pure (testable sans FastAPI) + monter(app, extraire_ip) appelé par api.py."""
import hashlib, json, time
from pathlib import Path

BASE = Path(__file__).resolve().parent
BILAN = BASE / "corpus" / "bilan.json"
JETONS = BASE / "qg" / "jetons.json"
CADENCE_S = 2.0
MASQUE = "[autre candidat]"


def empreinte(jeton):
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def resoudre(jeton, registre):
    """slug du jeton, ou None (inconnu ET révoqué : même issue)."""
    if not isinstance(jeton, str) or not jeton or len(jeton) > 200:
        return None
    e = registre.get(empreinte(jeton))
    if not e or e.get("revoque"):
        return None
    return e.get("slug")


def _masquer(x, noms):
    if isinstance(x, str):
        for n in noms:
            x = x.replace(n, MASQUE)
        return x
    if isinstance(x, list):
        return [_masquer(v, noms) for v in x]
    if isinstance(x, dict):
        return {k: _masquer(v, noms) for k, v in x.items()}
    return x


def vue(bilan, slug):
    cands = bilan.get("candidats", [])
    mien = next((e for e in cands if e.get("id") == slug), None)
    if mien is None:
        return None
    noms = sorted((e["nom"] for e in cands if e.get("id") != slug and e.get("nom")), key=len, reverse=True)
    sortie = {
        "slug": slug, "nom": mien.get("nom"), "parti": mien.get("parti"),
        "genere_le": bilan.get("_meta", {}).get("genere_le"),
        "vue_qg": mien.get("vue_qg"), "documents": mien.get("documents"),
        "trous": (mien.get("vue_qg") or {}).get("themes_manquants"),
    }
    return _masquer(sortie, noms)


def _lire(chemin):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except Exception:
        return {}


def monter(app, extraire_ip):
    from fastapi import HTTPException, Request
    dernier = {}

    @app.get("/api/qg/bilan")
    async def qg_bilan(request: Request, j: str = ""):
        ip = extraire_ip(request)
        maintenant = time.monotonic()
        if len(dernier) > 10000:
            dernier.clear()
        if maintenant - dernier.get(ip, 0) < CADENCE_S:
            raise HTTPException(status_code=429, detail={"error": "cadence"})
        dernier[ip] = maintenant
        slug = resoudre(j, _lire(JETONS))
        v = vue(_lire(BILAN), slug) if slug else None
        if v is None:
            raise HTTPException(status_code=404, detail="introuvable")
        return v
