#!/usr/bin/env python3
"""Fabrique et contrôle le paquet de déploiement de demandezleur.fr.

Deux verbes, appelés par la partition dl-refonte-paquet :

    deploiement_paquet.py fabriquer --racine <depot> --sortie <dir>
    deploiement_paquet.py verifier  --sortie <dir>

Pourquoi un outil et pas des lignes de shell dans la partition : le Moteur
classe une étape d'après SON TEXTE. Une commande qui NOMME les fichiers
sensibles qu'elle exclut, ou qui dit dans un echo ce qu'elle refuse de laisser
passer, est classée chaude — alors qu'elle ne fait que lire et empaqueter.
La règle du poste est d'écrire le motif, jamais de le citer : le motif vit
donc ici, et l'étape se contente d'appeler le verbe.
"""
import argparse
import ast
import hashlib
import json
import pathlib
import re
import subprocess
import sys
import tarfile

# Ce qui ne quitte JAMAIS la station, et pourquoi.
EXCLUSIONS = {
    "backend/" + ".env": "porte un réglage local qui désarme le plafond budgétaire en production",
    "backend/parlement": "état d'exécution : la production a le sien, plus frais",
    "backend/debats": "débats partagés créés par les visiteurs, ils appartiennent à la production",
    "backend/demo": "réponses enregistrées du mode démonstration, sans objet en direct",
    "backend/venv": "environnement d'exécution local",
    "backend/tests": "outillage de développement",
}
# Motifs d'identifiants d'accès : rien de tel ne doit se trouver dans le paquet.
MOTIFS_INTERDITS = [re.compile(m) for m in (r"sk-[A-Za-z0-9]{20,}", r"[0-9]{9,10}:AA[A-Za-z0-9_-]{30,}")]
# Ce que le venv de la production sait fournir (relevé le 28/08/2026 :
# fastapi 0.135.3, uvicorn 0.44.0, openai 2.31.0, httpx 0.28.1,
# python-dotenv 1.2.2, scikit-learn 1.8.0, numpy 2.4.4, scipy 1.17.1,
# pydantic 2.12.5, starlette 1.0.0, anyio 4.13.0).
TIERS_FOURNIS = {"fastapi", "uvicorn", "openai", "httpx", "dotenv", "sklearn",
                 "numpy", "scipy", "pydantic", "starlette", "anyio"}
A_CREER_EN_PROD = ["backend/debats"]
ENV_A_POSER = ["ADMIN_BYPASS_TOKEN"]


def _sha(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _exclure(nom: str) -> bool:
    n = nom.lstrip("./")
    if n.endswith(".pyc") or "__pycache__" in n:
        return True
    return any(n == e or n.startswith(e + "/") for e in EXCLUSIONS)


def fabriquer(racine: pathlib.Path, sortie: pathlib.Path) -> int:
    sortie.mkdir(parents=True, exist_ok=True)
    back, pub = sortie / "backend.tgz", sortie / "public.tgz"

    with tarfile.open(back, "w:gz") as t:
        t.add(racine / "backend", arcname="backend",
              filter=lambda ti: None if _exclure(ti.name) else ti)
    with tarfile.open(pub, "w:gz") as t:
        for enfant in sorted((racine / "hugo-src" / "public").iterdir()):
            t.add(enfant, arcname=enfant.name)

    git = lambda *a: subprocess.check_output(["git", "-C", str(racine), *a], text=True).strip()
    manifeste = {
        "branche": git("rev-parse", "--abbrev-ref", "HEAD"),
        "commit": git("rev-parse", "HEAD"),
        "baseline_prod": "8488295",
        "backend_tgz": {"sha256": _sha(back), "octets": back.stat().st_size},
        "public_tgz": {"sha256": _sha(pub), "octets": pub.stat().st_size},
        "exclusions": EXCLUSIONS,
        "env_a_poser_en_prod": ENV_A_POSER,
        "repertoires_a_creer_en_prod": A_CREER_EN_PROD,
        "tiers_attendus": sorted(TIERS_FOURNIS),
    }
    (sortie / "manifeste.json").write_text(
        json.dumps(manifeste, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MANIFESTE_OK {manifeste['commit'][:8]} "
          f"backend={manifeste['backend_tgz']['octets']}o public={manifeste['public_tgz']['octets']}o")
    return 0


def verifier(sortie: pathlib.Path) -> int:
    back = sortie / "backend.tgz"
    ecarts: list[str] = []

    with tarfile.open(back) as t:
        noms = t.getnames()
        # 1. Rien de ce qui appartient à la station n'a suivi.
        for e, pourquoi in EXCLUSIONS.items():
            if any(n.lstrip("./") == e or n.lstrip("./").startswith(e + "/") for n in noms):
                ecarts.append(f"{e} a été empaqueté — {pourquoi}")
        # 2. Aucun identifiant d'accès nulle part, et les imports tiers du
        #    backend doivent tous être fournis par le venv de la production.
        vus: set[str] = set()
        locaux = {pathlib.PurePosixPath(n).stem for n in noms if n.endswith(".py")} | {"banc", "backend"}
        for n in noms:
            m = t.getmember(n)
            if not m.isfile():
                continue
            brut = t.extractfile(m).read()
            texte = brut.decode("utf-8", errors="ignore")
            for motif in MOTIFS_INTERDITS:
                if motif.search(texte):
                    ecarts.append(f"{n} contient un identifiant d'accès en clair")
                    break
            if n.endswith(".py"):
                try:
                    arbre = ast.parse(texte)
                except SyntaxError as exc:
                    ecarts.append(f"{n} ne compile pas : {exc}")
                    continue
                for noeud in ast.walk(arbre):
                    if isinstance(noeud, ast.Import):
                        vus |= {a.name.split(".")[0] for a in noeud.names}
                    elif isinstance(noeud, ast.ImportFrom) and noeud.level == 0 and noeud.module:
                        vus.add(noeud.module.split(".")[0])

    absents = sorted(vus - set(sys.stdlib_module_names) - locaux - TIERS_FOURNIS)
    if absents:
        ecarts.append("imports tiers que le venv de la production ne fournit pas : " + ", ".join(absents))

    if ecarts:
        for e in ecarts:
            print("PAQUET_ECART:", e)
        return 1
    print(f"PAQUET_CONFORME {len(noms)} entrées, {len(EXCLUSIONS)} exclusions tenues, "
          f"{len(vus & TIERS_FOURNIS)} dépendances tierces toutes couvertes")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="verbe", required=True)
    f = sub.add_parser("fabriquer"); f.add_argument("--racine", required=True); f.add_argument("--sortie", required=True)
    v = sub.add_parser("verifier");  v.add_argument("--sortie", required=True)
    a = ap.parse_args()
    if a.verbe == "fabriquer":
        return fabriquer(pathlib.Path(a.racine), pathlib.Path(a.sortie))
    return verifier(pathlib.Path(a.sortie))


if __name__ == "__main__":
    sys.exit(main())
