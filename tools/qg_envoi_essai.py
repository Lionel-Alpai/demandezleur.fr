#!/usr/bin/env python3
"""qg_envoi_essai.py — courriers QG d'ESSAI, envoyés EN VRAI MAIL à Lionel SEUL (brique dl-qg-courrier-personnalise).

  python3 tools/qg_envoi_essai.py [<slug>…]     (défaut : nicolas-dupont-aignan fabien-roussel sylvain-durif)

- Rend chaque courrier par qg_courrier.rendre() avec le jeton d'ESSAI du coffre (pass demandezleur/qg/_test-<slug>) ;
  refuse un slug sans jeton d'essai (jamais le jeton réel d'un QG) et refuse si le juge du gabarit est KO.
- Expéditeur corpus@demandezleur.fr, sortie par le relais dabahargadon (10.0.0.9:587, DKIM d=demandezleur.fr).
- Destinataire VERROUILLÉ : lionel.denis@alpai.eu (règle zéro mail extérieur) ; objet préfixé [ESSAI QG].
"""
import json
import smtplib
import ssl
import subprocess
import sys
import time
from email.message import EmailMessage
from email.utils import formatdate, make_msgid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import qg_courrier as qc  # noqa: E402
import yaml  # noqa: E402

RELAIS = ("10.0.0.9", 587)
EXPEDITEUR = "corpus@demandezleur.fr"
DESTINATAIRE = "lionel.denis@alpai.eu"   # verrou : aucun autre destinataire possible
DEFAUT = ["nicolas-dupont-aignan", "fabien-roussel", "sylvain-durif"]


def coffre(chemin):
    r = subprocess.run(["pass", "show", chemin], capture_output=True, text=True, check=True)
    return r.stdout.splitlines()[0].strip()


def main():
    slugs = sys.argv[1:] or DEFAUT
    bilan = {e["id"]: e for e in json.loads(qc.BILAN.read_text(encoding="utf-8"))["candidats"]}
    ann = {q["slug"]: q for q in yaml.safe_load(qc.ANNUAIRE.read_text(encoding="utf-8"))["qg"]}
    msgs = []
    for s in slugs:
        j = qc.jeton_essai(s)
        if not j:
            sys.exit(f"REFUS {s} : pas de jeton d'essai au coffre (pass demandezleur/qg/_test-{s})")
        e = bilan[s]
        autres = [x["nom"] for k, x in bilan.items() if k != s]
        objet, texte, corps, ko = qc.rendre(e, ann.get(s, {}), f"{qc.SITE}/corpus/?j={j}", autres)
        if ko:
            sys.exit(f"REFUS {s} : juge du gabarit KO — {'; '.join(ko)}")
        m = EmailMessage()
        m["From"] = f"demandezleur.fr <{EXPEDITEUR}>"
        m["To"] = DESTINATAIRE
        m["Subject"] = f"[ESSAI QG {e['nom']}] {objet}"
        m["Date"] = formatdate(localtime=True)
        m["Message-ID"] = make_msgid(domain="demandezleur.fr")
        m.set_content(texte)
        m.add_alternative(corps, subtype="html")
        assert m["To"] == DESTINATAIRE
        msgs.append((s, m))
    ctx = ssl.create_default_context()
    ctx.check_hostname = False          # par IP dans le tunnel WG : le certificat porte le nom du relais
    ctx.verify_mode = ssl.CERT_NONE
    with smtplib.SMTP(*RELAIS, timeout=30) as smtp:
        smtp.starttls(context=ctx)
        smtp.login(EXPEDITEUR, coffre("relais-dabahargadon/corpus-demandezleur-smtp"))
        for s, m in msgs:
            refus = smtp.send_message(m, to_addrs=[DESTINATAIRE])
            print(f"{'ENVOYE' if not refus else 'REFUSE ' + str(refus)} {s} → {DESTINATAIRE} {m['Message-ID']}", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    main()
