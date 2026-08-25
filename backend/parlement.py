"""
Module stdlib pur — données de l'actualité parlementaire pour demandezleur.fr.
Ne lève jamais d'exception : échec silencieux via logging.warning.
"""
import json
import os
import re
import hmac
import unicodedata
import logging
import threading
from pathlib import Path
from datetime import date

logger = logging.getLogger(__name__)

BASE = Path(__file__).resolve().parent
DOSSIER = BASE / "parlement"
FICHIER = DOSSIER / "parlement.json"
PRECEDENT = DOSSIER / "parlement.precedent.json"
OFF = DOSSIER / "OFF"

# Cache mémoire pour _charger()
_cache_lock = threading.Lock()
_cache = {}  # clé = (st_mtime_ns, st_size), valeur = dict


def actif():
    """False si le coupe-circuit OFF existe ou si le fichier de données est absent."""
    if OFF.exists():
        return False
    if not FICHIER.exists():
        return False
    return True


def _charger():
    """Lit FICHIER avec un cache mémoire invalidé par (st_mtime_ns, st_size)."""
    global _cache
    try:
        stat = FICHIER.stat()
        cle = (stat.st_mtime_ns, stat.st_size)
    except OSError:
        return {}

    with _cache_lock:
        if cle in _cache:
            return _cache[cle]

    try:
        with open(FICHIER, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        logger.warning("parlement: JSON invalide dans %s", FICHIER, exc_info=True)
        return {}

    if not isinstance(data, dict):
        logger.warning("parlement: %s n'est pas un dict", FICHIER)
        return {}

    with _cache_lock:
        _cache = {cle: data}
    return data


def blocs_actu(candidat_id, maximum=8):
    """Rend les blocs d'actualité d'un candidat, limités à `maximum`."""
    if not actif():
        return []
    data = _charger()
    actu = data.get("actu", {})
    if not isinstance(actu, dict) or candidat_id not in actu:
        return []
    blocs = actu[candidat_id]
    if not isinstance(blocs, list):
        return []
    resultats = []
    for b in blocs[:maximum]:
        if not isinstance(b, dict):
            continue
        texte = b.get("text", "")
        source = b.get("source", "")
        if not texte or not source:
            continue
        item = {
            "text": texte,
            "source": source,
            "page": b.get("page", ""),
            "theme": b.get("theme", ""),
            "id": b.get("id", 0),
        }
        for cle_extra in ("url", "cr_uid", "date"):
            if cle_extra in b:
                item[cle_extra] = b[cle_extra]
        resultats.append(item)
    return resultats


def _couper_texte(texte, limite=240):
    """Coupe un texte à `limite` caractères sur la dernière espace + '…'."""
    if len(texte) <= limite:
        return texte
    tronque = texte[:limite]
    derniere_espace = tronque.rfind(" ")
    if derniere_espace > 0:
        return tronque[:derniere_espace] + "…"
    return tronque + "…"


def sujets(n=8):
    """Rend les sujets avec 'jours_depuis' recalculé à la lecture."""
    if not actif():
        return {"maj": None, "derniere_seance": None, "derniere_seance_lisible": None,
                "jours_depuis": None, "sujets": []}
    data = _charger()
    fraicheur = data.get("fraicheur", {})
    derniere_seance_str = fraicheur.get("derniere_seance", "")
    derniere_seance_lisible = fraicheur.get("derniere_seance_lisible", "")
    jours_depuis = None
    try:
        if derniere_seance_str:
            jours_depuis = (date.today() - date.fromisoformat(derniere_seance_str)).days
    except Exception:
        logger.warning("parlement: date de séance invalide: %s", derniere_seance_str)
    sujets_data = data.get("sujets", [])
    if not isinstance(sujets_data, list):
        sujets_data = []
    resultats = []
    for s in sujets_data[:n]:
        if not isinstance(s, dict):
            continue
        extrait = ""
        orateur = ""
        sequences = s.get("sequences", [])
        if isinstance(sequences, list) and sequences:
            premiere = sequences[0]
            if isinstance(premiere, dict):
                extrait = _couper_texte(premiere.get("texte", ""))
                orateur = premiere.get("orateur", "")
        resultats.append({
            "titre": s.get("titre", ""),
            "libelle": s.get("libelle", ""),
            "section": s.get("section", ""),
            "date": s.get("date", ""),
            "date_lisible": s.get("date_lisible", ""),
            "url": s.get("url", ""),
            "n_prises": s.get("n_prises", 0),
            "extrait": extrait,
            "orateur": orateur,
        })
    return {
        "maj": data.get("genere_le"),
        "derniere_seance": derniere_seance_str,
        "derniere_seance_lisible": derniere_seance_lisible,
        "jours_depuis": jours_depuis,
        "sujets": resultats,
    }


def _normaliser(texte):
    """Normalise une chaîne : minuscules, sans accents, ponctuation → espaces."""
    texte = texte.lower()
    texte = unicodedata.normalize("NFKD", texte)
    texte = "".join(c for c in texte if not unicodedata.combining(c))
    texte = re.sub(r"[^a-z0-9\s]", " ", texte)
    return texte


def sequences_pour_sujet(sujet, n=1):
    """Choisit le sujet le plus proche de `sujet` et rend ses séquences."""
    if not actif():
        return []
    data = _charger()
    sujets_data = data.get("sujets", [])
    if not isinstance(sujets_data, list) or not sujets_data:
        return []
    req_normalise = _normaliser(sujet)
    req_mots = {m for m in req_normalise.split() if len(m) > 3}
    meilleur_score = -1
    meilleur_sujet = None
    for s in sujets_data:
        if not isinstance(s, dict):
            continue
        libelle = s.get("libelle", s.get("titre", ""))
        libelle_normalise = _normaliser(libelle)
        libelle_mots = {m for m in libelle_normalise.split() if len(m) > 3}
        score = len(req_mots & libelle_mots)
        if score > meilleur_score:
            meilleur_score = score
            meilleur_sujet = s
    if meilleur_score == 0:
        meilleur_sujet = sujets_data[-1]
    if meilleur_sujet is None:
        return []
    sequences = meilleur_sujet.get("sequences", [])
    if not isinstance(sequences, list):
        return []
    resultats = []
    for seq in sequences[:n]:
        if not isinstance(seq, dict):
            continue
        resultats.append({
            "orateur": seq.get("orateur", ""),
            "texte": seq.get("texte", ""),
            "date_lisible": meilleur_sujet.get("date_lisible", ""),
            "titre": meilleur_sujet.get("titre", ""),
            "url": meilleur_sujet.get("url", ""),
        })
    return resultats


def etat():
    """Rend un résumé de l'état du module."""
    if not actif():
        return {"actif": False, "schema": None, "maj": None, "derniere_seance": None,
                "jours_depuis": None, "n_sujets": 0, "n_sequences": 0, "candidats_actu": {}}
    data = _charger()
    fraicheur = data.get("fraicheur", {})
    derniere_seance_str = fraicheur.get("derniere_seance", "")
    jours_depuis = None
    try:
        if derniere_seance_str:
            jours_depuis = (date.today() - date.fromisoformat(derniere_seance_str)).days
    except Exception:
        pass
    sujets_data = data.get("sujets", [])
    n_sujets = len(sujets_data) if isinstance(sujets_data, list) else 0
    n_sequences = 0
    if isinstance(sujets_data, list):
        for s in sujets_data:
            if isinstance(s, dict):
                seqs = s.get("sequences", [])
                if isinstance(seqs, list):
                    n_sequences += len(seqs)
    actu = data.get("actu", {})
    candidats_actu = {}
    if isinstance(actu, dict):
        for cid, blocs in actu.items():
            if isinstance(blocs, list):
                candidats_actu[cid] = len(blocs)
    return {
        "actif": True,
        "schema": data.get("schema"),
        "maj": data.get("genere_le"),
        "derniere_seance": derniere_seance_str,
        "jours_depuis": jours_depuis,
        "n_sujets": n_sujets,
        "n_sequences": n_sequences,
        "candidats_actu": candidats_actu,
    }


def verifier_token(valeur):
    """Compare le token fourni avec PARLEMENT_INGEST_TOKEN par hmac.compare_digest."""
    attendu = os.environ.get("PARLEMENT_INGEST_TOKEN")
    if not attendu:
        return False
    if valeur is None:
        return False
    return hmac.compare_digest(attendu, valeur)


URL_RE = re.compile(
    r"^https://www\.assemblee-nationale\.fr/dyn/\d+/comptes-rendus/seance/[A-Za-z0-9]+$"
)


def valider_payload(obj):
    """Valide un payload entrant. Rend (True, "") ou (False, raison)."""
    if not isinstance(obj, dict):
        return False, "le payload doit etre un dict"
    if obj.get("schema") != "parlement/1":
        return False, "schema invalide, attendu parlement/1"

    sujets_list = obj.get("sujets")
    if not isinstance(sujets_list, list) or len(sujets_list) < 1 or len(sujets_list) > 200:
        return False, "sujets doit etre une liste de 1 a 200 elements"

    for i, s in enumerate(sujets_list):
        if not isinstance(s, dict):
            return False, f"sujets[{i}] n'est pas un dict"
        titre = s.get("titre", "")
        if not isinstance(titre, str) or len(titre) < 1 or len(titre) > 300:
            return False, f"sujets[{i}].titre invalide (1..300 car.)"
        date_s = s.get("date", "")
        if not isinstance(date_s, str) or not re.match(r"^\d{4}-\d{2}-\d{2}$", date_s):
            return False, f"sujets[{i}].date invalide (AAAA-MM-JJ)"
        url = s.get("url", "")
        if not isinstance(url, str) or not URL_RE.match(url):
            return False, f"sujets[{i}].url invalide"
        sequences = s.get("sequences", [])
        if not isinstance(sequences, list) or len(sequences) < 1 or len(sequences) > 10:
            return False, f"sujets[{i}].sequences doit etre une liste de 1 a 10 elements"
        for j, seq in enumerate(sequences):
            if not isinstance(seq, dict):
                return False, f"sujets[{i}].sequences[{j}] n'est pas un dict"
            orateur = seq.get("orateur", "")
            texte = seq.get("texte", "")
            if not isinstance(orateur, str):
                return False, f"sujets[{i}].sequences[{j}].orateur invalide"
            if not isinstance(texte, str) or len(texte) < 30 or len(texte) > 1200:
                return False, f"sujets[{i}].sequences[{j}].texte invalide (30..1200 car.)"

    actu = obj.get("actu", {})
    if not isinstance(actu, dict):
        return False, "actu doit etre un dict"
    if len(actu) > 40:
        return False, "actu: maximum 40 candidats"
    for cid, blocs in actu.items():
        if not isinstance(cid, str):
            return False, "actu: les cles doivent etre des chaines"
        if not isinstance(blocs, list) or len(blocs) > 40:
            return False, f"actu[{cid}]: liste de 0 a 40 blocs attendue"
        for k, b in enumerate(blocs):
            if not isinstance(b, dict):
                return False, f"actu[{cid}][{k}] n'est pas un dict"
            texte = b.get("text", "")
            if not isinstance(texte, str) or len(texte) < 30 or len(texte) > 1200:
                return False, f"actu[{cid}][{k}].text invalide (30..1200 car.)"
            source = b.get("source", "")
            if not isinstance(source, str) or not source:
                return False, f"actu[{cid}][{k}].source invalide"
            page = b.get("page", "")
            if not isinstance(page, str) or not page:
                return False, f"actu[{cid}][{k}].page invalide"
            theme = b.get("theme", "")
            if not isinstance(theme, str) or not theme:
                return False, f"actu[{cid}][{k}].theme invalide"
            bid = b.get("id")
            if not isinstance(bid, int) or bid < 0:
                return False, f"actu[{cid}][{k}].id doit etre un entier >= 0"
            url = b.get("url", "")
            if not isinstance(url, str) or not URL_RE.match(url):
                return False, f"actu[{cid}][{k}].url invalide"

    try:
        serialise = json.dumps(obj, ensure_ascii=False, sort_keys=True)
    except Exception:
        return False, "payload non serialisable en JSON"
    if len(serialise.encode("utf-8")) > 900000:
        return False, "payload trop volumineux (max 900 000 octets)"

    return True, ""


def ecrire(obj):
    """Écrit le payload validé dans FICHIER (rotation atomique). Rend etat()."""
    ok, _ = valider_payload(obj)
    if not ok:
        logger.warning("parlement: ecrire() refuse — payload invalide")
        return etat()
    DOSSIER.mkdir(parents=True, exist_ok=True)
    # Rotation : FICHIER -> PRECEDENT
    if FICHIER.exists():
        FICHIER.rename(PRECEDENT)
    # Écriture atomique
    tmp = DOSSIER / "parlement.json.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        tmp.replace(FICHIER)
    except Exception:
        logger.warning("parlement: échec écriture atomique", exc_info=True)
        if tmp.exists():
            try:
                tmp.unlink()
            except Exception:
                pass
    # Invalider le cache
    global _cache
    with _cache_lock:
        _cache = {}
    return etat()
