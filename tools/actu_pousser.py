#!/usr/bin/env python3
"""Pousse le tiroir ACTU local vers l'ingest de prod.

Secrets lus à l'exécution depuis /etc/demandezleur-actu.json — aucun secret
en clair dans ce fichier.
"""
import argparse
import datetime
import json
import sys
import urllib.error
import urllib.request

FICHIER_ACTU = "/opt/demandezleur-actu/backend/actu/{jour}.json"
CONFIG_PAR_DEFAUT = "/etc/demandezleur-actu.json"


def main():
    parser = argparse.ArgumentParser(
        description="Pousse le tiroir ACTU local vers l'ingest de prod."
    )
    parser.add_argument(
        "--config", default=CONFIG_PAR_DEFAUT,
        help="Fichier de configuration JSON (défaut %(default)s)",
    )
    parser.add_argument(
        "--jour", default=datetime.date.today().isoformat(),
        help="Jour au format AAAA-MM-JJ (défaut : aujourd'hui)",
    )
    parser.add_argument(
        "--sans-push", action="store_true",
        help="Dry-run : lit et prépare le corps mais n'émet pas le POST",
    )
    args = parser.parse_args()

    with open(args.config) as f:
        conf = json.load(f)

    jour_path = FICHIER_ACTU.format(jour=args.jour)
    try:
        with open(jour_path) as f:
            donnees = json.load(f)
    except FileNotFoundError:
        print(f"ACTU_PUSH skip : pas de fichier {args.jour}")
        return 0

    # Le tiroir local peut être une liste d'entrées ou un objet contenant la
    # clé "entrees" ; on normalise pour bâtir le corps attendu par l'ingest.
    if isinstance(donnees, list):
        entrees = donnees
    elif isinstance(donnees, dict) and "entrees" in donnees:
        entrees = donnees["entrees"]
    else:
        entrees = [donnees]

    # [sans-entree] Un passage sans entree nouvelle est un jour normal, pas une
    # panne : l'ingest refuse une liste vide (422), on sort sain sans POST.
    if not entrees:
        print(f"RIEN_A_POUSSER : {args.jour} (0 entree), POST non envoyé")
        return 0

    corps = json.dumps({
        "schema": "actu/1",
        "jour": args.jour,
        "entrees": entrees,
    }).encode("utf-8")

    if args.sans_push:
        print(
            f"ACTU_PUSH dry-run : {args.jour} "
            f"({len(entrees)} entree(s)), POST non envoyé"
        )
        return 0

    requete = urllib.request.Request(
        conf["prod_ingest_url"],
        data=corps,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Actu-Token": conf["ingest_token"],
        },
    )

    try:
        with urllib.request.urlopen(requete, timeout=120) as rep:
            reponse = rep.read().decode("utf-8", "replace")
            print(f"ACTU_PUSH ok : {rep.status} {reponse[:120]}")
            return 0
    except urllib.error.HTTPError as e:
        reponse = e.read().decode("utf-8", "replace")
        print(f"ACTU_PUSH echec : {e.code} {reponse}")
        return 1
    except urllib.error.URLError as e:
        print(f"ACTU_PUSH echec : réseau {e.reason}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
