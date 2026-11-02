#!/usr/bin/env python3
r"""Vérificateur et banc de test pour dl-style-mesure-signature.

Modes :
  1. --banc : exécute les tests en bac temporaire isolé (témoin négatif rejeté,
     exclusion de voix_mixtes=true prouvée, double exécution déterministe sur
     les verbatims réels, >= 15 n-grammes par candidat, >= 3 mesures distinctives)
     et émet BANC_SIGNATURE_OK.
  2. Juge d'effet (par défaut) : contrôle les fichiers installés dans
     <signature_dir>/<slug>.json, relance un calcul indépendant en répertoire
     temporaire pour prouver que deux exécutions produisent exactement le même
     SHA-256, vérifie >= 15 n-grammes par candidat et >= 3 mesures distinguant
     nettement marine-le-pen et jean-luc-melenchon, puis émet VERDICT_SIGNATURE_OK.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile

# Import local depuis le même dossier (outils/)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import mesure_signature  # noqa: E402


CANDIDATS_PILOTES = ("marine-le-pen", "jean-luc-melenchon")

CLES_REQUISES = (
    "candidat",
    "couverture_corpus",
    "global",
    "par_situation",
    "longueur_phrases",
    "ponctuation_et_syntaxe",
    "taux_questions_pct",
    "taux_exclamations_pct",
    "taux_phrases_nominales_pct",
    "pronoms",
    "ngrammes_signature",
    "formules_ouverture",
    "formules_adresse",
    "reactions_interruption",
)


def sha256_fichier(chemin: Path) -> str:
    return hashlib.sha256(chemin.read_bytes()).hexdigest()


def ecart_relatif_pct(val_a: float, val_b: float) -> float:
    denom = max(abs(val_a), abs(val_b), 1e-6)
    return (abs(val_a - val_b) * 100.0) / denom


def evaluer_distinction_candidats(sig_mlp: dict, sig_jlm: dict) -> list[dict]:
    r"""Évalue sur combien de mesures indépendantes les deux candidats se distinguent nettement."""
    mesures_distinctives: list[dict] = []

    # Dimension 1 : Dispersion et rythme de phrase (IQR ou moyenne ou ratio rafales/périodes)
    lp_mlp = sig_mlp["longueur_phrases"]
    lp_jlm = sig_jlm["longueur_phrases"]
    ecart_iqr = ecart_relatif_pct(lp_mlp["iqr_mots"], lp_jlm["iqr_mots"])
    ecart_moy = ecart_relatif_pct(lp_mlp["moyenne_mots"], lp_jlm["moyenne_mots"])
    ecart_raf = ecart_relatif_pct(
        lp_mlp["ratio_rafales_periodes"], lp_jlm["ratio_rafales_periodes"]
    )
    if max(ecart_iqr, ecart_moy, ecart_raf) >= 10.0:
        mesures_distinctives.append({
            "famille": "longueur_phrases",
            "detail": (
                f"moyenne={lp_mlp['moyenne_mots']} vs {lp_jlm['moyenne_mots']} mots, "
                f"iqr={lp_mlp['iqr_mots']} vs {lp_jlm['iqr_mots']}, "
                f"ratio_rafales_periodes={lp_mlp['ratio_rafales_periodes']} vs {lp_jlm['ratio_rafales_periodes']}"
            ),
            "ecart_max_pct": round(max(ecart_iqr, ecart_moy, ecart_raf), 2),
        })

    # Dimension 2 : Ponctuation expressive et syntaxe (questions, exclamations, phrases nominales)
    ecart_q = ecart_relatif_pct(
        sig_mlp["taux_questions_pct"], sig_jlm["taux_questions_pct"]
    )
    ecart_e = ecart_relatif_pct(
        sig_mlp["taux_exclamations_pct"], sig_jlm["taux_exclamations_pct"]
    )
    ecart_n = ecart_relatif_pct(
        sig_mlp["taux_phrases_nominales_pct"], sig_jlm["taux_phrases_nominales_pct"]
    )
    if max(ecart_q, ecart_e, ecart_n) >= 15.0:
        mesures_distinctives.append({
            "famille": "ponctuation_et_syntaxe",
            "detail": (
                f"questions={sig_mlp['taux_questions_pct']}% vs {sig_jlm['taux_questions_pct']}%, "
                f"exclamations={sig_mlp['taux_exclamations_pct']}% vs {sig_jlm['taux_exclamations_pct']}%, "
                f"nominales={sig_mlp['taux_phrases_nominales_pct']}% vs {sig_jlm['taux_phrases_nominales_pct']}%"
            ),
            "ecart_max_pct": round(max(ecart_q, ecart_e, ecart_n), 2),
        })

    # Dimension 3 : Pronoms et marqueurs de posture (je, nous, vous, on, les Français)
    pr_mlp = sig_mlp["pronoms"]
    pr_jlm = sig_jlm["pronoms"]
    ecart_lf = ecart_relatif_pct(
        pr_mlp["les_francais"]["pour_1000_mots"],
        pr_jlm["les_francais"]["pour_1000_mots"],
    )
    ecart_nous = ecart_relatif_pct(
        pr_mlp["nous"]["pour_1000_mots"],
        pr_jlm["nous"]["pour_1000_mots"],
    )
    ecart_on = ecart_relatif_pct(
        pr_mlp["on"]["pour_1000_mots"],
        pr_jlm["on"]["pour_1000_mots"],
    )
    ecart_je = ecart_relatif_pct(
        pr_mlp["je"]["pour_1000_mots"],
        pr_jlm["je"]["pour_1000_mots"],
    )
    if max(ecart_lf, ecart_nous, ecart_on, ecart_je) >= 15.0:
        mesures_distinctives.append({
            "famille": "pronoms",
            "detail": (
                f"les_francais={pr_mlp['les_francais']['pour_1000_mots']}‰ vs {pr_jlm['les_francais']['pour_1000_mots']}‰, "
                f"nous={pr_mlp['nous']['pour_1000_mots']}‰ vs {pr_jlm['nous']['pour_1000_mots']}‰, "
                f"on={pr_mlp['on']['pour_1000_mots']}‰ vs {pr_jlm['on']['pour_1000_mots']}‰, "
                f"je={pr_mlp['je']['pour_1000_mots']}‰ vs {pr_jlm['je']['pour_1000_mots']}‰"
            ),
            "ecart_max_pct": round(max(ecart_lf, ecart_nous, ecart_on, ecart_je), 2),
        })

    # Dimension 4 : N-grammes signature (ensembles disjoints par log-odds)
    ng_mlp = {item["ngramme"] for item in sig_mlp["ngrammes_signature"][:15]}
    ng_jlm = {item["ngramme"] for item in sig_jlm["ngrammes_signature"][:15]}
    if len(ng_mlp) >= 15 and len(ng_jlm) >= 15 and len(ng_mlp & ng_jlm) == 0:
        mesures_distinctives.append({
            "famille": "ngrammes_signature",
            "detail": (
                f"top3_mlp={[x['ngramme'] for x in sig_mlp['ngrammes_signature'][:3]]} vs "
                f"top3_jlm={[x['ngramme'] for x in sig_jlm['ngrammes_signature'][:3]]}"
            ),
            "ecart_max_pct": 100.0,
        })

    # Dimension 5 : Formules d'ouverture et d'adresse
    adr_mlp = sig_mlp["formules_adresse"]["taux_pour_1000_mots"]
    adr_jlm = sig_jlm["formules_adresse"]["taux_pour_1000_mots"]
    ouv_mlp = sig_mlp["formules_ouverture"]["repartition_categories"][
        "adresse_institutionnelle"
    ]["part_pct"]
    ouv_jlm = sig_jlm["formules_ouverture"]["repartition_categories"][
        "adresse_institutionnelle"
    ]["part_pct"]
    ecart_adr = max(ecart_relatif_pct(adr_mlp, adr_jlm), ecart_relatif_pct(ouv_mlp, ouv_jlm))
    if ecart_adr >= 15.0:
        mesures_distinctives.append({
            "famille": "formules_ouverture_et_adresse",
            "detail": (
                f"taux_adresse={adr_mlp}‰ vs {adr_jlm}‰, "
                f"ouverture_institutionnelle={ouv_mlp}% vs {ouv_jlm}%"
            ),
            "ecart_max_pct": round(ecart_adr, 2),
        })

    # Dimension 6 : Réactions à l'interruption et dynamique d'hémicycle
    int_mlp = sig_mlp["reactions_interruption"]
    int_jlm = sig_jlm["reactions_interruption"]
    ecart_int = max(
        ecart_relatif_pct(
            int_mlp.get("part_interruptions_hemicycle_pct", 0.0),
            int_jlm.get("part_interruptions_hemicycle_pct", 0.0),
        ),
        ecart_relatif_pct(
            int_mlp.get("longueur_moyenne_interruption_mots", 0.0),
            int_jlm.get("longueur_moyenne_interruption_mots", 0.0),
        ),
    )
    if ecart_int >= 15.0:
        mesures_distinctives.append({
            "famille": "reactions_interruption",
            "detail": (
                f"part_interruptions_an={int_mlp.get('part_interruptions_hemicycle_pct')}% vs "
                f"{int_jlm.get('part_interruptions_hemicycle_pct')}%, "
                f"longueur_interruption={int_mlp.get('longueur_moyenne_interruption_mots')} vs "
                f"{int_jlm.get('longueur_moyenne_interruption_mots')} mots"
            ),
            "ecart_max_pct": round(ecart_int, 2),
        })

    return mesures_distinctives


def verifier_structure_signature(sig: dict, slug_attendu: str) -> list[str]:
    erreurs: list[str] = []
    if sig.get("candidat") != slug_attendu:
        erreurs.append(f"{slug_attendu}: champ candidat invalide ({sig.get('candidat')})")
    for cle in CLES_REQUISES:
        if cle not in sig:
            erreurs.append(f"{slug_attendu}: clé requise manquante '{cle}'")
    if not isinstance(sig.get("par_situation"), dict) or len(sig["par_situation"]) < 2:
        erreurs.append(f"{slug_attendu}: par_situation doit contenir au moins 2 situations")
    nb_ng = len(sig.get("ngrammes_signature", []))
    if nb_ng < 15:
        erreurs.append(f"{slug_attendu}: seulement {nb_ng} n-grammes distinctifs (< 15 requis)")
    # Vérifier la présence des 5 pronoms attendus
    pronoms = sig.get("pronoms", {})
    for p in ("je", "nous", "vous", "on", "les_francais"):
        if p not in pronoms:
            erreurs.append(f"{slug_attendu}: pronom '{p}' manquant dans pronoms")
    return erreurs


def executer_banc(verbatims_dir: Path) -> int:
    r"""Banc isolé en TemporaryDirectory : témoin négatif + exclusion voix_mixtes + double run réel."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)

        # 1. Cas témoin négatif : deux candidats aux textes identiques ne doivent avoir
        #    AUCUN n-gramme distinctif (log_odds == 0) ni aucune mesure distinctive.
        temoin_vdir = tmp_path / "verbatims_temoin"
        temoin_vdir.mkdir(parents=True, exist_ok=True)
        lignes_temoin = [
            json.dumps({
                "texte": "Monsieur le ministre, nous demandons des réponses claires. Pourquoi refusez-vous ?",
                "locuteur": "cand-a",
                "situation": "interpellation",
                "date": "2025-01-01",
                "source": "AN",
                "url": "https://example.org/1",
                "mots": 11,
                "voix_mixtes": False,
            }),
            json.dumps({
                "texte": "Ce texte mixte avec intervieweur doit être exclu du calcul de style.",
                "locuteur": "cand-a",
                "situation": "interview",
                "date": "2025-01-02",
                "source": "YT",
                "url": "https://example.org/2",
                "mots": 12,
                "voix_mixtes": True,
            }),
        ]
        (temoin_vdir / "cand-a.an.jsonl").write_text("\n".join(lignes_temoin) + "\n", encoding="utf-8")
        (temoin_vdir / "cand-b.an.jsonl").write_text("\n".join(lignes_temoin) + "\n", encoding="utf-8")

        sigs_temoin = mesure_signature.calculer_signatures_corpus(
            temoin_vdir, ["cand-a", "cand-b"], min_freq_ngram=1
        )
        # Preuve d'exclusion de voix_mixtes=True
        excl_a = sigs_temoin["cand-a"]["couverture_corpus"]["lignes_exclues_voix_mixtes"]
        ret_a = sigs_temoin["cand-a"]["couverture_corpus"]["lignes_retenues_voix_pure"]
        if excl_a != 1 or ret_a != 1:
            print(f"BANC_KO: filtrage voix_mixtes défaillant (exclus={excl_a}, retenus={ret_a})")
            return 1

        # Preuve que le témoin identique est bien détecté comme non-distinctif (0 n-gramme, 0 écart)
        dist_temoin = evaluer_distinction_candidats(sigs_temoin["cand-a"], sigs_temoin["cand-b"])
        ng_temoin = len(sigs_temoin["cand-a"]["ngrammes_signature"])
        if len(dist_temoin) != 0 or ng_temoin != 0:
            print(f"BANC_KO: le témoin identique aurait dû donner 0 distinction (obtenu {len(dist_temoin)})")
            return 1

        # 2. Double exécution sur les verbatims réels dans deux sous-dossiers isolés du bac
        out_run1 = tmp_path / "run1"
        out_run2 = tmp_path / "run2"
        rc1 = mesure_signature.main([
            "--verbatims-dir", str(verbatims_dir),
            "--out-dir", str(out_run1),
            "--candidats", ",".join(CANDIDATS_PILOTES),
            "--no-backup",
        ])
        rc2 = mesure_signature.main([
            "--verbatims-dir", str(verbatims_dir),
            "--out-dir", str(out_run2),
            "--candidats", ",".join(CANDIDATS_PILOTES),
            "--no-backup",
        ])
        if rc1 != 0 or rc2 != 0:
            print(f"BANC_KO: échec d'exécution de mesure_signature.py (rc1={rc1}, rc2={rc2})")
            return 1

        sigs_reel: dict[str, dict] = {}
        for slug in CANDIDATS_PILOTES:
            f1 = out_run1 / f"{slug}.json"
            f2 = out_run2 / f"{slug}.json"
            if not f1.exists() or not f2.exists():
                print(f"BANC_KO: fichier {slug}.json non généré")
                return 1
            sha1 = sha256_fichier(f1)
            sha2 = sha256_fichier(f2)
            if sha1 != sha2:
                print(f"BANC_KO: non-déterminisme sur {slug}.json ({sha1} != {sha2})")
                return 1
            sig = json.loads(f1.read_text(encoding="utf-8"))
            errs = verifier_structure_signature(sig, slug)
            if errs:
                for e in errs:
                    print(f"BANC_KO: {e}")
                return 1
            sigs_reel[slug] = sig

        dist_reel = evaluer_distinction_candidats(
            sigs_reel["marine-le-pen"], sigs_reel["jean-luc-melenchon"]
        )
        if len(dist_reel) < 3:
            print(
                f"BANC_KO: moins de 3 mesures distinctives sur le corpus réel ({len(dist_reel)})"
            )
            return 1

        print(
            f"BANC_SIGNATURE_OK temoin_ecart=0->reel_ecart={len(dist_reel)} "
            f"mlp_ng={len(sigs_reel['marine-le-pen']['ngrammes_signature'])} "
            f"jlm_ng={len(sigs_reel['jean-luc-melenchon']['ngrammes_signature'])}"
        )
        return 0


def executer_juge(verbatims_dir: Path, signature_dir: Path) -> int:
    r"""Vérifie les fichiers produits et prouve que 2 exécutions donnent le même SHA-256."""
    sigs: dict[str, dict] = {}
    shas_prod: dict[str, str] = {}

    for slug in CANDIDATS_PILOTES:
        cible = signature_dir / f"{slug}.json"
        if not cible.exists():
            print(f"JUGE_KO: fichier absent {cible}")
            return 1
        shas_prod[slug] = sha256_fichier(cible)
        sig = json.loads(cible.read_text(encoding="utf-8"))
        errs = verifier_structure_signature(sig, slug)
        if errs:
            for e in errs:
                print(f"JUGE_KO: {e}")
            return 1
        sigs[slug] = sig

    # Seconde exécution indépendante en répertoire temporaire pour prouver même SHA-256
    with tempfile.TemporaryDirectory() as tmp_recalcul:
        recalcul_dir = Path(tmp_recalcul)
        rc = mesure_signature.main([
            "--verbatims-dir", str(verbatims_dir),
            "--out-dir", str(recalcul_dir),
            "--candidats", ",".join(CANDIDATS_PILOTES),
            "--no-backup",
        ])
        if rc != 0:
            print(f"JUGE_KO: seconde exécution en échec (rc={rc})")
            return 1
        for slug in CANDIDATS_PILOTES:
            sha_bis = sha256_fichier(recalcul_dir / f"{slug}.json")
            if sha_bis != shas_prod[slug]:
                print(
                    f"JUGE_KO: SHA-256 différent entre exécution 1 et 2 pour {slug} "
                    f"({shas_prod[slug]} != {sha_bis})"
                )
                return 1
            print(f"SHA256_IDENTIQUE {slug} sha256={shas_prod[slug]}")

    distinctions = evaluer_distinction_candidats(
        sigs["marine-le-pen"], sigs["jean-luc-melenchon"]
    )
    for d in distinctions:
        print(f"MESURE_DISTINCTIVE [{d['famille']}] ({d['ecart_max_pct']}%) : {d['detail']}")

    if len(distinctions) < 3:
        print(f"JUGE_KO: seulement {len(distinctions)} mesures distinctives (< 3 requises)")
        return 1

    ng_mlp = len(sigs["marine-le-pen"]["ngrammes_signature"])
    ng_jlm = len(sigs["jean-luc-melenchon"]["ngrammes_signature"])
    print(
        f"VERDICT_SIGNATURE_OK : 2 candidats pilotes · même sha sur 2 exécutions · "
        f"ngrammes mlp={ng_mlp} jlm={ng_jlm} (>=15) · "
        f"{len(distinctions)} familles de mesures distinctives (>=3)"
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    racine_style = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Banc et juge d'effet pour les signatures de style oral."
    )
    parser.add_argument(
        "--banc",
        action="store_true",
        help="Exécuter le banc de test isolé en TemporaryDirectory",
    )
    parser.add_argument(
        "--verbatims-dir",
        type=Path,
        default=racine_style / "verbatims",
        help="Répertoire contenant les fichiers <slug>.*.jsonl",
    )
    parser.add_argument(
        "--signature-dir",
        type=Path,
        default=racine_style / "signature",
        help="Répertoire contenant les fichiers <slug>.json produits",
    )
    args = parser.parse_args(argv)

    if args.banc:
        return executer_banc(args.verbatims_dir)
    return executer_juge(args.verbatims_dir, args.signature_dir)


if __name__ == "__main__":
    raise SystemExit(main())
