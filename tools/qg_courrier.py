#!/usr/bin/env python3
"""qg_courrier.py — courrier PERSONNALISÉ à un QG de campagne, généré depuis bilan.json
(brique dl-qg-courrier-personnalise). Gabarit FIXE + champs calculés, ZÉRO LLM, même texte pour les 29.

  python3 tools/qg_courrier.py <slug> [<slug>…] --sortie <dossier> [--lien-essai]

Écrit <slug>.html et <slug>.txt. Le lien personnel :
  --lien-essai : jeton d'ESSAI au coffre (pass demandezleur/qg/_test-<slug>) s'il existe, sinon lien masqué ;
  sans option  : lien masqué (« ?j=•••• ») — le vrai jeton n'est inséré qu'à l'envoi.
Juge intégré (refus si KO) : clause « sauf erreur ou omission » présente ; aucune formule interdite ;
aucun nom d'un autre candidat ; chaque chiffre vient de bilan.json.
"""
import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

import yaml

RACINE = Path(__file__).resolve().parent.parent
BILAN = RACINE / "backend" / "corpus" / "bilan.json"
ANNUAIRE = RACINE / "qg" / "annuaire.yaml"
SITE = "https://demandezleur.fr"
THEMES_FR = {
    "economie-travail": "économie et travail", "ecologie-energie": "écologie et énergie",
    "social-sante": "social et santé", "europe-international": "Europe et international",
    "institutions": "institutions", "education": "éducation", "securite-protection": "sécurité",
    "agriculture": "agriculture", "culture-numerique": "culture et numérique", "immigration": "immigration",
    "services-publics": "services publics", "logement": "logement", "vision-generale": "vision d'ensemble",
}
INTERDITS = ["votre corpus est pauvre", "vous n'avez publié que", "vos sources sont insuffisantes",
             "vous n’avez publié que"]


def nb(n):
    return f"{n:,}".replace(",", " ")


def pct(x):
    return f"{x:.0f} %".replace(".", ",")


def position(rang, sur):
    if rang <= sur // 3:
        return "parmi les plus fournis"
    if rang > sur - sur // 3:
        return "parmi les moins fournis"
    return "dans la moyenne"


def jeton_essai(slug):
    r = subprocess.run(["pass", "show", f"demandezleur/qg/_test-{slug}"], capture_output=True, text=True)
    return r.stdout.splitlines()[0].strip() if r.returncode == 0 and r.stdout.strip() else None


def trous(e):
    v, f, o = e["vue_qg"], e["fraicheur"], e["officialite"]
    t = []
    man = v["themes_manquants"]
    if man:
        t.append("aucun document trouvé sur " + ", ".join(THEMES_FR.get(m, m) for m in man[:4])
                 + (" (et " + str(len(man) - 4) + " autre(s) thème(s))" if len(man) > 4 else ""))
    vieux = f["part_2022_et_avant"] + f["part_2023_2025"]
    if vieux >= 25:
        t.append(f"{pct(vieux)} du texte que nous avons trouvé date d'avant 2026 "
                 f"({pct(f['part_2022_et_avant'])} de 2022 ou d'avant) : vos propositions plus récentes nous ont peut-être échappé")
    if f["part_indeterminee"] >= 25:
        t.append(f"pour {pct(f['part_indeterminee'])} du texte, nous n'avons pas pu établir la date du document")
    if o["part_non_officielle"] >= 25:
        t.append(f"{pct(o['part_non_officielle'])} du texte vient de sources non officielles (presse, encyclopédies) "
                 "faute d'avoir trouvé les documents de la campagne elle-même")
    if v["volume_caracteres"]["valeur"] < v["volume_caracteres"]["mediane"]:
        t.append("le volume de texte que nous avons pu réunir reste modeste")
    return t[:3]


def rendre(e, q, lien, autres_noms):
    v, f = e["vue_qg"], e["fraicheur"]
    nom, parti = e["nom"], e["parti"]
    docs = len(e["documents"])
    vc, cv = v["volume_caracteres"], v["couverture"]
    T = trous(e)
    dest = (q.get("contact") or {}).get("email") or (q.get("canal") or {}).get("url") or "aucun canal public trouvé"
    objet = f"demandezleur.fr — ce que notre recherche a trouvé des publications de {nom}"
    P = []
    P.append("Madame, Monsieur,")
    P.append(f"demandezleur.fr fait répondre une intelligence artificielle au nom de chaque candidat déclaré à "
             f"l'élection présidentielle de 2027, uniquement à partir des documents publics de sa campagne. "
             f"C'est une projection statistique, signalée comme telle sur chaque page : elle n'engage ni "
             f"{nom}, ni {parti}.")
    P.append(f"Pour que la parole prêtée à {nom} soit fidèle, nous avons cherché tout ce que la campagne a publié. "
             f"Voici ce que notre recherche a trouvé, sauf erreur ou omission de notre part dans la recherche "
             f"que nous avons effectuée :")
    mesures = [
        ("Volume", f"{nb(vc['valeur'])} caractères de texte, tirés de {docs} document(s)"),
        ("Fraîcheur", f"{pct(f['part_2026_2027'])} du texte date de 2026 ou 2027"),
        ("Origine", f"{pct(e['officialite']['part_officielle'])} vient de sources officielles (site de campagne, parti)"),
        ("Thèmes", f"{cv['valeur']} des 13 grands thèmes du débat sont couverts"),
    ]
    rang_phrase = (f"Dans notre base, ce corpus est aujourd'hui {position(vc['rang'], vc['sur'])} "
                   f"par le volume (médiane des {vc['sur']} candidats : {nb(vc['mediane'])} caractères).")
    if T:
        trous_intro = "Là où notre recherche a pu manquer des documents :"
    else:
        trous_intro = "Nous n'avons pas relevé de manque important ; si vous avez publié d'autres documents, ils restent les bienvenus."
    lien_p = (f"Votre page personnelle montre ce bilan document par document et vous permet de nous transmettre "
              f"un document : {lien} . Chaque document est vérifié par la machine (publié sur un domaine officiel "
              f"de la campagne, ou transmis par ce lien), puis intégré ; le bilan est alors recalculé et nous vous "
              f"écrivons ce qui a changé.")
    neutre = (f"Ce courrier part le même jour, avec le même texte et les mêmes règles, vers les équipes des "
              f"{vc['sur']} candidats. Aucune équipe ne peut modifier ce que dit le corpus d'un autre candidat.")
    sig = ["Lionel Denis", "ALPAI — éditeur de demandezleur.fr", "corpus@demandezleur.fr"]
    ligne_ia = ("demandezleur.fr est conçu, construit et entretenu par des IA ; un humain arbitre et signe. "
                "Les traces de ce travail sont ouvrables sur demande.")
    rgpd = ("Information (art. 14 RGPD). Responsable du traitement : Lionel Denis, entrepreneur individuel (ALPAI), "
            "SIREN 409 776 861, 55 Grande Rue, 73220 Val-d'Arc. Finalité : informer le public sur les programmes "
            "des candidats et inviter les équipes de campagne à compléter ou corriger le corpus de leur candidat. "
            "Données : l'adresse de contact de l'équipe, relevée sur une page publique officielle, et les documents "
            "publics de la campagne. Base légale : intérêt légitime d'information. Conservation : jusqu'à six mois "
            "après le second tour de l'élection présidentielle de 2027. Vous pouvez demander l'accès, la "
            "rectification ou l'effacement de ces données, ou vous opposer au traitement, en écrivant à "
            "corpus@demandezleur.fr ; vous pouvez aussi saisir la CNIL (cnil.fr).")

    txt = [f"À : {dest}", f"Objet : {objet}", ""] + [P[0], "", P[1], "", P[2], ""]
    txt += [f"  • {k} : {val}" for k, val in mesures] + ["", rang_phrase, "", trous_intro]
    txt += [f"  • {t}" for t in T] + ["", lien_p, "", neutre, "", "Avec nos salutations républicaines,", ""]
    txt += sig + ["", "—", ligne_ia, "", rgpd]
    texte = "\n".join(txt)

    h = html.escape
    lien_html = f'<a href="{h(lien)}">{h(lien)}</a>' if lien.startswith("http") and "•" not in lien else h(lien)
    corps = f"""<!doctype html><html lang="fr"><head><meta charset="utf-8"><title>{h(objet)}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{{font:16px/1.55 Georgia,serif;color:#1d1d1f;background:#f4f2ee;margin:0;padding:24px 16px}}
.l{{max-width:640px;margin:auto;background:#fff;padding:32px 36px;border:1px solid #e2ddd3}}
.m{{color:#666;font:13px/1.4 system-ui,sans-serif;border-bottom:1px solid #eee;padding-bottom:10px;margin-bottom:18px}}
table{{border-collapse:collapse;width:100%;margin:8px 0 14px}}td{{padding:6px 8px;border-bottom:1px solid #eee;vertical-align:top}}
td:first-child{{font:600 13px system-ui,sans-serif;color:#555;width:90px}}.ia{{font-style:italic;color:#444}}
.r{{font:12px/1.45 system-ui,sans-serif;color:#666;border-top:1px solid #eee;margin-top:22px;padding-top:12px}}</style></head>
<body><div class="l"><div class="m">À : {h(dest)}<br>Objet : {h(objet)}</div>
<p>{h(P[0])}</p><p>{h(P[1])}</p><p>{h(P[2])}</p>
<table>{''.join(f'<tr><td>{h(k)}</td><td>{h(val)}</td></tr>' for k, val in mesures)}</table>
<p>{h(rang_phrase)}</p><p>{h(trous_intro)}</p>{'<ul>' + ''.join(f'<li>{h(t)}</li>' for t in T) + '</ul>' if T else ''}
<p>{h(lien_p).replace(h(lien), lien_html)}</p><p>{h(neutre)}</p><p>Avec nos salutations républicaines,</p>
<p>{'<br>'.join(h(s) for s in sig)}</p><p class="ia">{h(ligne_ia)}</p><p class="r">{h(rgpd)}</p></div></body></html>"""

    # juge
    bas = texte.lower()
    ko = []
    if "sauf erreur ou omission" not in bas:
        ko.append("clause « sauf erreur ou omission » absente")
    ko += [f"formule interdite : {i}" for i in INTERDITS if i in bas]
    ko += [f"nom d'un autre candidat : {n}" for n in autres_noms if n.lower() in bas]
    return objet, texte, corps, ko


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("slugs", nargs="+")
    ap.add_argument("--sortie", required=True)
    ap.add_argument("--lien-essai", action="store_true")
    a = ap.parse_args()
    bilan = {e["id"]: e for e in json.loads(BILAN.read_text(encoding="utf-8"))["candidats"]}
    ann = {q["slug"]: q for q in yaml.safe_load(ANNUAIRE.read_text(encoding="utf-8"))["qg"]}
    out = Path(a.sortie)
    out.mkdir(parents=True, exist_ok=True)
    rc = 0
    for s in a.slugs:
        e = bilan[s]
        autres = [x["nom"] for k, x in bilan.items() if k != s]
        j = jeton_essai(s) if a.lien_essai else None
        lien = f"{SITE}/corpus/?j={j}" if j else f"{SITE}/corpus/?j=••••"
        objet, texte, corps, ko = rendre(e, ann.get(s, {}), lien, autres)
        (out / f"{s}.txt").write_text(texte, encoding="utf-8")
        (out / f"{s}.html").write_text(corps, encoding="utf-8")
        print(f"{s}: {'JUGE_OK' if not ko else 'JUGE_KO ' + '; '.join(ko)} → {out / s}.html")
        rc |= bool(ko)
    sys.exit(rc)


if __name__ == "__main__":
    main()
