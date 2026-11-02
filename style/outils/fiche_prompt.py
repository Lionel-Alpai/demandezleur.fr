"""Rend une fiche de style compilée (fiches/<id>.json) en bloc de prompt pour l'orateur.

Le bloc remplace ton_<famille> : il dit COMMENT le candidat parle, jamais CE qu'il pense (le fond
vient des extraits de programme). Les preuves ne sont pas montrées à l'orateur — seulement les
traits — pour limiter la recopie ; les exemples sont donnés comme diapason, interdits de recopie.
"""
import json
from pathlib import Path

FICHES = Path(__file__).resolve().parent.parent / "fiches"


def charger_fiche(candidat_id: str, dossier: Path = FICHES):
    p = Path(dossier) / f"{candidat_id}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def rendre(fiche: dict, nom: str) -> str:
    l = [f"TA VOIX — {nom.upper()} (fiche de style : la FORME seulement ; le fond vient de tes extraits).",
         f"Posture : {' '.join(fiche['posture'].split())}",
         "Tes manières (une ou deux par réplique, jamais toutes, jamais la même deux fois de suite) :"]
    l += [f"- {t['trait']}" for t in fiche["traits"]]
    r = fiche["reactions"]
    l.append("Selon la situation :")
    l += [f"- {k.replace('_', ' ')} : {' '.join(v.split())}" for k, v in r.items()]
    l.append("Tics : au plus UNE fois par débat chacun, jamais deux dans la même réplique : "
             + ", ".join(f"« {t['forme']} »" for t in fiche["tics"]) + ".")
    l.append("Tu ne fais jamais : " + " ; ".join(j["quoi"] for j in fiche["ne_fait_jamais"]) + ".")
    l.append("Diapason (de vraies phrases à toi, pour le TON — ne les recopie JAMAIS, même en partie) : "
             + " / ".join(f"« {e} »" for e in fiche["exemples"]))
    l.append("Pas d'imitation de chansonnier : une voix reconnaissable, pas un pastiche.")
    return "\n".join(l)
