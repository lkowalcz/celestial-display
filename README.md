# Celestial Display

Ambient astronomical art for a framed OLED display. Four rotating scenes —
a log-radial orrery clocked to the real JPL ephemeris, a real-time horizon
view of the Gaia DR3 sky with the Sun, Moon, and planets where they stand
right now, the SDSS DR18 galaxy redshift fan, and a general-relativistic
ray-trace of M87* and Sgr A* shown beside the images the Event Horizon
Telescope actually recorded — rendered fullscreen on pure black,
crossfading through darkness.

The display architecture is deliberately dumb: any device with a browser
opens one URL in kiosk mode. Development happens here; displays update on
git push.

## Quick start

Open `index.html` in a browser. That's the whole app.

Keyboard: `←` / `→` switch scenes, `space` pauses. Move the mouse (or tap)
to reveal controls; they auto-hide.

## Deploy (GitHub Pages)

1. Push this repo to GitHub.
2. Settings → Pages → Deploy from branch → `main` / root.
3. The display URL is `https://<user>.github.io/<repo>/`.

Every device points at that URL with its own query string.

## Per-device configuration

Configuration is entirely via URL parameters — no code branches per device.

| param     | default        | meaning                                  |
|-----------|----------------|------------------------------------------|
| `hold`    | 40             | seconds per scene                        |
| `fade`    | 2.6            | crossfade seconds                        |
| `density` | auto by pixels | particle multiplier (0.35–2.0)           |
| `labels`  | on             | `off` = no planet names / AU rings       |
| `scene`   | (rotate)       | lock to scene N (0-indexed)              |
| `bh`      | (alternate)    | black hole: lock to `m87` or `sgra`      |
| `bhdwell` | 110            | black hole: seconds per source           |

Examples:

    # iPad picture frame: lighter field, pure art, 15-min scenes
    https://.../?density=0.6&labels=off&hold=900

    # future 4K wall OLED: full density, 30-min scenes
    https://.../?hold=1800

    # orrery only
    https://.../?scene=0

    # black hole only, M87* held
    https://.../?scene=3&bh=m87

## Display devices

See `docs/HARDWARE.md` for the iPad frame setup (Guided Access / kiosk
options, brightness scheduling, framing notes) and the planned wall-OLED
build.

## Data upgrades

The Local Sky scene renders real Gaia DR3 astrometry: ~482k stars to
G < 10 (`data/gaia_stars.bin`, built by `scripts/gaia_preprocess.py`),
with the brightest ~20 stars — which saturate Gaia — patched in from
Hipparcos. Its Sun, Moon (true phase), and planets come from the same
JPL elements as the orrery plus a low-precision lunar theory, verified
against JPL Horizons.
The large-scale structure scene renders the SDSS DR18 main galaxy
sample: 736k spectroscopic redshifts (`data/sdss_galaxies.bin`, built by
`scripts/sdss_preprocess.py`) drawn as a redshift fan that slowly
precesses through declination slices. Offline or over `file://` both
scenes fall back to synthetic generators and say so in their captions.

The black hole scene needs no data to render — its image is integrated
from null geodesics at load — but it shows the two real EHT
reconstructions alongside, recovered from the published renderings by
`scripts/eht_images.py` into `data/eht/`. Offline the insets are simply
omitted and the caption stops claiming them.
Remaining upgrade ideas live in `docs/ROADMAP.md`.

## Development conventions

Read `CLAUDE.md` first — it defines the architecture rules, design system,
scene interface, and performance budget. The short version: one static
file, no build step, pure-black OLED-native design, honest physics,
restraint over spectacle.
