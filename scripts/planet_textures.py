#!/usr/bin/env python3
"""Fetch and downsample real planetary surface/cloud maps into data/planets/.

Each entry is an equirectangular (simple cylindrical) global map from a NASA
mission mosaic, resampled to 2048x1024 JPEG (~1.5 MB total for all planets).
The runtime samples these per-pixel to shade an orthographic sphere, so what
matters is the projection and the longitude convention, recorded here per map
and encoded in the scene's PLANETS table in index.html.

Usage:  python3 scripts/planet_textures.py [name ...]   (default: all)

Requires: Pillow  (pip install Pillow)
"""

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "planets"
OUT_W, OUT_H = 3600, 1800
JPEG_QUALITY = 82

# Longitude conventions, verified against the gridded companion releases
# (e.g. PIA07782_fig1: Jupiter left edge = 180, decreasing eastward on the
# image, i.e. System III *west* longitude; map x-fraction u = (180 - lon)/360
# mod 1). The scene encodes each map's "lonLeft/lonDir" so the central-
# meridian caption stays honest.
MAPS = {
    # Cassini ISS narrow-angle global color map, Dec 11-12 2000 flyby.
    # PIA07782, NASA/JPL/Space Science Institute. 3601x1801, 0.1 deg/px,
    # planetocentric latitude, System III west longitude, 180 at left edge.
    # Poles (unseen by Cassini at low emission angle) are filled neutral gray.
    "jupiter": {
        "url": "https://assets.science.nasa.gov/content/dam/science/psd/"
               "photojournal/pia/pia07/pia07782/PIA07782.jpg",
        "credit": "NASA/JPL/Space Science Institute (Cassini ISS, PIA07782)",
        # 3601x1801 includes a duplicated wrap column/row (inclusive 0.1 deg
        # grid): drop the last column and row before resampling.
        "crop_dupe_edge": True,
    },
}


def fetch(url: str) -> Image.Image:
    req = urllib.request.Request(url, headers={"User-Agent": "celestial-display/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def build(name: str) -> None:
    spec = MAPS[name]
    print(f"{name}: fetching {spec['url']}")
    img = fetch(spec["url"])
    if spec.get("crop_dupe_edge"):
        img = img.crop((0, 0, img.width - 1, img.height - 1))
    img = img.resize((OUT_W, OUT_H), Image.LANCZOS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{name}.jpg"
    img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    print(f"{name}: wrote {out} ({out.stat().st_size / 1024:.0f} KB)  "
          f"credit: {spec['credit']}")


if __name__ == "__main__":
    names = sys.argv[1:] or list(MAPS)
    for n in names:
        build(n)
