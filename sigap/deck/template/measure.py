"""Re-derive every number in README.md from the template image itself.

    python3 measure.py [template-1920x1080.png]

Needs Pillow. Run this if the organiser ships a new template: the constants in
plot.mjs (GEO) are these measurements written down, and nothing else checks
that they still match the picture.

The method: the background is a smooth gradient, so anything that is NOT smooth
is artwork. Blur the image hard to get the background, subtract, and what is
left is the logos and the photo.
"""
import sys
from collections import deque

from PIL import Image, ImageChops, ImageFilter

SRC = sys.argv[1] if len(sys.argv) > 1 else "template-1920x1080.png"

im = Image.open(SRC).convert("RGB")
W, H = im.size
bg = im.filter(ImageFilter.GaussianBlur(radius=35))
lum = bg.convert("L")
lp = lum.load()

print(f"{SRC}  {W} x {H}")

# ---------------------------------------------------------------- artwork
ink = ImageChops.difference(im, bg).convert("L").point(lambda v: 255 if v > 28 else 0)
kp = ink.load()


def bbox(x0, y0, x1, y1, min_run=3):
    """Ink inside a window, ignoring single speckles of gradient noise."""
    xs, ys = [], []
    for y in range(y0, y1, 2):
        run = 0
        for x in range(x0, x1, 2):
            if kp[x, y]:
                run += 1
                if run >= min_run:
                    xs.append(x)
                    ys.append(y)
            else:
                run = 0
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


print("\norganiser artwork — nothing of ours may sit here")
for name, win in (("sokrates", (20, 10, 500, 220)),
                  ("hackathon", (1380, 10, 1910, 260)),
                  ("partners", (20, 860, 700, 1070)),
                  ("photo", (1380, 700, W, H))):
    b = bbox(*win)
    if b:
        print(f"  {name:10} x {b[0]:4}  y {b[1]:4}  w {b[2]-b[0]:4}  h {b[3]-b[1]:4}")

# ------------------------------------------------------------- white wedge
# Dark text needs a near-white background. 230 is the point where this
# template's lilac starts to eat 16px body text.
THRESH = 230


def right_edge(y, thresh=THRESH):
    last = 0
    for x in range(0, W, 4):
        if lp[x, y] >= thresh:
            last = x
        else:
            break
    return last


print(f"\nrightmost x that stays >= {THRESH} (white enough for dark text)")
for y in range(240, 900, 40):
    print(f"  y {y:4}   x {right_edge(y):5}")

for top, bot, label in ((240, 500, "zone A, wide"), (500, 856, "zone B, tall")):
    edge = min(right_edge(y) for y in range(top, bot, 8))
    print(f"\n{label}: y {top}..{bot} stays white to x {edge}"
          f"   ({edge - 80} wide from x=80)")

# ------------------------------------------------------------------ bands
print("\nbackground luminance, 40px rows (' ' white, '@' deep purple)")
small = lum.resize((W // 20, H // 20), Image.BOX)
sp = small.load()
for y in range(0, small.size[1], 2):
    row = "".join(
        " " if sp[x, y] >= 240 else "." if sp[x, y] >= 215
        else "+" if sp[x, y] >= 180 else "#" if sp[x, y] >= 130 else "@"
        for x in range(small.size[0]))
    print(f"  y {y*20:4}  {row}")
