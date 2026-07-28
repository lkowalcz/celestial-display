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
2. `localSky` — real-time horizon view: perspective camera (62° FOV)
   standing at `?lat`/`?lon`, stars where they stand over that spot NOW
   (true sidereal time from the wall clock, verified against hand
   calculation), slowly panning the horizon with horizon extinction.
   Stars come from the shared `gaiaCatalog` loader (~482k Gaia DR3
   stars to G < 10 in data/gaia_stars.bin, built by
   scripts/gaia_preprocess.py, brightest ~20 patched from Hipparcos;
   synthesized fallback offline/file://). Sun, Moon (with true phase
   via terminator-ellipse winding, low-precision lunar theory ~0.3°,
   topocentric), and naked-eye planets from the orrery's ephemeris —
   all verified against JPL Horizons. The `?callouts=N` closest bodies
   in frame get quiet name+distance labels. Pause freezes the pan,
   never the sky. Default location: Greenwich.
3. `cosmicWeb` — SDSS DR18 redshift fan: 736k real spectroscopic
   galaxies (data/sdss_galaxies.bin, built by scripts/sdss_preprocess.py),
   RA → angle, comoving distance (flat ΛCDM, H0 = 70, Ωm = 0.3) → radius.
   Precesses through 4°-wide declination slices (~36 s each, crossfaded);
   each slice baked to an offscreen texture. Reference arcs at even
   redshifts. Falls back to the synthetic web offline/file://.
4. `planetView` — planet grand tour (dedicated view: `?view=tour`, also
   served at `tour/`; not part of the default ambient rotation): the 8
   planets plus Pluto on real mission maps
   (data/planets/*.jpg, built by scripts/planet_textures.py — MESSENGER,
   Magellan radar, Blue Marble + VIIRS night, Viking MDIM, Cassini maps of
   Jupiter and Saturn, HST OPAL 2025 for Uranus/Neptune with disk-mean
   color anchored to published true color (Irwin et al. 2024 — the two are
   genuinely similar; Neptune only modestly bluer), New Horizons MVIC for
   Pluto; per-map longitude conventions recorded in both the script and
   the planetMaps registry),
   wrapped per-pixel on orthographic oblate spheres. Rotation from IAU
   pole + W models with per-planet epoch offsets fitted against JPL
   Horizons sub-observer longitudes (residual ≤0.3°, 2000–2026; conv ±1
   encodes each body's east/west longitude handedness); terminator/limb
   shading from true sun geometry (Mercury/Venus show their real phases,
   captioned); Saturn's rings colored per-radius from the Cassini
   PIA08389 radial scan (scripts/planet_textures.py build_saturn_rings —
   scan supplies registration/structure/hue, published per-region optical
   depths supply the opaque-vs-empty backbone; banded fallback offline)
   at the true opening angle, with unlit-face dimming and the planet's
   shadow cast across the ring plane; Uranus's real narrow rings (alpha
   through epsilon at true radii); Galilean moons (Meeus, Horizons-verified to
   ~0.05 R_J), Earth's Moon, and Charon (tidally locked: it rides on
   Pluto's rotation model along the sub-Charon prime meridian, verified
   against Horizons to <1 R_P); Gaia field behind each planet's true
   geocentric direction, camera up = the planet's IAU pole. Earth is
   viewed from an inertial hover over ?lat/lon (rotates beneath; VIIRS
   night lights on the dark side). The tour dwells `dwell` seconds per
   planet in order, then slews the camera across the real sky to the next
   planet's actual direction (~7 s); other planets and the Sun appear as
   dots at true positions/magnitudes throughout. Time runs at 1 s = 2 min
   (captioned); moon orbital radii compressed r^0.30 beyond 1.4 planet
   radii (captioned, limb-contact exact). Synthetic banded fallbacks
   offline/file://. Decoded textures are LRU-capped at 3 (~26 MB RGBA
   each); raw JPEGs are fetched once and kept.
5. `blackHole` — the only two black holes ever imaged at horizon scale,
   each shown twice over: as the image the EHT actually recorded, and as
   a ray-trace at the same mass, distance and inclination. The trace
   integrates null geodesics in Schwarzschild geometry (d²u/dφ² = −u +
   3u², RK4, 1536 impact parameters × 384 φ samples) once at load; the
   capture boundary lands on b = 3√3 GM/c² to within one table step, and
   the weak-field deflection matches 4GM/c²b plus its known second- and
   third-order terms. Everything visible follows from those rays: the
   shadow, the photon ring, the n = 1 lensed image of the disk's far
   side (equatorial crossings solve in closed form, A cos φ + B sin φ =
   0), and the one-sided brightness, from
   g = √(1 − 3GM/c²r) / (1 + Ω α sin i) carried as g⁴ — the photon's
   L_z/E = −α sin i makes the Doppler term exact per pixel. Thin,
   optically thin (correct at 1.3 mm) Keplerian disk from the ISCO to
   18 GM/c², emissivity ∝ r⁻² tapered at the outer edge. Mottling
   advects at the local Keplerian rate, so differential rotation shears
   it into trailing spirals by itself; two fields crossfade on a 45 s
   turbulent correlation time (unbounded shear would otherwise alias
   into hash) and per-pixel bandlimiting damps the modulation where the
   lensed ring undersamples it. Bake is 2×2 supersampled — averaging
   gain, keeping the brightest subsample's phase — because the shadow
   edge and the n = 1 ring are both sub-pixel. Color encodes g against a
   fixed anchor: white is g = 1, amber below, ice blue above, so the
   disk reads warm because it genuinely is net-redshifted nearly
   everywhere. Only `paBright` comes from the data — GR fixes how
   strongly the disk beams but not which way it spins on the sky, so the
   model is rotated to put its approaching side where the recorded
   bright arc sits. The contrast is then a check rather than a fit:
   blurred to the real 20 μas beam the model gives 2.34× for M87*
   against 2.41× measured (Sgr A* over-predicts, 4.7× vs 1.6×, as
   expected for a source that varies within the observation). The
   recorded images are rendered gray on purpose — the trace is colored
   by something the model knows, and intensity is all the data has.
   Sources alternate every `bhdwell` seconds, fading through black so
   the rebake is invisible. The trace needs no network at all; the
   insets come from data/eht/ (scripts/eht_images.py) and are simply
   omitted offline/file://, with the caption dropping the claim.

## Config (URL query params)

| param     | default        | meaning                                  |
|-----------|----------------|------------------------------------------|
| `view`    | ambient        | `ambient`: 4-scene rotation; `tour`: planet grand tour (also at `tour/`) |
| `hold`    | 40             | seconds per scene before crossfade       |
| `fade`    | 2.6            | crossfade duration (through black)       |
| `density` | auto by pixels | particle-count multiplier (0.35–2.0)     |
| `labels`  | on             | `off` hides planet names + AU rings      |
| `scene`   | (rotate)       | 0-indexed scene lock, disables rotation  |
| `lat`     | 51.4779        | observer latitude for Local Sky (deg, N+)|
| `lon`     | 0              | observer longitude (deg, E+)             |
| `callouts`| 4              | Local Sky: label the N closest bodies    |
| `dwell`   | 75 (tour)      | Planets: seconds per planet (min 10)     |
| `planet`  | mercury        | Planets: starting planet (name or 0–8)   |
| `bh`      | (alternate)    | Black Hole: lock to `m87` or `sgra`      |
| `bhdwell` | 110            | Black Hole: seconds per source (min 20)  |

Typical deployments:
- iPad frame: `?density=0.6&labels=off&hold=900`
- 4K wall OLED: `?hold=1800`
- dedicated planet tour: `tour/` (equivalently `?view=tour`), e.g.
  `tour/?dwell=180&labels=off`

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
- `tour/index.html` — tiny stub: forwards to `../?view=tour` (clean path
  for the planet-tour deployment; all logic stays in the single app)
- `data/` — preprocessed binary/JSON datasets (committed if <10MB, else
  documented download)
- `scripts/` — offline preprocessing (Python), never required at runtime
  (`eht_images.py` recovers relative intensity from the published EHT
  renderings by inverting the afmhot colormap — exact, since afmhot is
  piecewise-linear and injective — and anchors the pixel scale to the
  published ring diameter; both caveats are recorded in its docstring)
- `docs/HARDWARE.md` — device setup: iPad kiosk config, future wall build
- `docs/ROADMAP.md` — planned scenes and data upgrades
