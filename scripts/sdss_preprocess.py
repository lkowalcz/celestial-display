#!/usr/bin/env python3
"""
SDSS DR18 spectroscopic galaxies -> compact catalog for the redshift fan.

Downloads the legacy main galaxy sample (survey='sdss', class='GALAXY',
sciencePrimary=1, zWarning=0, 0.003 < z < 0.25) from the public SkyServer
SQL API — real observed galaxies with spectroscopic redshifts, the sample
behind the classic SDSS "fan" plots. No registration required.

Output format (little-endian), data/sdss_galaxies.bin:
    header:  uint32 magic 0x53445353 ("SDSS"), uint32 count
    per galaxy (6 bytes):
        uint16 ra     [0, 360) deg scaled to [0, 65535]
        uint16 dec    [-90, +90] deg scaled to [0, 65535]
        uint16 z      [0, Z_MAX] scaled to [0, 65535]

z is stored raw (the measurement); redshift -> comoving distance is the
display's job, so the cosmology is explicit in one place there.

Usage:
    python scripts/sdss_preprocess.py --out data/sdss_galaxies.bin
"""

import argparse
import io
import struct
import sys
import urllib.parse
import urllib.request

import numpy as np

MAGIC = 0x53445353
Z_MIN, Z_MAX = 0.003, 0.25
API = "https://skyserver.sdss.org/dr18/SkyServerWS/SearchTools/SqlSearch"

# SkyServer caps SqlSearch at 500k rows; chunk by declination.
DEC_EDGES = [-25, 0, 5, 10, 15, 20, 25, 30, 35, 40, 50, 90]


def fetch_chunk(d0: float, d1: float) -> "np.ndarray":
    sql = f"""
        SELECT ra, dec, z FROM SpecObj
        WHERE class='GALAXY' AND survey='sdss' AND zWarning=0
          AND sciencePrimary=1 AND z BETWEEN {Z_MIN} AND {Z_MAX}
          AND dec >= {d0} AND dec < {d1}
    """
    url = API + "?" + urllib.parse.urlencode({"cmd": " ".join(sql.split()), "format": "csv"})
    raw = urllib.request.urlopen(url, timeout=600).read().decode()
    # first line is "#Table1", second is the header
    data = np.genfromtxt(io.StringIO(raw), delimiter=",", skip_header=2)
    data = np.atleast_2d(data)
    if data.size == 0 or data.shape[1] != 3:
        return np.empty((0, 3))
    print(f"  dec [{d0:+.0f}, {d1:+.0f}): {len(data)} galaxies", file=sys.stderr)
    return data


def pack(gal: "np.ndarray", path: str) -> None:
    ra = np.mod(gal[:, 0], 360) / 360
    dec = (gal[:, 1] + 90) / 180
    z = np.clip(gal[:, 2] / Z_MAX, 0, 1)
    q = lambda x: np.round(x * 65535).astype("<u2")
    packed = np.column_stack([q(ra), q(dec), q(z)])
    with open(path, "wb") as f:
        f.write(struct.pack("<II", MAGIC, len(packed)))
        f.write(packed.tobytes())
    print(f"Wrote {len(packed)} galaxies -> {path} "
          f"({8 + packed.nbytes} bytes)", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", default="data/sdss_galaxies.bin")
    args = p.parse_args()

    chunks = []
    for d0, d1 in zip(DEC_EDGES, DEC_EDGES[1:]):
        chunks.append(fetch_chunk(d0, d1))
    gal = np.vstack([c for c in chunks if len(c)])
    print(f"total: {len(gal)}", file=sys.stderr)
    pack(gal, args.out)


if __name__ == "__main__":
    main()
