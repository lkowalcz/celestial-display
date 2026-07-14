# Roadmap

Ordered roughly by impact. Each dataset upgrade follows the same pattern:
an offline Python script in `scripts/` converts a public catalog into a
compact static file in `data/`, and the scene fetches it once at load
(falling back to the current synthetic generator if the fetch fails).

## 1. Gaia DR3 star field (flagship upgrade) — DONE 2026-07

Shipped: 482k stars to G < 10 in data/gaia_stars.bin; faint field baked
to a texture, bright stars live with BP−RP colors; Hipparcos fills the
Gaia bright-star saturation gap (nothing below G ≈ 1.7 in gaia_source).
Possible refinements: deeper mag limit via density texture, proper
motions. Original plan:

- Query Gaia DR3 for stars to magnitude ~10–11 (~1–2M stars is plenty;
  full DR3 is 1.8B and pointless at display resolution).
- Keep per star: galactic lon/lat (or ra/dec), G magnitude, BP−RP color.
- Pack as binary: 3 × uint16 per star (lon, lat, mag+color packed)
  → ~1–2M stars ≈ 6–12 MB, acceptable as a one-time fetch; or bin to a
  HEALPix/density texture for the faint field and keep only bright stars
  as discrete points (better).
- Render: bright stars (< mag 6) as discrete glows colored by BP−RP;
  fainter field as an accumulated intensity layer. The Milky Way emerges
  from the data instead of being painted.
- Starter script: `scripts/gaia_preprocess.py`.

## 2. Live Sun (SDO) — first live-data scene

- NASA SDO publishes near-real-time full-disk imagery (AIA 171/304/211 Å).
- Scene fetches the latest image every ~15 min, slowly crossfades
  wavelengths; caption shows observation timestamp.
- Needs a CORS-friendly source or a small Cloudflare Worker proxy that
  caches images. Must degrade gracefully offline (skip scene or show the
  last cached frame with an honest "stale" timestamp).

## 3. Real large-scale structure

Two candidate replacements for the synthetic cosmic web:

- SDSS spectroscopic galaxy sample: the classic redshift "fan" — real
  observed galaxies, plotted in comoving coordinates. 2D slice, striking,
  historically iconic.
- IllustrisTNG public snapshot: subsample dark-matter particles from one
  snapshot (~50–100k points), precompute positions, keep the current 3D
  slow-rotation renderer. Theory-side counterpart to SDSS.

Possibly both, as separate scenes.

## 4. Additional scene candidates

- Laniakea-style local flows: galaxy peculiar-velocity streamlines
  (CosmicFlows data) — the most beautiful figure in modern cosmology.
- Space weather instrument panel: DSCOVR solar wind speed/density/Bz,
  GOES X-ray flux, Kp — live streaming plots, deliberately styled like
  the rest (thin lines, mono labels), not like a dashboard product.
- Pulsar stack: PSR B1919+21 (the Unknown Pleasures data) rendered
  honestly, or a modern pulsar timing array visualization.
- Exoplanet systems: confirmed multi-planet systems drawn to the same
  log-radial grammar as the orrery, rotating through systems.

## 5. Infrastructure

- Auto-reload: displays should poll a version string (e.g., a `version.json`)
  every few hours and reload when it changes, so kiosk devices pick up
  deploys without touching them.
- Night schedule: optional `?nightdim=23-7` style param to drop global
  canvas brightness during set hours (belt-and-suspenders alongside device
  auto-brightness).
- Scene playlist param: `?scenes=0,2` to select and order a subset.
