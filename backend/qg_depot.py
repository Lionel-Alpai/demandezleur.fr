"""Page 3/4 du QG : depots de suggestions de documents, CONSERVES, lies au jeton.
Logique pure (enregistrer, testable sans FastAPI) + deposer() async appele par /api/suggerer-document.
Jeton valide -> candidat = slug du jeton (le champ du formulaire est ignore), source=equipe-officielle.
Sans jeton -> depots/_public/, source=public. Fichier joint : PDF seul, 10 Mo max, nom assaini."""
import hashlib, json, os, re, time, unicodedata
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
MAX_PDF = 10 * 1024 * 1024
CADENCE_S = 5.0
_dernier = {}


class ErreurDepot(Exception):
    def __init__(self, status, message):
        Exception.__init__(self, message)
        self.status = status
        self.detail = {"error": "depot", "message_utilisateur": message}


def empreinte(jeton):
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def resoudre(jeton, registre):
    """slug du jeton, ou None (inconnu ET revoque : meme issue)."""
    if not isinstance(jeton, str) or not jeton or len(jeton) > 200:
        return None
    e = registre.get(empreinte(jeton))
    if not e or e.get("revoque"):
        return None
    return e.get("slug")


def assainir(nom):
    nom = str(nom).replace("\\", "/").split("/")[-1]
    nom = unicodedata.normalize("NFKD", nom).encode("ascii", "ignore").decode("ascii")
    stem = re.sub(r"\.pdf$", "", nom, flags=re.I)
    stem = re.sub(r"[^A-Za-z0-9_-]+", "-", stem).strip("-_")[:60] or "document"
    return stem + ".pdf"


def _ecrire(chemin, octets):
    tmp = chemin.with_name(chemin.name + ".tmp")
    tmp.write_bytes(octets)
    os.chmod(tmp, 0o640)
    os.replace(tmp, chemin)


def enregistrer(candidat, titre, url, notes, nom_fichier, octets, jeton, base=None, maintenant=None):
    base = Path(base) if base else BASE
    slug = None
    if jeton:
        try:
            registre = json.loads((base / "qg" / "jetons.json").read_text(encoding="utf-8"))
        except Exception:
            registre = {}
        slug = resoudre(jeton, registre)
        if not slug:
            raise ErreurDepot(404, "Lien non reconnu.")
    if nom_fichier:
        if octets is None or len(octets) > MAX_PDF:
            raise ErreurDepot(413, "Fichier trop volumineux (maximum 10 Mo).")
        if not octets.startswith(b"%PDF-") or not str(nom_fichier).lower().endswith(".pdf"):
            raise ErreurDepot(415, "Seuls les fichiers PDF sont acceptes.")
    source = "equipe-officielle" if slug else "public"
    dossier = base / "qg" / "depots" / (slug or "_public")
    dossier.mkdir(parents=True, exist_ok=True, mode=0o750)
    quand = maintenant or datetime.now()
    graine = json.dumps([candidat, titre, url, notes, slug], ensure_ascii=False).encode("utf-8") + (octets or b"")
    sha8 = hashlib.sha256(graine).hexdigest()[:8]
    base_nom = quand.strftime("%Y%m%d-%H%M%S") + "-" + sha8
    joint = None
    if nom_fichier:
        joint = base_nom + "-" + assainir(nom_fichier)
        _ecrire(dossier / joint, octets)
    meta = {
        "horodatage": quand.isoformat(timespec="seconds"), "source": source,
        "candidat": slug or str(candidat).strip()[:100],
        "candidat_formulaire": str(candidat).strip()[:100],
        "titre": str(titre).strip()[:200], "url": str(url).strip()[:500], "notes": str(notes).strip()[:1000],
        "fichier": joint, "fichier_sha256": hashlib.sha256(octets).hexdigest() if joint else None,
    }
    chemin = dossier / (base_nom + ".json")
    _ecrire(chemin, json.dumps(meta, indent=1, ensure_ascii=False).encode("utf-8"))
    return {"chemin": str(chemin), "source": source, "candidat": meta["candidat"], "fichier": joint}


async def deposer(candidat, titre, url, notes, fichier, jeton, ip):
    from fastapi import HTTPException
    maintenant = time.monotonic()
    if len(_dernier) > 10000:
        _dernier.clear()
    if maintenant - _dernier.get(ip, 0) < CADENCE_S:
        raise HTTPException(status_code=429, detail={"error": "cadence", "message_utilisateur": "Merci de patienter quelques secondes avant un nouvel envoi."})
    _dernier[ip] = maintenant
    nom = octets = None
    if fichier is not None and fichier.filename:
        nom = fichier.filename
        octets = await fichier.read(MAX_PDF + 1)
    try:
        return enregistrer(candidat, titre, url, notes, nom, octets, jeton)
    except ErreurDepot as e:
        raise HTTPException(status_code=e.status, detail=e.detail)
