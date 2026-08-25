#!/usr/bin/env python3
"""Image Open Graph 1200×630 → hugo-src/static/img/og.png (PIL, police Inter si disponible sinon DejaVu)."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
R = Path(__file__).resolve().parent.parent
OUT = R / "hugo-src/static/img/og.png"
def police(taille, gras=True):
    for c in ["/usr/share/fonts/truetype/inter/Inter-Bold.ttf" if gras else "/usr/share/fonts/truetype/inter/Inter-Regular.ttf",
              "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if gras else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]:
        if Path(c).exists(): return ImageFont.truetype(c, taille)
    return ImageFont.load_default()
im = Image.new("RGB", (1200, 630), "#0a1428"); d = ImageDraw.Draw(im)
d.rectangle([0, 0, 1200, 12], fill="#e53946")
d.text((72, 80), "demandezleur.fr", font=police(40), fill="#f4f6fb"); d.text((72 + d.textlength("demandezleur", font=police(40)), 80), "", font=police(40))
d.text((72, 170), "Vous êtes dans le fauteuil", font=police(64), fill="#f4f6fb")
d.text((72, 250), "du journaliste.", font=police(64), fill="#f4f6fb")
d.text((72, 360), "Interrogez les programmes officiels des candidats à la", font=police(28, False), fill="#c5cad6")
d.text((72, 398), "présidentielle 2027, puis faites-les débattre entre eux.", font=police(28, False), fill="#c5cad6")
d.text((72, 540), "Programmes officiels · réponses sourcées · prompts publics · code ouvert · aucun traceur", font=police(22, False), fill="#ff5f6b")
OUT.parent.mkdir(parents=True, exist_ok=True); im.save(OUT, optimize=True); print("og.png", im.size, OUT.stat().st_size // 1024, "Ko")
