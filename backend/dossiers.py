# dossiers.py — le DOSSIER de l'Arène : deux tiroirs, servis UNIQUEMENT en mode arène.
"""
FAITS     dossiers/faits/<candidat_id>.json
          {"candidat_id", "maj", "entrees": [{"id", "classe", "fait", "date", "instance", "statut",
           "sources": [{"url", "media", "titre", "date"}], "verifie_le", "notes"}]}
          classe  : condamnation_definitive | condamnation_appel | mise_en_examen | vote | declaration | sanction
          statut  : verifie_auto | a_valider | valide | refuse | perime
          Seuls verifie_auto et valide sont servis à l'Arène.

RAPPORTS  dossiers/rapports/<famille_A>__<famille_B>.json (flèche A → B), surcharge possible <idA>__<idB>.json
          {"de", "vers", "registre", "maj", "griefs": [{"id", "grief", "statut",
           "exemples": [{"auteur", "date", "verbatim", "media", "source_url"}]}]}
          registre : ennemi_principal | concurrent_meme_electorat | rival_interne | adversaire_respecte | neutre
          Un grief est servi comme REPROCHE DOCUMENTÉ (ce que le camp dit), jamais comme fait.

Équité : un fichier par candidat et par flèche, même vide et daté (voir tools/dossiers_initialiser.py).
"""
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)
BASE = Path(__file__).resolve().parent / "dossiers"
FAITS = BASE / "faits"
RAPPORTS = BASE / "rapports"
STATUTS_SERVIS = {"verifie_auto", "valide"}
REGISTRES = {
    "ennemi_principal": "C'est ton adversaire principal : frontal, sans concession, mais sur les faits et les reproches documentés.",
    "concurrent_meme_electorat": "Vous visez le même électorat : tu le disqualifies comme copie ou comme traître à ses propres électeurs, pas comme ennemi.",
    "rival_interne": "C'est une querelle de famille : tu parles de trahison de vos idées communes, de division, pas d'ennemi.",
    "adversaire_respecte": "Adversaire que tu respectes : tu attaques les idées, jamais la personne, avec une pointe de considération.",
    "neutre": "Pas de relation particulière : tu attaques sur le programme.",
}
CLASSES_LIBELLE = {
    "condamnation_definitive": "condamnation définitive", "condamnation_appel": "condamnation NON définitive — reprendre l'étape exacte donnée dans le fait (première instance, appel, pourvoi en cassation)",
    "mise_en_examen": "mise en examen (présomption d'innocence)", "vote": "vote", "declaration": "déclaration publique", "sanction": "sanction officielle",
}


def _lire(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
    except Exception:
        logger.warning("dossier illisible : %s", p)
        return {}


def faits_de(candidat_id: str) -> list:
    """Entrées servies (vérifiées) du tiroir faits d'un candidat."""
    d = _lire(FAITS / f"{candidat_id}.json")
    return [e for e in d.get("entrees", []) if e.get("statut") in STATUTS_SERVIS and e.get("fait")]


def rapport(orateur: dict, adversaire: dict) -> dict:
    """Flèche du camp de l'orateur vers l'adversaire : surcharge candidat→candidat sinon famille→famille."""
    for p in (RAPPORTS / f"{orateur['id']}__{adversaire['id']}.json", RAPPORTS / f"{orateur.get('famille')}__{adversaire.get('famille')}.json"):
        d = _lire(p)
        if d:
            d["griefs"] = [g for g in d.get("griefs", []) if g.get("statut", "verifie_auto") in STATUTS_SERVIS and g.get("grief")]
            return d
    return {}


def _src(sources: list) -> str:
    s = [x for x in sources or [] if x.get("url")]
    return ", ".join(f"{x.get('media') or x['url']}" + (f" ({x['date']})" if x.get("date") else "") for x in s[:3])


def pieces_pour(orateur: dict, adversaires: list) -> tuple:
    """(texte_prompt, preuves) : ce que l'orateur sait des adversaires présents, en Arène."""
    blocs, preuves = [], []
    for adv in adversaires:
        faits = faits_de(adv["id"])
        r = rapport(orateur, adv)
        lignes = [f"— {adv['nom']} ({adv.get('parti_court') or adv.get('parti', '')}) :"]
        if r.get("registre") in REGISTRES:
            lignes.append(f"  REGISTRE : {REGISTRES[r['registre']]}")
        if faits:
            lignes.append("  FAITS VÉRIFIÉS (tu peux les citer tels quels, avec leur qualification exacte, jamais aggravés) :")
            for e in faits[:6]:
                lignes.append(f"   · [{CLASSES_LIBELLE.get(e.get('classe'), e.get('classe'))}] {e['fait']}" + (f" — sources : {_src(e.get('sources'))}" if e.get("sources") else ""))
                preuves.append({"type": "dossier", "candidat_id": adv["id"], "titre": CLASSES_LIBELLE.get(e.get("classe"), e.get("classe", "")),
                                "page": e.get("date", ""), "theme": e.get("instance", ""), "extrait": e["fait"], "texte_integral": e["fait"],
                                "url": (e.get("sources") or [{}])[0].get("url", ""), "orateur": (e.get("sources") or [{}])[0].get("media", ""), "date_lisible": e.get("date", "")})
        else:
            lignes.append("  FAITS VÉRIFIÉS : aucun au dossier. Tu ne lui prêtes aucune condamnation, aucune affaire.")
        if r.get("griefs"):
            lignes.append("  CE QUE TON CAMP LUI REPROCHE (reproches documentés — porte-les COMME DES REPROCHES, pas comme des faits) :")
            for g in r["griefs"][:5]:
                ex = (g.get("exemples") or [{}])[0]
                lignes.append(f"   · {g['grief']}" + (f" — ex. {ex.get('auteur', '')}, {ex.get('date', '')} : « {ex.get('verbatim', '')} »" if ex.get("verbatim") else ""))
                preuves.append({"type": "reproche", "candidat_id": adv["id"], "titre": g["grief"], "page": "", "theme": r.get("registre", ""),
                                "extrait": (f"{ex.get('auteur', '')}, {ex.get('date', '')} : « {ex.get('verbatim', '')} »" if ex.get("verbatim") else g["grief"]),
                                "texte_integral": g["grief"] + " " + " / ".join(f"{x.get('auteur', '')} ({x.get('date', '')}) : « {x.get('verbatim', '')} »" for x in (g.get("exemples") or [])[:3]),
                                "url": ex.get("source_url", ""), "orateur": ex.get("auteur", ""), "date_lisible": ex.get("date", "")})
        blocs.append("\n".join(lignes))
    if not blocs:
        return "", []
    texte = ("\n\nDOSSIER DE TES ADVERSAIRES (Arène) :\n" + "\n".join(blocs) +
             "\nRÈGLES DU DOSSIER : un fait se cite avec sa qualification exacte (« condamnée en première instance », « mis en examen »), jamais aggravée. "
             "Un reproche se porte comme reproche de ton camp (« vous que nous appelons… », « comme le disait X… »), jamais comme une vérité établie. "
             "Rien sur la vie privée, la santé, la famille. Aucune insulte nue : le coup, c'est le fait ou le reproche documenté.")
    return texte, preuves
