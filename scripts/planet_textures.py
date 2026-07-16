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


MAPS = {
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
        "post": lambda im: fill_polar_gap(im, -2, north=False),
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
        "post": lambda im: fill_polar_gap(im, 30, north=True),
    },
}


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
    names = sys.argv[1:] or list(MAPS)
    for n in names:
        build(n)
