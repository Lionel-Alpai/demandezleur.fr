#!/usr/bin/env python3
"""Normalise les photos des candidats en carrés 512×512 (webp q82).

- Originaux : hugo-src/photos-originales/<id>.<ext> (hors static/, jamais publiés).
- Sortie    : hugo-src/static/img/candidats/<id>.webp
- Cadrage   : point focal (x, y) en fraction de l'image, depuis data/candidats.json
              (champ photo_cadrage, défaut x=0.5, y=0.35 = visage dans le haut du carré).
              Si OpenCV est disponible, le visage détecté remplace le point focal par défaut.
- Rapport   : dimensions source, ratio, drapeau A_REMPLACER si photo_type == "affiche"
              ou si la source est plus petite que 400 px.
Usage : python3 tools/photos_normaliser.py [--taille 512] [--ids id1,id2]
"""
import argparse, json, sys
from pathlib import Path
from PIL import Image

RACINE = Path(__file__).resolve().parent.parent / "hugo-src"
ORIGINAUX = RACINE / "photos-originales"
SORTIE = RACINE / "static" / "img" / "candidats"
DATA = RACINE / "data" / "candidats.json"

try:
    import cv2  # facultatif
    CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
except Exception:
    cv2 = None; CASCADE = None


def point_focal_visage(chemin):
    if cv2 is None:
        return None
    img = cv2.imread(str(chemin))
    if img is None:
        return None
    gris = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    visages = CASCADE.detectMultiScale(gris, 1.1, 5, minSize=(40, 40))
    if len(visages) == 0:
        return None
    x, y, w, h = max(visages, key=lambda v: v[2] * v[3])
    H, W = gris.shape
    return ((x + w / 2) / W, (y + h / 2) / H)


def carre(im, fx, fy):
    W, H = im.size
    cote = min(W, H)
    # On centre le carré sur le point focal, borné dans l'image.
    cx, cy = fx * W, fy * H
    gauche = min(max(cx - cote / 2, 0), W - cote)
    haut = min(max(cy - cote / 2, 0), H - cote)
    return im.crop((int(gauche), int(haut), int(gauche + cote), int(haut + cote)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--taille", type=int, default=512)
    ap.add_argument("--ids", default="")
    a = ap.parse_args()
    cands = json.loads(DATA.read_text(encoding="utf-8"))
    voulus = set(a.ids.split(",")) if a.ids else None
    SORTIE.mkdir(parents=True, exist_ok=True)
    print(f"{'id':24} {'source':>11} {'ratio':>6}  cadrage      statut")
    for c in cands:
        cid = c["id"]
        if voulus and cid not in voulus:
            continue
        srcs = sorted(ORIGINAUX.glob(cid + ".*"))
        srcs = [s for s in srcs if s.suffix.lower() in (".webp", ".jpg", ".jpeg", ".png")]
        if not srcs:
            print(f"{cid:24} {'ABSENT':>11}"); continue
        src = srcs[0]
        im = Image.open(src).convert("RGB")
        W, H = im.size
        cad = c.get("photo_cadrage") or {}
        fx, fy = float(cad.get("x", 0.5)), float(cad.get("y", 0.35))
        methode = "json" if cad else "defaut"
        if not cad:
            pf = point_focal_visage(src)
            if pf:
                fx, fy = pf; methode = "visage"
        out = carre(im, fx, fy).resize((a.taille, a.taille), Image.LANCZOS)
        out.save(SORTIE / f"{cid}.webp", "WEBP", quality=82, method=6)
        statut = "ok"
        if c.get("photo_type") == "affiche":
            statut = "A_REMPLACER (affiche)"
        elif min(W, H) < 400:
            statut = f"A_REMPLACER (source {min(W,H)}px)"
        print(f"{cid:24} {W}x{H:<6} {W/H:6.2f}  {methode:6}{fx:.2f},{fy:.2f}  {statut}")


if __name__ == "__main__":
    main()
