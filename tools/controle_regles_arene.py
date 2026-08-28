#!/usr/bin/env python3
"""Contrôle des règles d'Arène CONTRE LE CODE RÉELLEMENT DÉPLOYÉ.

    cd <backend> && venv/bin/python controle_regles_arene.py

Pourquoi ce fichier existe : un site qui répond 200 ne prouve rien sur une règle
de contenu. Les trois règles nées de la session du 28/08/2026 se vérifient en
rejouant, là où elles tournent, les phrases exactes qui les ont fait naître —
et une phrase légitime, pour s'assurer que la règle tient le débat au lieu de le
censurer. Toute sortie autre que CONTROLE_REGLES_OK est un échec.

À lancer depuis le répertoire du backend : il importe garde_fou et debat en place.
"""
import sys

sys.path.insert(0, ".")

import debat  # noqa: E402
import garde_fou as G  # noqa: E402

# (libellé, phrase, pièces fournies au modèle, doit être retirée)
CAS = [
    ("acte parlementaire inventé — aucune pièce ne le porte",
     "Madame Le Pen, vous n'avez même pas daigné voter la résolution "
     "pour dénoncer les accords franco-algériens de 1968 !",
     [], True),

    ("reproche sur un texte du propre parti de la cible",
     "Madame Le Pen, vous n'avez pas voté la résolution RN sur les accords de 1968 !",
     [], True),

    ("acte réellement ancré dans une pièce — doit RESTER",
     "Madame Le Pen, vous avez voté la loi Duplomb sans en mesurer les effets !",
     [{"type": "dossier", "candidat_id": "marine-le-pen", "titre": "Assemblée",
       "texte_integral": "scrutin sur la loi Duplomb, adoptée le 8 juillet"}], False),

    ("attaque rhétorique sans acte parlementaire — doit RESTER",
     "Madame Le Pen, votre obsession sécuritaire ne protège personne !",
     [], False),
]


def main() -> int:
    faits = debat.charger_faits()
    cible = debat.charger_candidat("marine-le-pen")
    echecs = []
    for libelle, phrase, pieces, doit_partir in CAS:
        _, revisions = G.verifier_faits(phrase, [cible], faits, cible["id"], pieces)
        partie = bool(revisions)
        etat = "retirée" if partie else "gardée"
        if partie != doit_partir:
            echecs.append(f"{libelle} → {etat}, attendu {'retirée' if doit_partir else 'gardée'}")
        else:
            print(f"  ✓ {libelle} → {etat}")

    # La production ne doit pas avoir changé de modèle à l'occasion d'un correctif.
    import llm
    if "deepseek" not in llm.BASE_URL:
        echecs.append(f"fournisseur de production inattendu : {llm.BASE_URL}")
    else:
        print(f"  ✓ fournisseur de production inchangé : {llm.MODELE} (juge : {llm.MODELE_JUGE})")

    if echecs:
        for e in echecs:
            print("CONTROLE_REGLES_FAIL:", e)
        return 1
    print(f"CONTROLE_REGLES_OK {len(CAS)} cas conformes, modèle de production inchangé")
    return 0


if __name__ == "__main__":
    sys.exit(main())
