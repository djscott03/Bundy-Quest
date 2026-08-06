#!/usr/bin/env python3
"""
Bake the Bundy photos into bundyquest.html.

    photos/bundies/   -> ally slots b1..bN   (filename = that Bundy's name)
    photos/villains/  -> boss slots x1..xN   (filename = that villain's name)

Repeat photos of the same person -- "Scoot.jpeg", "Scoot (2).jpeg", ... -- become
selectable LOOKS for that one Bundy rather than separate roster slots.  PREFERRED
picks which look is equipped by default; the rest are cycled with the blue chip
on the character-select card.

Cropping and resizing go through `sips`, so this needs no third-party packages.

    python3 embed.py
"""
import base64, json, os, re, shutil, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
HTML = os.path.join(HERE, "bundyquest.html")
SIZE = 200          # baked head size in px
QUALITY = 80

# Roster order.  Ally slots are b1.. in this order; villains are x1.. in this
# order, so the last entry is the final boss.
ALLY_ORDER = ["Berner", "Chip", "Decoursey", "Diaz", "Hendo", "Howe",
              "Johnson", "Kerin", "Pancake", "Scoot", "Todje", "Wraithel"]

# Which look is equipped by default when someone has more than one photo.
PREFERRED = {"Scoot": "Scoot (3)", "Diaz": "Diaz",
             "Johnson": "Johnson (2)", "Todje": "Todje"}

# (filename stem, display name).  Difficulty ramps down the list; Spinz closes it.
VILLAIN_ORDER = [
    ("Muniz' Dog",       "MUNIZ' DOG"),
    ("Lambert",          "LAMBERT"),
    ("Jacobs",           "JACOBS"),
    ("Tran the Trannie", "TRAN"),
    ("Lomsdale",         "LOMSDALE"),
    ("Sabado",           "SABADO"),
    ("Spinz 1.5",        "SPINZ 1.5"),
    ("Spinz",            "SPINZ"),
]

EXT = (".jpg", ".jpeg", ".png", ".heic", ".heif", ".webp")
BASE = re.compile(r"\s*\(\d+\)$")          # "Scoot (2)" -> "Scoot"


def stems(sub):
    """{stem: path} for every image in photos/<sub>."""
    d = os.path.join(HERE, "photos", sub)
    out = {}
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.lower().endswith(EXT) and not f.startswith("."):
                out[os.path.splitext(f)[0]] = os.path.join(d, f)
    return out


def dims(path):
    r = subprocess.run(["sips", "-g", "pixelWidth", "-g", "pixelHeight", path],
                       check=True, capture_output=True, text=True)
    w = h = 0
    for line in r.stdout.splitlines():
        if "pixelWidth:" in line:
            w = int(line.split(":")[1])
        elif "pixelHeight:" in line:
            h = int(line.split(":")[1])
    return w, h


# Per-photo crop tuning, keyed by filename stem: (x, y, zoom).
# x/y are where the square sits in the leftover space (0 = hard left/top,
# 1 = hard right/bottom); zoom is a fraction of the short edge.  Only listed
# here when the generic rule below framed someone badly.
CROP = {
    "Berner":    (0.50, 0.58, 1.00),   # face fills the frame; needs the chin back
    "Chip":      (0.50, 0.82, 1.00),   # tall chef hat pushes the face right down
    "Decoursey": (0.50, 0.46, 1.00),
    "Hendo":     (0.62, 0.34, 0.62),   # distant group shot — zoom right in
    "Kerin":     (0.52, 0.30, 0.58),   # ditto
    "Scoot":     (0.50, 0.52, 1.00),
    "Scoot (2)": (0.50, 0.50, 1.00),
    "Scoot (3)": (0.50, 0.80, 1.00),   # wide boonie brim
    "Todje":     (0.50, 0.46, 1.00),
    "Wraithel":  (0.58, 0.64, 1.00),   # all that hair sits above the face
    "Lambert":   (0.50, 0.56, 1.00),
    "Sabado":    (0.50, 0.42, 1.00),
    "Spinz":     (0.50, 0.44, 1.00),
}


def face_box(w, h, stem=""):
    """Square crop aimed at the face. Faces sit a little above centre, so the
    default window rides high — but nowhere near as high as a naive top crop."""
    xf, yf, z = CROP.get(stem, (0.50, 0.30 if h > w * 1.15 else 0.32, 0.95))
    side = min(w, h) * z
    sx = max(0, min(w - side, (w - side) * xf))
    sy = max(0, min(h - side, (h - side) * yf))
    return int(round(sx)), int(round(sy)), int(round(side))


def data_url(path):
    stem = os.path.splitext(os.path.basename(path))[0]
    tmp = tempfile.mktemp(suffix=".jpg")
    subprocess.run(["sips", "-s", "format", "jpeg", path, "--out", tmp],
                   check=True, capture_output=True)
    w, h = dims(tmp)
    sx, sy, side = face_box(w, h, stem)
    subprocess.run(["sips", "-c", str(side), str(side), "--cropOffset", str(sy), str(sx), tmp],
                   check=True, capture_output=True)
    subprocess.run(["sips", "-Z", str(SIZE), tmp], check=True, capture_output=True)
    subprocess.run(["sips", "-s", "formatOptions", str(QUALITY), tmp],
                   check=True, capture_output=True)
    with open(tmp, "rb") as f:
        raw = f.read()
    os.remove(tmp)
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode()


def main():
    allies, villains = stems("bundies"), stems("villains")

    # group ally photos by person, preferred look first
    groups = {}
    for stem, path in allies.items():
        groups.setdefault(BASE.sub("", stem), []).append((stem, path))
    for person, items in groups.items():
        pref = PREFERRED.get(person)
        items.sort(key=lambda sp: (sp[0] != pref, sp[0]))

    order = ALLY_ORDER + [p for p in sorted(groups) if p not in ALLY_ORDER]
    order = [p for p in order if p in groups]

    baked, bnames = {}, {}
    for i, person in enumerate(order):
        k = "b%d" % (i + 1)
        bnames[k] = person.upper()
        baked[k] = [data_url(p) for _, p in groups[person]]
        looks = " + %d more look(s)" % (len(baked[k]) - 1) if len(baked[k]) > 1 else ""
        print("  %-4s %-12s %s%s" % (k, person, os.path.basename(groups[person][0][1]), looks))

    vorder = [(s, n) for s, n in VILLAIN_ORDER if s in villains]
    vorder += [(s, s.upper()) for s in sorted(villains) if s not in dict(VILLAIN_ORDER)]
    for i, (stem, disp) in enumerate(vorder):
        k = "x%d" % (i + 1)
        bnames[k] = disp
        baked[k] = [data_url(villains[stem])]
        print("  %-4s %-12s %s%s" % (k, disp, os.path.basename(villains[stem]),
                                     "   <- FINAL BOSS" if i == len(vorder) - 1 else ""))

    if not baked:
        print("No images found under photos/. Nothing to do.")
        return 1

    with open(HTML, encoding="utf-8") as f:
        html = f.read()

    for name, obj in (("BAKED", baked), ("BAKED_NAMES", bnames)):
        blob = "const %s=%s;" % (name, json.dumps(obj, separators=(",", ":")))
        html, n = re.subn(r"const %s=\{.*?\};" % name, lambda _: blob, html, count=1, flags=re.S)
        if not n:
            print("Could not find the %s={} marker in bundyquest.html" % name, file=sys.stderr)
            return 1

    # keep the slot counts in step with what actually got baked
    html, n = re.subn(r"const ALLY_N=\d+, BOSS_N=\d+,",
                      "const ALLY_N=%d, BOSS_N=%d," % (len(order), len(vorder)), html, count=1)
    if not n:
        print("Could not find the ALLY_N/BOSS_N line", file=sys.stderr)
        return 1

    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)

    print("\n%d Bundyz (%d looks) and %d villains baked in. bundyquest.html is now %.0f KB."
          % (len(order), sum(len(v) for k, v in baked.items() if k[0] == "b"),
             len(vorder), os.path.getsize(HTML) / 1024))
    print("Photos previously imported on a device still win — use RESET PHOTOS in the roster to see these.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
