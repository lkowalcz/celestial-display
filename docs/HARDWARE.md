# Hardware

## Phase 1 — iPad Pro picture frame (current)

Target: iPad Pro M4 (11" or 13", tandem OLED). Standard vs. nano-texture
glass: nano-texture (matte, etched) is meaningfully better for a wall
display facing windows or lamps, but is only sold on 1TB/2TB configs.
Standard glass is fine if the frame can be positioned to avoid direct
reflections, and keeps the device cheaper for dual personal use.

### Running the display

Option A — Home Screen web app (simplest):
1. Open the display URL in Safari (with the device's query string).
2. Share → Add to Home Screen. Launching from that icon is fullscreen
   (no Safari chrome) thanks to the app-capable meta tags.
3. Settings → Display & Brightness → Auto-Lock → Never.

Option B — Guided Access (kiosk hardening):
1. Settings → Accessibility → Guided Access → on; set a passcode.
2. Launch the web app, triple-click the top button, Start.
3. Locks the device to the app; disable touch if the frame is reachable
   by guests/kids.

Option C — dedicated kiosk app: Kiosk Pro or similar from the App Store
adds scheduled on/off, auto-reload on network recovery, and remote URL
changes. Worth it if the iPad becomes a permanent frame.

### Brightness and panel care

- Keep auto-brightness ON — a fixed brightness that looks right at noon
  is a floodlight at midnight, and ambient adaptation is the correct
  behavior for wall art.
- True Tone: preference call. It warms the whites toward room lighting;
  for astronomical content, consider turning it off so star colors stay
  colorimetric.
- Burn-in risk on the tandem OLED is low with this content (pure black
  background, everything drifts, no static chrome), but avoid locking a
  single scene with `?scene=` for weeks at a time.

### Power and framing

- USB-C routed out the frame back to a low-profile wall adapter; charge
  limiting (iPadOS caps at 80% when persistently plugged) protects the
  battery.
- A local framer can cut a mat to the iPad's visible-screen dimensions
  and build a shadowbox deep enough for the body (~6mm + clearance).
  Leave a ventilation gap top and bottom; the M4 runs cool on this
  workload but heat shortens OLED life.
- Portrait vs. landscape: the app is orientation-agnostic (geometry
  derives from viewport at draw time). The orrery and cosmic web favor
  aspect ratios near square-to-landscape; the star field works in both.

## Phase 2 — wall OLED (future home)

Planned build, unchanged in architecture (same URL, new device):

- Panel: 42" LG C-series OLED, or a matte "glare-free" Samsung OLED
  (S95-class) if reflections demand it. Real OLED beats The Frame's QLED
  for this content — black level dominates.
- Driver: Intel N100-class mini PC (~$150) velcroed to the panel back,
  running Chromium in kiosk mode:

      chromium --kiosk --noerrdialogs --disable-session-crashed-bubble \
        --autoplay-policy=no-user-gesture-required \
        "https://<user>.github.io/<repo>/?hold=1800"

  Autostart via a systemd user service or the desktop environment's
  autostart. Disable screen blanking/DPMS.
- Power: in-wall recessed outlet + brush plate kit so no cable is visible.
- Frame: custom float frame from a framer, ventilation gaps top/bottom.
- Panel settings: disable all motion smoothing and dynamic contrast;
  enable the panel's pixel-shift/screen-saver maintenance features;
  schedule display off overnight (mini PC can stay up).
