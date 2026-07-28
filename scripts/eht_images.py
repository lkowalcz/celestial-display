#!/usr/bin/env python3
"""Turn the published Event Horizon Telescope reconstructions into small
grayscale intensity maps for the black-hole scene.

The EHT has imaged exactly two black holes at horizon scale: M87* (observed
April 2017, published 2019) and Sgr A* (same campaign, published 2022). The
public GitHub releases from the collaboration are calibrated *visibilities*
(uvfits), not images, and the fiducial image FITS live behind
eventhorizontelescope.org / CyVerse. What is reliably fetchable is the
released image itself, via the ESO archive under CC BY 4.0:

  M87*   eso1907a          "First Image of a Black Hole"
  Sgr A* eso2208-eht-mwa   "First image of our black hole"

Those are published as RGB renderings in the EHT's standard `afmhot`
colormap. afmhot is piecewise-linear and injective,

    R = clip(2x, 0, 1)    G = clip(2x - 0.5, 0, 1)    B = clip(2x - 1, 0, 1)

so the display mapping inverts exactly, channel by channel, recovering the
relative intensity that was plotted. Two honest caveats, both stated in the
scene caption's provenance and worth repeating here:

  * this recovers the *released image's* relative intensity, not calibrated
    photometry — press renderings carry their own stretch and a soft halo,
    and JPEG quantization costs the bottom few percent;
  * the pixel scale is not read from a FITS header (there isn't one). It is
    set by measuring the azimuthally-averaged brightness peak and declaring
    its diameter to equal the published ring diameter (42.0 μas for M87*,
    51.8 μas for Sgr A*). Everything downstream is therefore anchored to the
    published ring size, which is the number we actually want the display to
    be honest about.

Both maps are emitted over the same 100 μas field so the scene can show them
at a common angular scale, and next to a ray-trace using the same scale.

Usage:  python3 scripts/eht_images.py [id ...]     (default: all)

Requires: Pillow, numpy  (pip install Pillow numpy)
"""

import io
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

Image.MAX_IMAGE_PIXELS = None

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "eht"
UA = "celestial-display/1.0 (offline preprocessing; +https://github.com/)"

OUT_PX = 160          # emitted map size
FOV_UAS = 100.0       # emitted field of view, both sources

# Physical parameters. Masses and distances are the values the EHT papers
# adopt, kept here so the runtime can derive the gravitational angular scale
# θ_g = GM/(c²D) itself rather than trusting a hardcoded number.
SOURCES = {
    "m87": dict(
        name="M87*",
        eso="eso1907a",
        # EHT Collaboration 2019, ApJL 875, L1 / L6
        ring_diameter_uas=42.0,
        ring_diameter_err_uas=3.0,
        mass_msun=6.5e9,
        mass_err_msun=0.7e9,
        distance_m=16.8 * 3.0856775814913673e22,   # 16.8 Mpc
        distance_label="16.8 Mpc",
        # jet axis ~17° from the line of sight; approaching side is south,
        # which is why the released image is brightest at the bottom
        inclination_deg=17.0,
        pa_deg=198.0,
        epoch="2017-04-11",
        published=2019,
        credit="EHT Collaboration (ESO/eso1907a, CC BY 4.0)",
    ),
    "sgra": dict(
        name="Sgr A*",
        eso="eso2208-eht-mwa",
        # EHT Collaboration 2022, ApJL 930, L12 / L14
        ring_diameter_uas=51.8,
        ring_diameter_err_uas=2.3,
        # GRAVITY priors adopted by the EHT Sgr A* papers
        mass_msun=4.14e6,
        mass_err_msun=0.14e6,
        distance_m=8.127e3 * 3.0856775814913673e16,  # 8.127 kpc
        distance_label="8.127 kpc",
        # image-domain modelling favors a face-on-ish flow, i ≲ 30°
        inclination_deg=30.0,
        pa_deg=150.0,
        epoch="2017-04-07",
        published=2022,
        credit="EHT Collaboration (ESO/eso2208-eht-mwa, CC BY 4.0)",
    ),
}

# nominal EHT resolution at 230 GHz; both releases are restored at ~this scale
BEAM_FWHM_UAS = 20.0


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def unmap_afmhot(rgb):
    """Invert the afmhot display mapping channel by channel.

    Each channel saturates in turn (R at x=0.5, G at x=0.75), so the highest
    channel that is *not* yet clipped carries the intensity. Reading them in
    that order is exact and shrugs off JPEG noise in the clipped channels."""
    r, g, b = rgb[..., 0] / 255.0, rgb[..., 1] / 255.0, rgb[..., 2] / 255.0
    x = 0.5 * r
    x = np.where(r >= 0.99, 0.25 + 0.5 * g, x)
    x = np.where((r >= 0.99) & (g >= 0.99), 0.5 + 0.5 * b, x)
    return np.clip(x, 0.0, 1.0)


def ring_center(I):
    """Find the ring center by maximizing radial symmetry.

    A centroid is the obvious thing and the wrong thing: both released images
    are strongly asymmetric rings (that asymmetry is the physics), so the
    centroid sits well off center, on the bright side. Instead, search for the
    center that makes the azimuthally-averaged profile peak hardest — a ring
    smears into a plateau when you average it about the wrong point, and
    sharpens to its true contrast about the right one. Coarse-to-fine on a
    downsampled copy, which is all the precision the scale calibration needs."""
    h, w = I.shape
    step = max(1, int(round(max(h, w) / 512)))
    S = I[::step, ::step]
    sh, sw = S.shape

    # seed on the centroid of everything above a quarter peak: biased, but
    # comfortably inside the basin the search needs to start in
    wgt = np.maximum(S - 0.25 * S.max(), 0.0)
    yy, xx = np.mgrid[0:sh, 0:sw].astype(np.float32)
    cx = float((wgt * xx).sum() / wgt.sum())
    cy = float((wgt * yy).sum() / wgt.sum())

    # a fixed averaging radius keeps the score comparable between candidates
    rfix = min(sh, sw) * 0.30

    def contrast(px, py):
        """Ring brightness minus central brightness. Maximizing the ring peak
        alone would happily center on a hot spot; demanding a *dark middle*
        is what actually locates the shadow."""
        prof, _ = radial_profile(S, px, py, nb=160, rmax=rfix)
        return float(prof.max() - prof[:6].mean())

    span = min(sh, sw) * 0.16
    while span > 0.4:
        best = (contrast(cx, cy), cx, cy)
        for dy in (-span, 0.0, span):
            for dx in (-span, 0.0, span):
                px, py = cx + dx, cy + dy
                if not (span < px < sw - span and span < py < sh - span):
                    continue
                v = contrast(px, py)
                if v > best[0]:
                    best = (v, px, py)
        _, cx, cy = best
        span *= 0.5
    return cx * step + (step - 1) / 2.0, cy * step + (step - 1) / 2.0


def gaussian_blur(a, sigma):
    """Separable Gaussian, edge-clamped. Small enough kernel that doing it by
    hand beats pulling in scipy for one call."""
    rad = max(1, int(round(3 * sigma)))
    k = np.exp(-0.5 * (np.arange(-rad, rad + 1) / sigma) ** 2)
    k /= k.sum()
    out = a
    for axis in (0, 1):
        pad = [(0, 0), (0, 0)]
        pad[axis] = (rad, rad)
        p = np.pad(out, pad, mode="edge")
        acc = np.zeros_like(out)
        for i, wgt in enumerate(k):
            sl = [slice(None), slice(None)]
            sl[axis] = slice(i, i + out.shape[axis])
            acc += wgt * p[tuple(sl)]
        out = acc
    return out


def radial_profile(I, cx, cy, nb=500, rmax=None):
    h, w = I.shape
    yy, xx = np.mgrid[0:h, 0:w]
    rr = np.hypot(xx - cx, yy - cy)
    if rmax is None:
        rmax = float(min(cx, cy, w - cx, h - cy))
    idx = np.clip((rr / rmax * nb).astype(np.int32), 0, nb - 1).ravel()
    tot = np.bincount(idx, I.ravel(), nb)
    cnt = np.maximum(np.bincount(idx, None, nb), 1)
    return tot / cnt, rmax


def build(sid):
    s = SOURCES[sid]
    url = f"https://cdn.eso.org/images/large/{s['eso']}.jpg"
    print(f"{s['name']}: fetching {url}")
    raw = fetch(url)

    a = np.asarray(Image.open(io.BytesIO(raw)).convert("RGB"), dtype=np.float32)
    I = unmap_afmhot(a)

    cx, cy = ring_center(I)
    # measure the ring inside a window a little larger than the ring itself,
    # so the extended press halo can't drag the peak outward
    rmax = min(cx, cy, a.shape[1] - cx, a.shape[0] - cy) * 0.55
    prof, rmax = radial_profile(I, cx, cy, nb=400, rmax=rmax)
    k = int(np.argmax(prof))
    ring_px = (k + 0.5) / len(prof) * rmax

    # anchor the pixel scale to the published ring diameter
    uas_per_px = (s["ring_diameter_uas"] / 2.0) / ring_px
    print(f"  center ({cx:.1f}, {cy:.1f})  ring radius {ring_px:.1f} px"
          f"  → {uas_per_px:.5f} μas/px")

    half_px = (FOV_UAS / 2.0) / uas_per_px
    if min(cx, cy, a.shape[1] - cx, a.shape[0] - cy) < half_px:
        print(f"  warning: {FOV_UAS} μas field runs off the source image; "
              f"edges will be padded with the background level")

    # resample the requested field with bilinear sampling on a regular grid
    u = (np.arange(OUT_PX) + 0.5) / OUT_PX * 2.0 - 1.0      # [-1, 1)
    gx = cx + u[None, :] * half_px
    gy = cy + u[:, None] * half_px
    h, w = I.shape
    x0 = np.clip(np.floor(gx).astype(np.int32), 0, w - 1)
    y0 = np.clip(np.floor(gy).astype(np.int32), 0, h - 1)
    x1 = np.clip(x0 + 1, 0, w - 1)
    y1 = np.clip(y0 + 1, 0, h - 1)
    fx = np.clip(gx - x0, 0, 1)
    fy = np.clip(gy - y0, 0, 1)
    out = (I[y0, x0] * (1 - fx) * (1 - fy) + I[y0, x1] * fx * (1 - fy)
           + I[y1, x0] * (1 - fx) * fy + I[y1, x1] * fx * fy)

    # JPEG chroma subsampling speckles the region where R is clipped and the
    # intensity is being read out of G, so smooth by σ = 1.2 output px. That
    # is 0.75 μas against a 20 μas beam — a 27× margin, well inside the noise
    # and nowhere near able to touch resolved structure.
    out = gaussian_blur(out, 1.2)

    # remove the flat pedestal the press render sits on (estimated from the
    # source image's corners, well outside any real emission), then normalize
    corner = float(np.median([I[:40, :40], I[:40, -40:],
                              I[-40:, :40], I[-40:, -40:]]))
    out = np.clip(out - corner, 0.0, None)
    out /= max(out.max(), 1e-9)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    png = OUT_DIR / f"{sid}.png"
    Image.fromarray(np.round(out * 255).astype(np.uint8), "L").save(png,
                                                                    optimize=True)
    print(f"  wrote {png.relative_to(OUT_DIR.parent.parent)} "
          f"({png.stat().st_size} bytes)")

    G_C2 = 1.4766250382e3           # GM_sun/c² in metres
    theta_g = (s["mass_msun"] * G_C2 / s["distance_m"]) * (180 / np.pi) * 3.6e9
    return dict(
        id=sid, name=s["name"], px=OUT_PX, fov_uas=FOV_UAS,
        ring_diameter_uas=s["ring_diameter_uas"],
        ring_diameter_err_uas=s["ring_diameter_err_uas"],
        beam_fwhm_uas=BEAM_FWHM_UAS,
        theta_g_uas=round(float(theta_g), 4),
        mass_msun=s["mass_msun"], mass_err_msun=s["mass_err_msun"],
        distance_label=s["distance_label"],
        inclination_deg=s["inclination_deg"], pa_deg=s["pa_deg"],
        epoch=s["epoch"], published=s["published"], credit=s["credit"],
        pedestal=round(corner, 5), uas_per_px_src=round(float(uas_per_px), 6),
    )


def main():
    want = sys.argv[1:] or list(SOURCES)
    bad = [k for k in want if k not in SOURCES]
    if bad:
        sys.exit(f"unknown source(s): {', '.join(bad)}")

    meta = {}
    index = OUT_DIR / "eht.json"
    if index.exists():
        meta = {m["id"]: m for m in json.loads(index.read_text())["sources"]}
    for sid in want:
        meta[sid] = build(sid)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    index.write_text(json.dumps({
        "note": ("Relative intensity recovered by inverting the afmhot "
                 "display mapping of the published EHT images; pixel scale "
                 "anchored to the published ring diameter. See "
                 "scripts/eht_images.py for the exact procedure and caveats."),
        "sources": [meta[k] for k in SOURCES if k in meta],
    }, indent=2) + "\n")
    print(f"wrote {index.relative_to(OUT_DIR.parent.parent)}")


if __name__ == "__main__":
    main()
