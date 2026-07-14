# Celestial Display

Ambient astronomical art for a framed OLED display. Three rotating scenes —
a log-radial Keplerian orrery, an all-sky star field, and a synthetic cosmic
web — rendered fullscreen on pure black, crossfading through darkness.

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

Examples:

    # iPad picture frame: lighter field, pure art, 15-min scenes
    https://.../?density=0.6&labels=off&hold=900

    # future 4K wall OLED: full density, 30-min scenes
    https://.../?hold=1800

    # orrery only
    https://.../?scene=0

## Display devices

See `docs/HARDWARE.md` for the iPad frame setup (Guided Access / kiosk
options, brightness scheduling, framing notes) and the planned wall-OLED
build.

## Data upgrades

The star field and cosmic web currently use synthetic data (and say so in
their captions). The upgrade path — Gaia DR3 for the stars, SDSS or
IllustrisTNG for large-scale structure — is documented in
`docs/ROADMAP.md`, with a starter preprocessing script in `scripts/`.

## Development conventions

Read `CLAUDE.md` first — it defines the architecture rules, design system,
scene interface, and performance budget. The short version: one static
file, no build step, pure-black OLED-native design, honest physics,
restraint over spectacle.
