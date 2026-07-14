# Celestial Display

An ambient astronomical art display: rotating, physically honest space
visualizations rendered fullscreen in a browser, framed on a wall. Currently
targeting an iPad Pro (tandem OLED) in a picture frame; will later migrate to
a large wall-mounted OLED. The display device is a dumb screen pointing a
kiosk browser at a hosted URL — all intelligence lives in this repo.

## Owner context

The owner is a quantitative researcher with a physics/math-literate eye.
Scientific honesty is a feature: real orbital mechanics, real catalogs, real
survey data. "Looks like a screensaver" is failure; "looks like an instrument
made by someone who understands the data" is success.

## Architecture principles (do not violate without discussion)

1. **Single static site, no build step.** `index.html` is self-contained
   vanilla HTML/CSS/JS + Canvas 2D. No frameworks, no bundlers, no npm. It
   must open correctly from `file://` and from GitHub Pages.
2. **Device-independent, URL-configured.** One deployment serves every
   display. Per-device tuning happens ONLY via query params (see Config
   below), never via device-detection branches in code.
3. **Offline-first for rendering.** Scenes must render with no network.
   Real datasets (Gaia, SDSS, etc.) are preprocessed into compact static
   files in `data/` and fetched once. Live-data scenes (future: SDO sun,
   space weather) must degrade gracefully when offline.
4. **OLED-native design.** Background is pure #000 (pixels off). Scene
   transitions fade through black. No static bright chrome (burn-in); all UI
   is hover/touch-revealed and auto-hides. Ambient motion is slow drift —
   this is both the aesthetic and the burn-in mitigation.
5. **Physics is honest.** Orbital positions solve Kepler's equation; speeds
   follow Kepler's third law; the log-radial mapping is applied to true
   instantaneous distance. When a scene uses synthetic/procedural data, its
   caption must say so. Never fake a dataset and label it real.

## Design system

- Palette: background #000; star white #E8ECF2; mid gray #9AA3AD; dim gray
  #565E68; ice blue #7FB4D9; warm amber #C9A26B. Introduce new colors
  sparingly and only with a physical justification (e.g., stellar
  temperature classes).
- Type: IBM Plex Mono only. Captions are small (9–11px), uppercase,
  letter-spaced (0.18–0.28em). Text is nearly absent by design — the
  imagery is the interface.
- Restraint over spectacle. No lens flares, no purple nebula clichés, no
  bloom for its own sake. Thin lines, small glows, low alphas.

## Scene interface

Each scene is an object: `{ title, detail, init(), draw(t) }`.
- `init()` runs once at load; generates size-independent data only.
- `draw(t)` renders one frame; `t` is per-scene seconds (pausable). All
  geometry derives from current `W`, `H` at draw time (resize-safe).
- Register in the `scenes` array. Captions/dots/keyboard update automatically.
- Respect `MOTION` (reduced-motion multiplier) and `D` (density multiplier)
  in all particle counts and angular speeds.

Current scenes:
1. `orrery` — log-radial heliocentric solar system on real ephemeris:
   JPL/Standish J2000 elements + rates, Kepler-solved. Runs as a clock —
   each showing sweeps a time window centered on the actual current date
   (half past, half future) at 1 s = 1 day, with a live date readout in
   the caption. Kirkwood-gapped asteroid belt (statistical), Jupiter
   trojans tied to Jupiter's true mean longitude, 1/10 AU reference rings.
2. `starfield` — all-sky equirectangular field from real Gaia DR3 data:
   ~482k stars to G < 10 (data/gaia_stars.bin, built by
   scripts/gaia_preprocess.py; brightest ~20 stars from Hipparcos since
   Gaia saturates on them). Faint field is baked into an offscreen
   texture once at load (rebuilt on resize); naked-eye stars draw live
   with twinkle and BP−RP temperature colors. Falls back to the previous
   synthetic generator when the data fetch fails (offline, file://).
3. `cosmicWeb` — synthetic large-scale structure: halo nodes, nearest-
   neighbor filaments, 3D slow rotation. Upgrade path: SDSS or IllustrisTNG.

## Config (URL query params)

| param     | default        | meaning                                  |
|-----------|----------------|------------------------------------------|
| `hold`    | 40             | seconds per scene before crossfade       |
| `fade`    | 2.6            | crossfade duration (through black)       |
| `density` | auto by pixels | particle-count multiplier (0.35–2.0)     |
| `labels`  | on             | `off` hides planet names + AU rings      |
| `scene`   | (rotate)       | 0-indexed scene lock, disables rotation  |

Typical deployments:
- iPad frame: `?density=0.6&labels=off&hold=900`
- 4K wall OLED: `?hold=1800`

## Performance budget

Must hold 60fps (or clean 30) on an iPad in Safari and on an Intel N100
mini PC in Chromium. Practical ceilings: ~8k particles per scene at
density 1.0, no per-frame allocation in draw loops, no shadowBlur (it is
slow) — use radial gradients or pre-rendered sprites for glows.

## Testing changes

No test framework. Verify by opening index.html locally and checking:
every scene renders, crossfades complete, controls appear on
mousemove/touch and auto-hide, arrow keys + space work, `?scene=N` locks,
`?labels=off` removes all text from the orrery, resize mid-scene doesn't
break, and prefers-reduced-motion slows all drift.

## Repo layout

- `index.html` — the entire app
- `data/` — preprocessed binary/JSON datasets (committed if <10MB, else
  documented download)
- `scripts/` — offline preprocessing (Python), never required at runtime
- `docs/HARDWARE.md` — device setup: iPad kiosk config, future wall build
- `docs/ROADMAP.md` — planned scenes and data upgrades
