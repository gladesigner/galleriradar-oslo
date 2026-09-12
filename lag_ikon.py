"""Tegner appikonet i alle størrelsene som trengs.

Motivet: en ramme med to lerret inni, der det ene bryter ut av rammen, og en
liten prikk som gir en tredje størrelse. Fargene er hentet fra et maleri –
kobolt, oransje sol, magenta og grønt. Kjøres når ikonet skal endres:

    .venv/bin/python lag_ikon.py
"""
from PIL import Image, ImageDraw

OPPTEGNING = 4          # tegnes opp og skaleres ned, for myke kanter

PAPIR    = (247, 240, 229)
RAMME    = (78, 112, 246)
LERRET_1 = (232, 136, 52)
LERRET_2 = (214, 96, 232)
PRIKK    = (96, 196, 130)


def tegn(storrelse: int) -> Image.Image:
    K = storrelse * OPPTEGNING
    b = Image.new("RGB", (K, K), PAPIR)
    d = ImageDraw.Draw(b)
    d.rounded_rectangle([K * .20, K * .20, K * .80, K * .80], radius=K * .15,
                        fill=PAPIR, outline=RAMME, width=int(K * .048))
    d.ellipse([K * .28, K * .34, K * .56, K * .62], fill=LERRET_1)
    d.ellipse([K * .48, K * .48, K * .90, K * .90], fill=LERRET_2)   # bryter hjørnet
    d.ellipse([K * .30, K * .66, K * .41, K * .77], fill=PRIKK)
    return b.resize((storrelse, storrelse), Image.LANCZOS)


if __name__ == "__main__":
    for sti, px in [("ios/Galleriradar/Assets.xcassets/AppIcon.appiconset/ikon.png", 1024),
                    ("front/ikon-512.png", 512),
                    ("front/ikon-192.png", 192),
                    ("ikonforslag/valgt.png", 512)]:
        tegn(px).save(sti, "PNG")
        print(f"  {sti}  {px}×{px}")
