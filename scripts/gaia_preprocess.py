#!/usr/bin/env python3
"""
Gaia DR3 -> compact star catalog for the Celestial Display star field.

Queries the ESA Gaia archive (TAP) for bright stars, converts to galactic
coordinates, and packs a small binary the display fetches once.

Output format (little-endian), data/gaia_stars.bin:
    header:  uint32 magic 0x47414941 ("GAIA"), uint32 count
    per star (8 bytes):
        uint16 lon      galactic longitude, [0, 2pi) scaled to [0, 65535]
        uint16 lat      galactic latitude, [-pi/2, pi/2] scaled to [0, 65535]
        uint16 mag      G magnitude, [MAG_MIN, MAG_MAX] scaled to [0, 65535]
        uint16 color    BP-RP, [BPRP_MIN, BPRP_MAX] clamped+scaled

~500k stars = 4 MB. Run offline; never required at display runtime.

Usage:
    pip install astroquery numpy
    python scripts/gaia_preprocess.py --mag-limit 10.0 --out data/gaia_stars.bin

NOTE: written as a starting point; verify against the current Gaia archive
schema/endpoints on first run (table gaiadr3.gaia_source, columns l, b,
phot_g_mean_mag, bp_rp).
"""

import argparse
import struct
import sys

import numpy as np

MAGIC = 0x47414941
MAG_MIN, MAG_MAX = -2.0, 12.0
BPRP_MIN, BPRP_MAX = -0.6, 4.0


def query_gaia(mag_limit: float, max_rows: int) -> "np.ndarray":
    from astroquery.gaia import Gaia

    Gaia.ROW_LIMIT = max_rows
    adql = f"""
        SELECT l, b, phot_g_mean_mag, bp_rp
        FROM gaiadr3.gaia_source
        WHERE phot_g_mean_mag < {mag_limit}
          AND bp_rp IS NOT NULL
    """
    print(f"Querying Gaia DR3 (G < {mag_limit}) ...", file=sys.stderr)
    job = Gaia.launch_job_async(adql)
    table = job.get_results()
    print(f"  received {len(table)} rows", file=sys.stderr)

    out = np.empty((len(table), 4), dtype=np.float64)
    out[:, 0] = np.radians(np.asarray(table["l"], dtype=np.float64))    # lon
    out[:, 1] = np.radians(np.asarray(table["b"], dtype=np.float64))    # lat
    out[:, 2] = np.asarray(table["phot_g_mean_mag"], dtype=np.float64)  # mag
    out[:, 3] = np.asarray(table["bp_rp"], dtype=np.float64)            # color
    return out


def query_bright_hipparcos(vmax: float = 3.0) -> "np.ndarray":
    """Gaia saturates on the brightest stars (nothing below G ~ 1.7 in DR3
    gaia_source with bp_rp), so Sirius, Vega, Betelgeuse etc. are absent.
    Augment from Hipparcos (VizieR I/239) with approximate photometric
    conversions (V ~ G, BP-RP ~ 1.3(B-V)) — display-grade, not science-grade.
    """
    from astroquery.vizier import Vizier
    from astropy.coordinates import SkyCoord

    v = Vizier(columns=["RAICRS", "DEICRS", "Vmag", "B-V"],
               column_filters={"Vmag": f"<{vmax}"}, row_limit=-1)
    table = v.query_constraints(catalog="I/239/hip_main")[0]
    print(f"Hipparcos bright stars (V < {vmax}): {len(table)}", file=sys.stderr)

    vmag = np.ma.filled(np.asarray(table["Vmag"], dtype=np.float64), 1.0)
    bv = np.ma.filled(np.asarray(table["B-V"], dtype=np.float64), 0.5)
    gal = SkyCoord(ra=table["RAICRS"], dec=table["DEICRS"],
                   unit="deg", frame="icrs").galactic

    out = np.empty((len(table), 4), dtype=np.float64)
    out[:, 0] = gal.l.radian
    out[:, 1] = gal.b.radian
    out[:, 2] = vmag                # V ~ G
    out[:, 3] = 1.3 * bv            # B-V -> BP-RP, rough
    return out


def merge_bright(gaia: "np.ndarray", hip: "np.ndarray") -> "np.ndarray":
    """Append Hipparcos stars not already present in Gaia (0.3 deg match
    against Gaia G < 3.5)."""
    def unit(lon, lat):
        cb = np.cos(lat)
        return np.stack([cb * np.cos(lon), cb * np.sin(lon), np.sin(lat)], axis=1)

    gb = gaia[gaia[:, 2] < 3.5]
    gu, hu = unit(gb[:, 0], gb[:, 1]), unit(hip[:, 0], hip[:, 1])
    cos_match = np.cos(np.radians(0.3))
    dup = (hu @ gu.T).max(axis=1) > cos_match if len(gb) else np.zeros(len(hip), bool)
    added = hip[~dup]
    print(f"  {dup.sum()} already in Gaia, adding {len(added)}", file=sys.stderr)
    return np.vstack([gaia, added])


def pack(stars: "np.ndarray", path: str) -> None:
    lon = np.mod(stars[:, 0], 2 * np.pi) / (2 * np.pi)
    lat = (stars[:, 1] + np.pi / 2) / np.pi
    mag = np.clip((stars[:, 2] - MAG_MIN) / (MAG_MAX - MAG_MIN), 0, 1)
    col = np.clip((stars[:, 3] - BPRP_MIN) / (BPRP_MAX - BPRP_MIN), 0, 1)

    q = lambda x: np.round(x * 65535).astype("<u2")
    packed = np.column_stack([q(lon), q(lat), q(mag), q(col)])

    with open(path, "wb") as f:
        f.write(struct.pack("<II", MAGIC, len(packed)))
        f.write(packed.tobytes())
    print(f"Wrote {len(packed)} stars -> {path} "
          f"({8 + packed.nbytes} bytes)", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mag-limit", type=float, default=10.0,
                   help="G magnitude limit (10 ~ 0.5M stars, 11 ~ 1.5M)")
    p.add_argument("--max-rows", type=int, default=3_000_000)
    p.add_argument("--out", default="data/gaia_stars.bin")
    args = p.parse_args()

    stars = query_gaia(args.mag_limit, args.max_rows)
    stars = merge_bright(stars, query_bright_hipparcos())
    pack(stars, args.out)


if __name__ == "__main__":
    main()
