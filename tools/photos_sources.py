#!/usr/bin/env python3
"""Sources photo RÉCENTES et propres pour les portraits : Wikimedia Commons (API), triées par date de prise de vue.
Pour chaque candidat : jusqu'à 6 images ≥ 600 px avec un visage détecté, recadrées autour du visage (marge),
enregistrées dans hugo-src/photos-sources/<id>/NN.jpg + provenance.json (titre, date, auteur, licence, url).
Planche par candidat (date + licence) et planche générale des sources retenues (la plus récente en tête).
Usage : /home/lionel/tools/flux2/venv/bin/python tools/photos_sources.py [--ids a,b] [--n 6]"""
import argparse, io, json, re, sys, time, urllib.error, urllib.parse, urllib.request
from pathlib import Path
import cv2, numpy as np
from PIL import Image, ImageDraw, ImageFont
R = Path(__file__).resolve().parent.parent
OUT = R / "hugo-src/photos-sources"; OUT.mkdir(exist_ok=True)
UA = {"User-Agent": "demandezleur.fr/portraits (site citoyen ; contact via le site)"}
YUNET = "/home/lionel/trio/orchestre/tools/fabrique/juge_visage/yunet.onnx"  # OpenCV 5 : plus de Haar, on prend YuNet (même détecteur que le juge)
_DET = cv2.FaceDetectorYN.create(YUNET, "", (320, 320), 0.6, 0.3, 5000)


def detecter_visages(im_rgb):
    bgr = cv2.cvtColor(np.array(im_rgb), cv2.COLOR_RGB2BGR); H, W = bgr.shape[:2]
    _DET.setInputSize((W, H)); _, faces = _DET.detect(bgr)
    return [tuple(int(v) for v in f[:4]) for f in (faces if faces is not None else [])]


def commons(q, n=25):
    p = {"action": "query", "generator": "search", "gsrsearch": q, "gsrnamespace": "6", "gsrlimit": str(n), "prop": "imageinfo",
         "iiprop": "url|size|timestamp|mime|extmetadata", "iiurlwidth": "1200", "format": "json"}
    req = urllib.request.Request("https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode(p), headers=UA)
    for attente in (0, 20, 45, 90):
        time.sleep(attente or 1.5)  # rythme poli ; sur 429, reprise avec attente croissante
        try:
            d = json.load(urllib.request.urlopen(req, timeout=40)); break
        except urllib.error.HTTPError as e:
            if e.code != 429: raise
            print(f"   429 — reprise dans {attente or 20}s", flush=True); d = None
    if d is None: return []
    out = []
    for pg in d.get("query", {}).get("pages", {}).values():
        ii = (pg.get("imageinfo") or [{}])[0]; em = ii.get("extmetadata", {})
        if not ii.get("mime", "").startswith("image/") or ii.get("width", 0) < 600: continue
        date = (em.get("DateTimeOriginal", {}).get("value") or ii.get("timestamp", ""))[:10]
        out.append({"titre": pg["title"], "w": ii["width"], "h": ii["height"], "date": date, "date_upload": ii.get("timestamp", "")[:10],
                    "licence": re.sub(r"<[^>]+>", "", em.get("LicenseShortName", {}).get("value", "")), "auteur": re.sub(r"<[^>]+>", "", em.get("Artist", {}).get("value", ""))[:60],
                    "url": ii.get("thumburl") or ii["url"], "page": ii.get("descriptionurl", "")})
    return out


def telecharger(url):
    try:
        return Image.open(io.BytesIO(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60).read())).convert("RGB")
    except Exception:
        return None


def recadrer_visage(im):
    """Plus grand visage frontal ; crop carré généreux autour (portrait buste). None si pas de visage ≥ 120 px."""
    faces = [f for f in detecter_visages(im) if f[2] >= 120 and f[3] >= 120]
    if not faces: return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    cx, cy, cote = x + w / 2, y + h * 0.55, int(max(w, h) * 2.6)
    W, H = im.size; cote = min(cote, W, H)
    g0, h0 = int(min(max(cx - cote / 2, 0), W - cote)), int(min(max(cy - cote / 2, 0), H - cote))
    return im.crop((g0, h0, g0 + cote, h0 + cote)), int(w)


def collecter(c, n):
    nom = c["nom"]; d = OUT / c["id"]; d.mkdir(exist_ok=True)
    vus, cands = set(), []
    for q in (f"filetype:bitmap {nom} 2026", f"filetype:bitmap {nom} 2025", f"filetype:bitmap {nom} 2024", f"filetype:bitmap {nom}"):
        try:
            for r in commons(q):
                if r["titre"] not in vus: vus.add(r["titre"]); cands.append(r)
        except Exception as e:
            print("   commons KO", q[:40], str(e)[:60])
    cands.sort(key=lambda r: r["date"], reverse=True)
    gardees = []
    for r in cands:
        if len(gardees) >= n: break
        im = telecharger(r["url"])
        if im is None: continue
        rc = recadrer_visage(im)
        if rc is None: continue
        crop, taille_visage = rc
        if taille_visage < 150: continue
        k = len(gardees) + 1; crop.resize((768, 768), Image.LANCZOS).save(d / f"{k:02d}.jpg", quality=92)
        gardees.append({**r, "fichier": f"{k:02d}.jpg", "visage_px": taille_visage})
        print(f"   {k}. {r['date']} {r['w']}x{r['h']} visage {taille_visage}px {r['licence']:12} {r['titre'][5:60]}")
    (d / "provenance.json").write_text(json.dumps({"candidat_id": c["id"], "choix": "01.jpg" if gardees else None, "sources": gardees}, ensure_ascii=False, indent=1), encoding="utf-8")
    return gardees


def planche(c, gardees):
    T = 300; im = Image.new("RGB", (T * max(1, len(gardees)), T + 44), "#0a1428"); dr = ImageDraw.Draw(im)
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 16); f2 = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 13)
    for k, g in enumerate(gardees):
        im.paste(Image.open(OUT / c["id"] / g["fichier"]).resize((T - 8, T - 8)), (k * T + 4, 4))
        dr.text((k * T + 8, T + 2), f"{k+1}. {g['date']}", font=f, fill="#ff5f6b"); dr.text((k * T + 8, T + 22), f"{g['licence'][:22]} · {g['w']}px", font=f2, fill="#c5cad6")
    im.save(OUT / c["id"] / "planche.jpg", quality=88)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--ids", default=""); ap.add_argument("--n", type=int, default=6); a = ap.parse_args()
    cands = json.loads((R / "hugo-src/data/candidats.json").read_text(encoding="utf-8"))
    voulus = set(a.ids.split(",")) if a.ids else None
    bilan = {}
    for c in cands:
        if voulus and c["id"] not in voulus: continue
        prov = OUT / c["id"] / "provenance.json"
        if not a.ids and prov.exists() and json.loads(prov.read_text(encoding="utf-8")).get("sources"):
            bilan[c["id"]] = json.loads(prov.read_text(encoding="utf-8"))["sources"]; print("==", c["nom"], "(déjà collecté)"); continue
        print("==", c["nom"], flush=True); g = collecter(c, a.n); bilan[c["id"]] = g
        if g: planche(c, g)
    # planche générale : la source retenue (la plus récente) par candidat
    ok = [c for c in cands if bilan.get(c["id"])]
    T = 240; cols = 6; rows = (len(ok) + cols - 1) // cols; im = Image.new("RGB", (T * cols, (T + 40) * rows), "#0a1428"); dr = ImageDraw.Draw(im)
    f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15)
    for i, c in enumerate(ok):
        g = bilan[c["id"]][0]; x, y = (i % cols) * T, (i // cols) * (T + 40)
        im.paste(Image.open(OUT / c["id"] / g["fichier"]).resize((T - 8, T - 8)), (x + 4, y + 4)); dr.text((x + 8, y + T), f"{c['nom'][:22]} · {g['date'][:4]}", font=f, fill="#f4f6fb")
    im.save(OUT / "planche_sources.jpg", quality=88)
    print("\nsans source :", [c["id"] for c in cands if not bilan.get(c["id"])], "\nplanche :", OUT / "planche_sources.jpg")
