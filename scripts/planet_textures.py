#!/usr/bin/env python3
"""Fetch and downsample real planetary surface/cloud maps into data/planets/.

Each entry is an equirectangular (simple cylindrical) global map from a real
mission mosaic, resampled to a display-friendly JPEG. The runtime samples
these per-pixel to shade an orthographic sphere, so what matters is the
projection and the longitude convention — recorded here per map and encoded
in the scene's planetMaps registry in index.html (lonLeft/texDir, expressed
in the same longitude convention as the engine's Horizons-calibrated
central-meridian for that planet).

Usage:  python3 scripts/planet_textures.py [name ...]   (default: all)

Requires: Pillow  (pip install Pillow)
"""

import io
import sys
import urllib.request
from pathlib import Path

from PIL import Image

# The full USGS mosaics are legitimately huge (Mars MDIM is 228 Mpx).
Image.MAX_IMAGE_PIXELS = 600_000_000

OUT_DIR = Path(__file__).resolve().parent.parent / "data" / "planets"
JPEG_QUALITY = 82


def fill_polar_gap(img, edge_lat, north):
    """OPAL Hubble maps can't see the pole tilted away from Earth; the gap
    is black, with mosaic artifacts near the data edge. Replace everything
    poleward of edge_lat with the mean color at edge_lat, blended over ~4°,
    so the (barely visible, Earth-averted) pole doesn't render as a hole.
    Captioned as an HST map; the filled cap is unobservable from Earth."""
    px = img.load()
    w, h = img.size
    row_of = lambda lat: min(h - 1, max(0, int((90 - lat) / 180 * h)))
    edge_row = row_of(edge_lat)
    mean = [0, 0, 0]
    for x in range(w):
        c = px[x, edge_row]
        for k in range(3):
            mean[k] += c[k]
    mean = tuple(v // w for v in mean)
    blend_rows = max(1, int(4 / 180 * h))
    for y in range(h):
        lat_dir = y <= edge_row if north else y >= edge_row
        if not lat_dir:
            continue
        f = min(1.0, abs(edge_row - y) / blend_rows)
        if f <= 0:
            continue
        for x in range(w):
            c = px[x, y]
            px[x, y] = tuple(int(c[k] + (mean[k] - c[k]) * f) for k in range(3))
    return img


def tint_to_mean(img, target):
    """Scale channels so the image mean matches a target RGB. The OPAL
    color composites are narrowband-filter renderings with arbitrary
    scaling; this anchors each map's disk-average to the published
    true-color values (Irwin et al. 2024, MNRAS 527: Uranus and Neptune
    are both pale greenish-blue, Neptune slightly bluer — the familiar
    deep-blue Neptune is a Voyager-era processing artifact)."""
    px = img.load()
    w, h = img.size
    lum = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
    step = max(1, w // 400)
    tot, n = 0.0, 0
    for y in range(0, h, step):
        for x in range(0, w, step):
            tot += lum(px[x, y])
            n += 1
    mean_l = max(1.0, tot / n)
    # luminance carries the (real) structure; chromaticity comes from the
    # true-color target, plus a muted 35% of the original narrowband tint
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            l = lum(c)
            f = l / mean_l
            px[x, y] = tuple(min(255, max(0,
                int(target[k] * f + 0.35 * (c[k] - l)))) for k in range(3))
    return img


def fill_lat_band(img, lat_top, lat_bot):
    """Replace a latitude band with a per-column linear blend between its
    bounding rows. Used to remove illumination artifacts (e.g. the ring
    shadow baked into the 2011 Cassini Saturn map) — the shadow is a
    property of that day's lighting, not of the atmosphere."""
    px = img.load()
    w, h = img.size
    row_of = lambda lat: min(h - 1, max(0, int((90 - lat) / 180 * h)))
    r0, r1 = row_of(lat_top), row_of(lat_bot)

    # horizontally smooth the two boundary rows first, so per-column
    # interpolation doesn't drag column noise into vertical streaks
    def smoothed_row(r, win=61):
        row = [px[x, r] for x in range(w)]
        out = []
        half = win // 2
        for x in range(w):
            acc = [0, 0, 0]
            for dx in range(-half, half + 1):
                c = row[(x + dx) % w]
                for k in range(3):
                    acc[k] += c[k]
            out.append(tuple(v // win for v in acc))
        return out

    row0, row1 = smoothed_row(r0), smoothed_row(r1)
    for x in range(w):
        c0, c1 = row0[x], row1[x]
        for y in range(r0 + 1, r1):
            f = (y - r0) / (r1 - r0)
            px[x, y] = tuple(int(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
    return img


def fill_black_south(img, start_lat):
    """New Horizons could not see Pluto's south (seasonal darkness): the
    map is black below ~-53 deg with ragged black bites from ~-30 deg.
    Southward of start_lat, replace near-black pixels with the row mean of
    the remaining real data (carrying the last filled color once a row is
    fully unmapped). Latitudinal gradient survives; no fake detail."""
    px = img.load()
    w, h = img.size
    r0 = min(h - 1, max(0, int((90 - start_lat) / 180 * h)))
    lum = lambda c: 0.299 * c[0] + 0.587 * c[1] + 0.114 * c[2]
    carry = None
    for y in range(r0, h):
        bright = [px[x, y] for x in range(w) if lum(px[x, y]) > 14]
        if bright:
            n = len(bright)
            carry = tuple(sum(c[k] for c in bright) // n for k in range(3))
        if carry is None:
            continue
        for x in range(w):
            if lum(px[x, y]) <= 14:
                px[x, y] = carry
    return img


MAPS = {
    # New Horizons Ralph/MVIC enhanced-color global mosaic of Pluto (July
    # 2015 flyby; blue/red/NIR filters — enhanced, not visual color).
    # Equirectangular, left edge 0 deg longitude, east-positive increasing
    # rightward, Sputnik Planitia (175 deg E) at map center — verified by
    # landmark. The encounter hemisphere is sharp; the far side is low-res
    # approach imagery; south of ~-30..-53 deg was in seasonal darkness
    # (unmapped black) and is filled with row means of the real data.
    "pluto": {
        "url": "https://assets.science.nasa.gov/content/dam/science/psd/"
               "solar/2023/09/p/l/pluto_color_mapmosaic.jpg",
        "credit": "NASA/JHUAPL/SwRI (New Horizons MVIC global color "
                  "mosaic, enhanced color)",
        "size": (3600, 1800),
        "post": lambda im: fill_black_south(im, -25),
    },

    # Cassini ISS narrow-angle global color map, Dec 11-12 2000 flyby.
    # PIA07782, NASA/JPL/Space Science Institute. 3601x1801, 0.1 deg/px,
    # planetocentric latitude, System III west longitude, 180 at left edge
    # (verified via the gridded companion figure PIA07782_fig1).
    # Poles (unseen by Cassini at low emission angle) filled neutral gray.
    "jupiter": {
        "url": "https://assets.science.nasa.gov/content/dam/science/psd/"
               "photojournal/pia/pia07/pia07782/PIA07782.jpg",
        "credit": "NASA/JPL/Space Science Institute (Cassini ISS, PIA07782)",
        "size": (3600, 1800),
        # 3601x1801 includes a duplicated wrap column/row (inclusive 0.1 deg
        # grid): drop the last column and row before resampling.
        "crop_dupe_edge": True,
    },

    # Viking Orbiter MDIM 2.1 colorized global mosaic (real Viking VIS
    # imagery, NASA Ames colorization, MOLA-controlled). USGS Astrogeology,
    # official 1 km/px JPEG rendition of the 232 m product. Equirectangular,
    # planetocentric latitude, east-positive longitude centered on 0 deg E
    # (verified: Olympus Mons lands at 226 deg E, Hellas at ~70 deg E).
    "mars": {
        "url": "https://astrogeology.usgs.gov/ckan/dataset/"
               "7131d503-cdc9-45a5-8f83-5126c0fd397e/resource/"
               "5ea881c6-01b3-41fa-a7af-42d2131b54f1/download/"
               "mars_viking_mdim21_clrmosaic_1km.jpg",
        "local": "mars_full.jpg",
        "credit": "NASA/JPL/USGS (Viking MDIM 2.1 colorized mosaic)",
        "size": (3600, 1800),
    },

    # Cassini ISS global color map of Saturn, 2011-08-11 (one rotation,
    # 15 WAC frames), 0.1 deg/px. PDS4 bundle "Cassini ISS Global Maps"
    # (Li et al. 2023), PDS Atmospheres Node; contrast-enhanced RGB
    # variant. System III WEST longitude, 360 at the left edge. The
    # archive distributes FITS; converted locally to PNG before this
    # script runs (see "local"). Cloud data spans ~±78 deg latitude —
    # poleward of ±76 is filled with the data-edge mean. The near-black
    # band at ~+4..-18 deg is the 2011 ring shadow — an illumination
    # artifact of that day, not atmosphere — interpolated across.
    "saturn": {
        "url": "https://atmos.nmsu.edu/PDS/data/PDS4/co_iss_global-maps/"
               "data_derived/Cassini_ISS_RGB_Saturn_global_color_map_"
               "contrast_enhance.fits",
        "local": "saturn_full.png",
        "credit": "NASA/JPL-Caltech/Space Science Institute (Cassini ISS, "
                  "Li et al. 2023 PDS4 bundle)",
        "size": (3600, 1800),
        "crop_dupe_edge": True,          # 3601x1801 inclusive grid
        "post": lambda im: fill_lat_band(
            fill_polar_gap(fill_polar_gap(im, 76, north=True), -76, north=False),
            5.0, -19.0),
    },

    # MESSENGER MDIS enhanced-color global mosaic (8-filter principal-
    # component composite emphasizing composition — not visual color; the
    # caption says "enhanced color"). PIA17386. Simple cylindrical centered
    # 180 deg E: left edge 0 deg E, east-positive increasing rightward
    # (verified: Caloris basin lands at 162 deg E). Polar zones are filled
    # with the monochrome MDIS basemap where color coverage was missing.
    "mercury": {
        "url": "https://assets.science.nasa.gov/content/dam/science/psd/"
               "photojournal/pia/pia17/pia17386/PIA17386.jpg",
        "credit": "NASA/JHUAPL/Carnegie Inst. Washington (MESSENGER MDIS, "
                  "PIA17386, enhanced color)",
        "size": (3600, 1800),
    },

    # Magellan C3-MDIR synthetic-color radar mosaic (radar backscatter with
    # a Venera-lander-derived palette — brightness is radar roughness, not
    # optical appearance). USGS Astrogeology. Equirectangular, planetocentric
    # latitude, east-positive longitude -180..180, Greenwich-analog (0 deg E)
    # at center (verified: Aphrodite Terra spans the equator 60-210 deg E).
    # The source GeoTIFF is ~100 MB; a locally converted JPEG is used when
    # present at the "local" path.
    "venus": {
        "url": "https://planetarymaps.usgs.gov/mosaic/"
               "Venus_Magellan_C3-MDIR_Colorized_Global_Mosaic_4641m.tif",
        "local": "venus_full.jpg",
        "credit": "NASA/JPL/USGS (Magellan C3-MDIR synthetic color radar "
                  "mosaic)",
        "size": (3600, 1800),
    },

    # Blue Marble Next Generation w/ topography & bathymetry, July 2004.
    # MODIS/Terra composite, cloud-free. -180..180 east longitude,
    # Greenwich at center (verified visually against continents).
    "earth": {
        "url": "https://eoimages.gsfc.nasa.gov/images/imagerecords/73000/"
               "73751/world.topo.bathy.200407.3x5400x2700.jpg",
        "credit": "NASA Earth Observatory Blue Marble NG, R. Stockli "
                  "(MODIS/Terra), July 2004",
        "size": (3600, 1800),
    },

    # Earth at Night 2012, Suomi NPP VIIRS day/night band composite.
    # Same projection/convention as Blue Marble; resampled to identical
    # dimensions so the runtime can index both textures with one lookup.
    "earth_night": {
        "url": "https://eoimages.gsfc.nasa.gov/images/imagerecords/79000/"
               "79765/dnb_land_ocean_ice.2012.3600x1800.jpg",
        "credit": "NASA Earth Observatory / NOAA NGDC, Suomi NPP VIIRS, 2012",
        "size": (3600, 1800),
    },

    # Hubble OPAL global map of Uranus, Cycle 33 rotation 2 (2025-10-24),
    # WFC3/UVIS F657N/F547M/F467M composite, Minnaert-corrected.
    # Right edge = 0 deg EAST longitude increasing leftward (per readme);
    # zero-longitude epoch effectively arbitrary for a featureless giant.
    # The southern hemisphere is unobservable from Earth (pole tilted
    # away) and the data edge carries RGB-misregistration fringe up to
    # ~-4 deg: everything south of -2 deg is filled with the data-edge
    # mean color.
    "uranus": {
        "url": "https://archive.stsci.edu/hlsps/opal/cycle33/uranus/"
               "hlsp_opal_hst_wfc3-uvis_uranus-2025b_f657n-f547m-f467m_v1_globalmap.tif",
        "credit": "NASA/ESA/STScI, Hubble OPAL program (PI A. Simon), "
                  "DOI 10.17909/T9G593, Oct 2025",
        "size": (2160, 1080),
        "crop_dupe_edge": True,          # 721x361 inclusive grid
        "post": lambda im: tint_to_mean(fill_polar_gap(im, -2, north=False),
                                        (166, 199, 203)),
    },

    # Hubble OPAL global map of Neptune, Cycle 32 rotation 2 (2025-08-24),
    # same filter recipe. Left edge = 360 deg WEST longitude decreasing
    # rightward (per readme). The north is unobservable and scalloped
    # frame-limb artifacts reach down to ~+35 deg: filled above +30.
    "neptune": {
        "url": "https://archive.stsci.edu/hlsps/opal/cycle32/neptune/"
               "hlsp_opal_hst_wfc3-uvis_neptune-2025c_f467m-f547m-f657n_v1_globalmap.tif",
        "credit": "NASA/ESA/STScI, Hubble OPAL program (PI A. Simon), "
                  "DOI 10.17909/T9G593, Aug 2025",
        "size": (2160, 1080),
        "crop_dupe_edge": True,
        "post": lambda im: tint_to_mean(fill_polar_gap(im, 30, north=True),
                                        (118, 154, 189)),
    },
}


def build_saturn_rings():
    """Radial color/alpha profile of Saturn's rings from the Cassini
    PIA08389 rectified natural-color scan of the UNLIT ring face
    (radius left to right, ~6 km/px).

    Physics: unlit-face brightness peaks at intermediate optical depth —
    translucent regions glow with transmitted sunlight while both the
    opaque B-ring core and truly empty gaps are dark — so the scan gives
    radius-registered fine structure and hue, while published per-region
    mean optical depths provide the low-frequency backbone that breaks
    the dark=opaque / dark=empty degeneracy. tau is modulated within each
    region by the scan with the physically right sign; alpha = 1-e^-tau;
    lit luminance = region albedo x alpha^0.55 (C/CD particles are darker
    than B/A ice).

    Radius calibration: piecewise-linear through six unambiguous scan
    features verified by eye — C inner edge, Colombo gap (77,870 km),
    Maxwell gap (87,510), Encke gap (133,589), A outer edge (136,780),
    F ring peak (140,180); the scan rate drifts ~5%% so a single linear
    fit is not enough. Output: data/planets/saturn_rings.png (660x1 RGBA,
    74,000..140,600 km)."""
    import numpy as np

    url = ("https://assets.science.nasa.gov/content/dam/science/psd/"
           "photojournal/pia/pia08/pia08389/PIA08389.jpg")
    print(f"saturn_rings: fetching {url}")
    img = fetch(url)
    a = np.asarray(img).astype(np.float64)
    H, W = a.shape[:2]
    band = a[int(H * 0.38):int(H * 0.62)].mean(axis=0)
    lum = band @ [0.299, 0.587, 0.114]
    sl = np.convolve(lum, np.ones(7) / 7, mode="same")

    # anchors: (approx px from inspection, refine, radius km)
    def local_min(px0, w=140):
        s = slice(max(0, px0 - w), px0 + w)
        return s.start + int(np.argmin(sl[s]))
    def local_max(px0, w=140):
        s = slice(max(0, px0 - w), px0 + w)
        return s.start + int(np.argmax(sl[s]))
    def rise_edge(px0, w=200):     # C inner: first sustained brightness
        s0 = max(0, px0 - w)
        for x in range(s0, px0 + w):
            if sl[x] > 25 and sl[x + 15] > 25:
                return x
        return px0
    def drop_edge(px0, w=200):     # A outer: steepest fall
        s = slice(max(0, px0 - w), px0 + w)
        g = np.diff(sl[s])
        return s.start + int(np.argmin(g))

    anchors = [
        (rise_edge(420), 74490.0),      # C inner edge
        (local_min(990), 77870.0),      # Colombo gap
        (local_min(2600), 87510.0),     # Maxwell gap
        (local_min(9800), 133589.0),    # Encke gap
        (drop_edge(10310), 136780.0),   # A outer edge
        (local_max(10880), 140180.0),   # F ring
    ]
    px_a = np.array([p for p, _ in anchors], float)
    km_a = np.array([r for _, r in anchors], float)
    rates = np.diff(km_a) / np.diff(px_a)
    print("saturn_rings: anchors", [(int(p), int(r)) for p, r in anchors])
    print("saturn_rings: km/px per segment", np.round(rates, 2))
    assert np.all(rates > 4.5) and np.all(rates < 8.0), "calibration failed"
    px_of = lambda r: np.interp(r, km_a, px_a)

    REGIONS = [   # r0, r1, tau0, albedo, sign(+1: brighter=thicker)
        (74490., 91983., 0.09, 0.55, +1),     # C
        (91983., 104500., 1.00, 1.00, -1),    # B inner
        (104500., 110300., 2.50, 1.00, -1),   # B core
        (110300., 117516., 1.50, 1.00, -1),   # B outer
        (117516., 122053., 0.12, 0.60, +1),   # Cassini Division
        (122053., 133423., 0.50, 0.95, +1),   # A inner
        (133423., 133745., 0.02, 0.95, +1),   # Encke gap
        (133745., 136485., 0.60, 0.95, +1),   # A outer
        (136485., 136522., 0.02, 0.95, +1),   # Keeler gap
        (136522., 136780., 0.60, 0.95, +1),   # A edge
        (139980., 140380., 0.15, 0.80, +1),   # F
    ]
    N, R0, R1 = 660, 74000.0, 140600.0
    rgba = np.zeros((1, N, 4), np.uint8)
    norms = {}
    for (r0, r1, *_x) in REGIONS:
        i0, i1 = int(px_of(r0)), int(px_of(r1))
        if i1 - i0 > 4:
            seg = sl[i0:i1]
            norms[r0] = (np.percentile(seg, 4), np.percentile(seg, 96))
    for i in range(N):
        r = R0 + (R1 - R0) * (i + 0.5) / N
        reg = next((g for g in REGIONS if g[0] <= r < g[1]), None)
        if reg is None:
            continue
        r0, r1, tau0, alb, sgn = reg
        j = int(px_of(r))
        if j < 2 or j >= W - 2:
            continue
        loN, hiN = norms.get(r0, (0.0, 1.0))
        u = min(1.0, max(0.0, (sl[j] - loN) / max(1e-6, hiN - loN)))
        mod = (0.35 + 1.40 * u) if sgn > 0 else (1.70 - 1.10 * u)
        tau = tau0 * mod
        alpha = 1.0 - np.exp(-tau)
        cl = max(1.0, lum[j])
        chroma = np.clip(band[j] / cl, 0.8, 1.2)
        lit = 250.0 * alb * alpha ** 0.55
        rgba[0, i, :3] = np.clip(chroma * lit, 0, 255)
        rgba[0, i, 3] = int(min(0.97, alpha) * 255)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "saturn_rings.png"
    Image.fromarray(rgba, "RGBA").save(out)
    print(f"saturn_rings: wrote {out} ({out.stat().st_size} B)  credit: "
          "NASA/JPL/Space Science Institute (Cassini ISS, PIA08389)")


def fetch(url: str) -> Image.Image:
    req = urllib.request.Request(url, headers={"User-Agent": "celestial-display/1.0"})
    with urllib.request.urlopen(req, timeout=180) as r:
        return Image.open(io.BytesIO(r.read())).convert("RGB")


def build(name: str) -> None:
    spec = MAPS[name]
    local = spec.get("local")
    candidates = [Path(local), Path(__file__).parent / local] if local else []
    src = next((p for p in candidates if p.exists()), None)
    if src:
        print(f"{name}: using local {src}")
        img = Image.open(src).convert("RGB")
    else:
        print(f"{name}: fetching {spec['url']}")
        img = fetch(spec["url"])
    if spec.get("crop_dupe_edge"):
        img = img.crop((0, 0, img.width - 1, img.height - 1))
    if spec.get("post"):
        img = spec["post"](img)
    img = img.resize(spec["size"], Image.LANCZOS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / f"{name}.jpg"
    img.save(out, "JPEG", quality=JPEG_QUALITY, optimize=True)
    print(f"{name}: wrote {out} ({out.stat().st_size / 1024:.0f} KB)  "
          f"credit: {spec['credit']}")


if __name__ == "__main__":
    names = sys.argv[1:] or list(MAPS) + ["saturn_rings"]
    for n in names:
        if n == "saturn_rings":
            build_saturn_rings()
        else:
            build(n)
