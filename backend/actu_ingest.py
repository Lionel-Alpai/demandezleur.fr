"""Ingestion du tiroir ACTU (grelée côté FastAPI).

Petit module autonome, sans dépendance vers api.py : lit/écrit le tiroir
`<backend>/actu/<jour>.json`, protège les entrées verrouillées (valide/refuse),
valide le payload et vérifie le jeton d'ingestion. Aucun secret en dur : le
jeton est lu dans l'environnement (`ACTU_INGEST_TOKEN`).
"""

import hmac
import json
import os
import re
from pathlib import Path

# __file__ vit DANS le répertoire backend (le patcher y copie ce module) :
# son parent EST le backend, et le tiroir ACTU est `backend/actu`.
BACKEND = Path(__file__).resolve().parent
BASE = BACKEND / "actu"
OFF = BASE / "OFF"

SCHEMA = "actu/1"
STATUTS = {"verifie_auto", "a_valider", "valide", "refuse"}
# Statuts verrouillés : une entrée déjà validée/refusée n'est jamais réécrite.
VERROUS = ("valide", "refuse")

_JOUR = re.compile(r"\d{4}-\d{2}-\d{2}")


def verifier_token(valeur):
    """True si `valeur` == ACTU_INGEST_TOKEN (comparaison temps constant).

    Refuse dès que la valeur OU la variable d'environnement manque : un jeton
    absent (mauvaise config, appel démaqué) ne peut jamais passer.
    """
    attendu = os.environ.get("ACTU_INGEST_TOKEN")
    if not valeur or not attendu:
        return False
    return hmac.compare_digest(valeur, attendu)


def valider_payload(obj):
    """Valide le payload d'ingestion -> (bool, raison).

    Un objet dict, un schema exact, un jour au format AAAA-MM-JJ, une liste
    d'entrées non vide, et chaque entrée un dict avec un 'id' non vide et un
    'statut' connu.
    """
    if not isinstance(obj, dict):
        return False, "payload attendu : un objet JSON"
    if obj.get("schema") != SCHEMA:
        return False, f"schema attendu : {SCHEMA}"
    jour = obj.get("jour")
    if not isinstance(jour, str) or not _JOUR.fullmatch(jour):
        return False, "jour invalide (format attendu : AAAA-MM-JJ)"
    entrees = obj.get("entrees")
    if not isinstance(entrees, list) or not entrees:
        return False, "entrees invalide (doit être une liste non vide)"
    for i, e in enumerate(entrees, 1):
        if not isinstance(e, dict):
            return False, f"entree {i} : doit être un objet"
        eid = e.get("id")
        st = e.get("statut")
        if not isinstance(eid, str) or not eid.strip():
            return False, f"entree {i} : 'id' requis et non vide"
        if st not in STATUTS:
            return False, f"entree {i} : statut inconnu '{st}'"
    return True, ""


def ecrire_merge(obj):
    """Fusionne les entrées dans `backend/actu/<jour>.json` (écriture idempotente).

    Garde (conserve) toute entrée déjà verrouillée (valide/refuse) présente sur
    le disque, par id ; ajoute ou remplace les autres. L'écriture se fait avec
    ensure_ascii=False et indent=1.

    Retour : {"jour", "entrees", "gardes_conserves"}.
    """
    jour = obj["jour"]
    if not _JOUR.fullmatch(jour):  # défense en profondeur (pas de traversée de chemin)
        raise ValueError("jour invalide pour l'ecriture")
    entrees = obj["entrees"]

    tiroir = BASE
    tiroir.mkdir(parents=True, exist_ok=True)
    chemin = tiroir / f"{jour}.json"

    existant = []
    if chemin.exists():
        try:
            with open(chemin, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("entrees"), list):
                existant = data["entrees"]
        except ValueError:
            # fichier corrompu : on repart d'un tiroir vide plutôt que de bloquer
            existant = []

    # Garde n°1 : on énumère les entrées déjà verrouillées (par id).
    gardes = {
        e["id"]: e
        for e in existant
        if isinstance(e, dict) and e.get("id") and e.get("statut") in VERROUS
    }

    # Base de fusion : les entrées disque existantes (dédupliquées par id).
    fusion = []
    ids_vus = set()
    for e in existant:
        if not isinstance(e, dict) or not e.get("id"):
            continue
        eid = e["id"]
        if eid not in ids_vus:
            fusion.append(e)
            ids_vus.add(eid)

    # Application des entrées entrantes : jamais au-dessus d'une garde.
    for e in entrees:
        if not isinstance(e, dict) or not e.get("id"):
            continue  # déjà filtré par valider_payload, mais on reste défensif
        eid = e["id"]
        if eid in gardes:
            continue  # entrée verrouillée conservée telle qu'elle est
        if eid in ids_vus:
            for i, fe in enumerate(fusion):
                if fe["id"] == eid:
                    fusion[i] = e
                    break
        else:
            fusion.append(e)
            ids_vus.add(eid)

    journal = {"schema": SCHEMA, "jour": jour, "entrees": fusion}
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(journal, f, ensure_ascii=False, indent=1)

    return {"jour": jour, "entrees": fusion, "gardes_conserves": len(gardes)}
