#!/usr/bin/env python3
"""Portrait « plateau » SANS API (29/10/2026) : détourage u2net local + bichromie tramée bleu nuit / crème + liseré rouge,
dans la palette mesurée sur les portraits gpt-image en service. Repli quand l'API OpenAI est indisponible (crédit épuisé),
et carte « silhouette + initiales » pour un candidat sans photo libre.
Usage : /home/lionel/tools/flux2/venv/bin/python tools/portrait_local.py photo <source.jpg> <sortie_dir> <id>
        /home/lionel/tools/flux2/venv/bin/python tools/portrait_local.py initiales "<NOM>" <sortie_dir> <id>
Sortie : <id>.webp (640) + <id>-320.webp."""
import sys
from pathlib import Path
import cv2
import numpy as np
import onnxruntime as ort
from PIL import Image, ImageDraw, ImageFont

FOND = np.array([25, 33, 53], np.float32)
CREME = np.array([242, 240, 228], np.float32)
ROUGE = np.array([208, 38, 28], np.float32)
U2NET = Path.home() / ".u2net/u2net.onnx"
T = 640


def masque(rgb):
    s = ort.InferenceSession(str(U2NET), providers=["CPUExecutionProvider"])
    x = cv2.resize(rgb, (320, 320)).astype(np.float32) / 255.0
    x = (x - [0.485, 0.456, 0.406]) / [0.229, 0.224, 0.225]
    x = x.transpose(2, 0, 1)[None].astype(np.float32)
    m = s.run(None, {s.get_inputs()[0].name: x})[0][0, 0]
    m = (m - m.min()) / (m.max() - m.min() + 1e-6)
    return cv2.resize(m, (rgb.shape[1], rgb.shape[0]))


def trame(ton, periode=5.0):
    """Trame de points à 45° : un pixel est encré si le ton dépasse le seuil local de la grille."""
    h, w = ton.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    u = (xx + yy) / (periode * 1.414)
    v = (xx - yy) / (periode * 1.414)
    seuil = (np.cos(u * 2 * np.pi) + np.cos(v * 2 * np.pi) + 2) / 4  # 0..1
    return np.clip((ton - seuil) * 6 + 0.5, 0, 1)


def portrait(src, out, cid):
    rgb = cv2.cvtColor(cv2.imread(str(src)), cv2.COLOR_BGR2RGB)
    rgb = cv2.resize(rgb, (T, T), interpolation=cv2.INTER_AREA)
    m = masque(rgb)
    m = cv2.GaussianBlur(np.clip((m - 0.35) * 3, 0, 1), (5, 5), 0)
    g = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    g = cv2.createCLAHE(clipLimit=2.5, tileGridSize=(8, 8)).apply(g).astype(np.float32) / 255.0
    g = np.clip((g - 0.08) / 0.85, 0, 1) ** 1.15
    ton = 0.55 * g + 0.45 * trame(g)
    img = FOND + (CREME - FOND) * (ton * m)[..., None]
    # liseré rouge : couronne extérieure du masque, plus marquée côté droit (lumière de plateau)
    bord = np.clip(cv2.GaussianBlur(cv2.dilate(m, np.ones((9, 9), np.uint8)), (15, 15), 0) - m, 0, 1)
    cote = np.linspace(0.12, 1.0, T)[None, :] ** 1.5
    a = np.clip(bord * 1.8 * cote, 0, 1)[..., None]
    img = img * (1 - a) + ROUGE * a
    ecrire(Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)), out, cid)


def initiales(nom, out, cid):
    img = Image.new("RGB", (T, T), tuple(int(c) for c in FOND))
    d = ImageDraw.Draw(img)
    # silhouette neutre (tête + épaules) en crème tramée très sombre, initiales en crème, filet rouge
    sil = Image.new("L", (T, T), 0); ds = ImageDraw.Draw(sil)
    ds.ellipse((230, 120, 410, 320), fill=255); ds.ellipse((110, 340, 530, 760), fill=255)
    a = np.array(sil, np.float32) / 255.0 * 0.16
    arr = np.array(img, np.float32) * (1 - a[..., None]) + CREME * a[..., None]
    img = Image.fromarray(arr.astype(np.uint8)); d = ImageDraw.Draw(img)
    ini = "".join(p[0] for p in nom.replace("-", " ").split()[:2]).upper()
    try:
        f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 150)
    except OSError:
        f = ImageFont.load_default()
    bb = d.textbbox((0, 0), ini, font=f)
    d.text(((T - (bb[2] - bb[0])) / 2 - bb[0], 440 - bb[1]), ini, font=f, fill=tuple(int(c) for c in CREME))
    d.rectangle((0, T - 10, T, T), fill=tuple(int(c) for c in ROUGE))
    ecrire(img, out, cid)


def ecrire(img, out, cid):
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    img.save(out / f"{cid}.webp", "WEBP", quality=84)
    img.resize((320, 320), Image.LANCZOS).save(out / f"{cid}-320.webp", "WEBP", quality=84)
    print("PORTRAIT_LOCAL_OK", out / f"{cid}.webp")


if __name__ == "__main__":
    mode, a, out, cid = sys.argv[1:5]
    (portrait if mode == "photo" else initiales)(a, out, cid)
