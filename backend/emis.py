"""emis.py — registre des textes ÉMIS par le plateau (répliques, phrases retirées ou annotées, pièces).

Un débat partagé (/api/debat/sauver) n'est accepté que si CHAQUE texte qu'il contient a été produit
par ce serveur : un lien /d/?id=… ne peut plus porter des propos fabriqués côté client et mis dans la
bouche d'un candidat réel. Le sujet et la question du modérateur restent des textes du visiteur
(ils sont présentés comme tels sur la page).

Empreinte = sha256 du texte à espaces repliés. Persistance : debats/emis/AAAAMMJJ.txt (une empreinte
par ligne), JOURS_RETENUS jours rechargés au démarrage, les fichiers plus vieux sont retirés.
Bibliothèque standard seule ; testable sans FastAPI.
"""
import hashlib
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DOSSIER = BASE_DIR / "debats" / "emis"
JOURS_RETENUS = 7
# Texte posé par api.py quand un candidat n'a pas pu répondre : émis par le serveur, donc connu d'office.
PLACEHOLDER_ERREUR = "(Erreur technique, ce candidat n'a pas pu répondre.)"
CHAMPS_REVISION = ("phrase", "raison")

_connus = set()
_verrou = threading.Lock()
_charge = False


def _normaliser(texte) -> str:
    return re.sub(r"\s+", " ", str(texte or "")).strip()


def empreinte(texte) -> str:
    return hashlib.sha256(_normaliser(texte).encode("utf-8")).hexdigest()


def _jour() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d")


def _charger():
    """Recharge les empreintes des JOURS_RETENUS derniers jours (une fois), purge le reste."""
    global _charge
    if _charge:
        return
    _charge = True
    DOSSIER.mkdir(parents=True, exist_ok=True)
    limite = (datetime.now(timezone.utc) - timedelta(days=JOURS_RETENUS)).strftime("%Y%m%d")
    for f in sorted(DOSSIER.glob("*.txt")):
        if f.stem < limite:
            try:
                f.unlink()
            except OSError:
                pass
            continue
        try:
            for ligne in f.read_text(encoding="utf-8").splitlines():
                ligne = ligne.strip()
                if len(ligne) == 64:
                    _connus.add(ligne)
        except OSError:
            pass
    _connus.add(empreinte(PLACEHOLDER_ERREUR))


def enregistrer(texte):
    """Déclare un texte émis par le plateau (idempotent, vide ignoré)."""
    t = _normaliser(texte)
    if not t:
        return
    e = empreinte(t)
    with _verrou:
        _charger()
        if e in _connus:
            return
        _connus.add(e)
        try:
            with open(DOSSIER / f"{_jour()}.txt", "a", encoding="utf-8") as f:
                f.write(e + "\n")
        except OSError:
            pass


def enregistrer_intervention(texte, revisions=None, annotations=None, preuves=None):
    """Tout ce qu'une réplique rend visible sur /d/ : texte, phrases retirées/annotées et leurs raisons, pièces."""
    enregistrer(texte)
    for r in list(revisions or []) + list(annotations or []):
        if isinstance(r, dict):
            for champ in CHAMPS_REVISION:
                enregistrer(r.get(champ))
    for p in preuves or []:
        if isinstance(p, dict):
            for v in p.values():
                if isinstance(v, str):
                    enregistrer(v)


def connu(texte) -> bool:
    t = _normaliser(texte)
    if not t:
        return True
    with _verrou:
        _charger()
        return empreinte(t) in _connus


def verifier_document(doc) -> str:
    """'' si tous les textes du document partagé ont été émis par le plateau, sinon le motif du refus."""
    for n, t in enumerate((doc or {}).get("tours") or [], 1):
        for i in (t or {}).get("interventions") or []:
            if not isinstance(i, dict):
                return f"tour {n} : intervention invalide"
            if not connu(i.get("texte", "")):
                return f"tour {n} : réplique non émise par le plateau"
            for champ in ("revisions", "annotations"):
                for r in i.get(champ) or []:
                    if isinstance(r, dict) and any(not connu(r.get(c)) for c in CHAMPS_REVISION):
                        return f"tour {n} : {champ[:-1]} non émise par le plateau"
            for p in i.get("preuves") or []:
                if isinstance(p, dict) and any(isinstance(v, str) and not connu(v) for v in p.values()):
                    return f"tour {n} : pièce non émise par le plateau"
    return ""
