#!/usr/bin/env python3
"""Jetons par QG : clair au coffre pass (jamais ailleurs), empreinte sha256 seule dans le registre.
Usage : qg_jetons.py creer|revoquer|lister|slugs [<slug>] [--test] [--etiquette X]
Env (bancs) : QG_WEB, QG_ANNUAIRE, QG_REGISTRE, QG_PASS_BIN."""
import argparse, hashlib, json, os, secrets, subprocess, sys, time
from pathlib import Path

WEB = Path(os.environ.get("QG_WEB", str(Path.home() / "web" / "demandezleur.fr")))
ANNUAIRE = Path(os.environ.get("QG_ANNUAIRE", str(WEB / "qg" / "annuaire.yaml")))
REGISTRE = Path(os.environ.get("QG_REGISTRE", str(WEB / "backend" / "qg" / "jetons.json")))
PASS = os.environ.get("QG_PASS_BIN", "pass")


def empreinte(jeton):
    return hashlib.sha256(jeton.encode("utf-8")).hexdigest()


def slugs():
    lignes = [l for l in ANNUAIRE.read_text(encoding="utf-8").splitlines() if not l.lstrip().startswith("#")]
    return [q["slug"] for q in json.loads("\n".join(lignes))["qg"]]


def charger():
    if not REGISTRE.exists():
        return {}
    return json.loads(REGISTRE.read_text(encoding="utf-8"))


def ecrire(reg):
    REGISTRE.parent.mkdir(parents=True, exist_ok=True)
    tmp = REGISTRE.with_name(REGISTRE.name + ".tmp")
    tmp.write_text(json.dumps(reg, indent=1, sort_keys=True), encoding="utf-8")
    os.chmod(tmp, 0o640)
    os.replace(tmp, REGISTRE)


def coffre(slug, test, etiquette):
    if not test:
        return "demandezleur/qg/" + slug
    return "demandezleur/qg/_test-" + slug + ("-" + etiquette if etiquette else "")


def lire_coffre(chemin):
    r = subprocess.run([PASS, "show", chemin], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 and r.stdout.strip() else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["creer", "revoquer", "lister", "slugs"])
    ap.add_argument("slug", nargs="?")
    ap.add_argument("--test", action="store_true")
    ap.add_argument("--etiquette", default="")
    a = ap.parse_args()
    if a.action == "slugs":
        print("\n".join(slugs()))
        return 0
    reg = charger()
    if a.action == "lister":
        for h, e in sorted(reg.items(), key=lambda kv: kv[1]["slug"]):
            print(e["slug"], h[:8], e["cree"], "REVOQUE" if e.get("revoque") else "actif", "test" if e.get("test") else "")
        return 0
    if not a.slug or a.slug not in slugs():
        print("SLUG_INCONNU", a.slug)
        return 2
    chemin = coffre(a.slug, a.test, a.etiquette)
    clair = lire_coffre(chemin)
    if a.action == "creer":
        deja = clair is not None
        if not deja:
            clair = secrets.token_urlsafe(24)
            r = subprocess.run([PASS, "insert", "-e", "-f", chemin], input=clair + "\n", capture_output=True, text=True)
            if r.returncode != 0:
                print("COFFRE_KO", chemin)
                return 3
        h = empreinte(clair)
        if h not in reg:
            e = {"slug": a.slug, "cree": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "revoque": None}
            if a.test:
                e["test"] = True
            reg[h] = e
            ecrire(reg)
        print("DEJA" if deja else "CREE", a.slug, "test" if a.test else "", h[:8])
        return 0
    if clair is None or empreinte(clair) not in reg:
        print("JETON_INTROUVABLE", chemin)
        return 4
    e = reg[empreinte(clair)]
    if not e.get("revoque"):
        e["revoque"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        ecrire(reg)
    print("REVOQUE", a.slug, empreinte(clair)[:8])
    return 0


if __name__ == "__main__":
    sys.exit(main())
