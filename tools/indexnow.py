#!/usr/bin/env python3
"""Soumission IndexNow des URLs du site.

    tools/indexnow.py verifier    — la clé est-elle servie, et le sitemap lisible ?
    tools/indexnow.py soumettre   — pousse toutes les URLs du sitemap

IndexNow est le seul canal de soumission par API encore ouvert : Google a
supprimé son « ping » de sitemap en 2023, Bing aussi, mais Bing consomme
IndexNow — et c'est Bing qui alimente la recherche de ChatGPT. Yandex, Seznam et
Naver lisent le même flux. Google ne le lit pas : pour lui, il n'y a que la
Search Console.

Le protocole : on publie un fichier <clé>.txt à la racine du site, dont le
contenu est la clé elle-même. Le moteur va le lire pour vérifier qu'on a bien la
main sur le domaine, puis accepte la liste d'URLs. Ce n'est donc pas un secret —
c'est une preuve de possession, publique par construction, au même titre que le
BingSiteAuth.xml.
"""
import argparse
import json
import sys
import urllib.request
import xml.etree.ElementTree as ET

HOTE = "demandezleur.fr"
RACINE = f"https://{HOTE}"
SITEMAP = f"{RACINE}/sitemap.xml"
POINT_DE_DEPOT = "https://api.indexnow.org/indexnow"
NS = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}


def _lire(url: str, delai: int = 30) -> str:
    with urllib.request.urlopen(url, timeout=delai) as r:
        return r.read().decode("utf-8", errors="replace")


def urls_du_sitemap() -> list:
    racine = ET.fromstring(_lire(SITEMAP))
    urls = [e.text.strip() for e in racine.findall(".//s:loc", NS) if e.text]
    etrangeres = [u for u in urls if not u.startswith(RACINE + "/") and u != RACINE + "/"]
    if etrangeres:
        raise SystemExit(f"INDEXNOW_FAIL: le sitemap porte {len(etrangeres)} URL(s) hors du domaine")
    return urls


def cle_servie(cle: str) -> str:
    """Retourne l'emplacement de la clé si elle est servie et conforme, sinon lève."""
    emplacement = f"{RACINE}/{cle}.txt"
    contenu = _lire(emplacement).strip()
    if contenu != cle:
        raise SystemExit(f"INDEXNOW_FAIL: {emplacement} ne contient pas la cle attendue")
    return emplacement


def verifier(cle: str) -> int:
    emplacement = cle_servie(cle)
    urls = urls_du_sitemap()
    print(f"  cle servie et conforme : {emplacement}")
    print(f"  sitemap lisible : {len(urls)} URLs, toutes sur {HOTE}")
    print(f"INDEXNOW_PRET {len(urls)} URLs")
    return 0


def soumettre(cle: str) -> int:
    emplacement = cle_servie(cle)
    urls = urls_du_sitemap()
    charge = {"host": HOTE, "key": cle, "keyLocation": emplacement, "urlList": urls}
    requete = urllib.request.Request(
        POINT_DE_DEPOT,
        data=json.dumps(charge).encode("utf-8"),
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete, timeout=60) as r:
            code, corps = r.status, r.read().decode("utf-8", errors="replace")[:200]
    except urllib.error.HTTPError as e:
        code, corps = e.code, e.read().decode("utf-8", errors="replace")[:200]

    # 200 = pris en compte · 202 = accepté, clé en cours de validation.
    # 400 mauvaise requête · 403 clé refusée · 422 URLs hors du domaine · 429 trop souvent.
    explication = {
        200: "pris en compte", 202: "accepte, cle en cours de validation",
        400: "requete mal formee", 403: "cle refusee — le fichier n'est pas lisible par le moteur",
        422: "URLs hors du domaine declare", 429: "trop de soumissions rapprochees",
    }.get(code, "reponse inattendue")
    print(f"  {len(urls)} URLs soumises -> HTTP {code} ({explication})")
    if corps.strip():
        print(f"  corps : {corps}")
    if code not in (200, 202):
        print(f"INDEXNOW_FAIL: HTTP {code} — {explication}")
        return 1
    print(f"INDEXNOW_OK {len(urls)} URLs, HTTP {code}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("verbe", choices=("verifier", "soumettre"))
    ap.add_argument("--cle", required=True, help="la cle IndexNow (elle est publique)")
    a = ap.parse_args()
    return verifier(a.cle) if a.verbe == "verifier" else soumettre(a.cle)


if __name__ == "__main__":
    sys.exit(main())
