# Karaoke Buddy — Browser Preview

A **static, no-backend, in-browser demo** of Karaoke Buddy's core experience:
shift a song's **key** live and **fade out the original lead singer**, with
your ears as the only proof you need. Open it, press play, drag two sliders.

> This is a *preview*, not the product. It exists so a hiring manager can hear
> what the desktop app does in ten seconds, with no download.

## What it demonstrates

| Control | What it does | How |
| --- | --- | --- |
| **Song key** (-6…+6 semitones, snaps to integers) | Re-pitches the playing audio in real time **without changing tempo** | [SoundTouchJS](./vendor/soundtouchjs/) WSOLA pitch shifter, driven inside a Web Audio **AudioWorklet** |
| **Silence the singer** (0–100%) | Fades the centre-panned lead vocal | Mid/side centre subtraction: `out_L = L - mix·R`, `out_R = R - mix·L`, `mix = pct/100 · 0.5` |
| **Match my key** (mic) | Sings → auto-sets the Song key to fit your voice | Autocorrelation pitch detection on `getUserMedia` mic input (see below) |

Both controls are live: drag while the audio plays and you hear the change
immediately.

## ✨ Match my key (mic auto-key-detect)

Tap **Match my key**, hum or sing one steady note for ~2 seconds, and the
demo shifts the **Song key** to fit *your* voice — no guessing where the
fader should go.

It's transparent, not magic — it tells you exactly what it heard, e.g.
**"Heard ~G3 (196 Hz) → shifting +2."**

How it works (all in `app.js`):

1. **Capture** — `getUserMedia({audio:true})` → an `AnalyserNode`. The mic is
   only requested on tap (never on load) and the stream is **torn down the
   instant capture ends** — the recording dot doesn't linger.
2. **Detect pitch** — clean-room **time-domain autocorrelation**: a periodic
   signal correlates with itself shifted by its period `P`, so we scan a band
   of candidate lags, take the strongest normalized peak, refine it with
   parabolic interpolation, and read `f0 = sampleRate / lag`. We collect a
   confident estimate per animation frame and take the **median** over the
   window (robust to octave jumps / transients).
3. **Two honest gates, no fallback** — an estimate counts only if it's loud
   enough (RMS ≥ 0.01) *and* periodic enough (normalized autocorrelation peak
   ≥ 0.9). Too quiet, too noisy, or mic denied → an explicit, visible failure
   (*"Didn't catch a clear note — try again"*), never a made-up shift.
4. **Map to semitones** — detected `f0` → nearest note (MIDI 69 = A4 = 440 Hz).
   "Best fit" = shift the song so its reference pitch (**A3, 220 Hz**) lands
   nearest your note: `semitones = round(12·log2(f0 / 220))`, **clamped to the
   slider's ±6 range** (if your note wants more, it says so: *"wanted +9,
   capped at +6"*).
5. **One pitch path** — the suggestion is applied through the *same*
   `applyKeyShift()` the slider uses: it moves the fader, repaints the label,
   and drives the worklet — UI and engine stay in lockstep.

## The audio: synthesized, never copyrighted

The demo ships **no song files**. On first play we render a ~24-second stereo
clip from Web Audio oscillators (`app.js` → `synthesizeDemo`):

- a warm arpeggiated **backing bed**, hard-panned left/right (lives in the
  *sides*), and
- a clear **lead "vocal" melody**, panned dead-centre (identical in L and R).

Because the lead is centred and the backing is in the sides, the two controls
are independently demonstrable:

- **Song key** shifts *everything* up or down.
- **Silence the singer** cancels *only* the centred lead — the backing band
  survives — which is exactly what centre subtraction does to a real mix.

You can also click **Use my audio** to load any local file (WAV/MP3/M4A/…) and
run the same engine over it. Nothing is uploaded; decoding happens in your
browser.

**File limits (enforced, no silent truncation):** a file is rejected with a
visible error if it's **over 40 MB** (checked *before* any bytes are read) or
decodes to **longer than 6 minutes** (checked *after* decode). Fully decoding
an arbitrarily large file to Float32 PCM can freeze or OOM the tab, so we
refuse it loudly rather than half-load it.

## Run it locally

No build step. Serve the folder over HTTP (an AudioWorklet won't load from a
`file://` URL) and open the page:

```bash
# Python 3
python -m http.server 8127 --directory apps/web-demo
# → http://localhost:8127

# …or Node
npx serve apps/web-demo
```

Requires a current browser with Web Audio `AudioWorklet` support (Chrome,
Edge, Firefox, Safari). If the API is missing, the page shows an explicit
"needs a modern browser" message rather than silently failing.

## How it works

```
app.js  ──load──▶  AudioWorkletNode ("pitch-worklet")
   │                       │
   │  port messages        │  runs on the audio thread:
   │  (pitch / vocal /      │    SimpleFilter → SoundTouch (WSOLA pitch shift)
   │   seek / play / pause) │    → mid/side centre subtraction
   ▼                       ▼
 sliders                ctx.destination  → speakers
```

- `index.html` — markup and the studio UI.
- `styles.css` — the dark "studio" theme; the Song-key fader is a custom-styled
  `<input type=range>`.
- `app.js` — page controller: synthesizes the demo, decodes uploads, bridges
  sliders to the worklet, reflects playback state.
- `pitch-worklet.js` — the `AudioWorkletProcessor`. All DSP lives here.
- `vendor/soundtouchjs/` — the pitch-shift library, vendored with its license.

## Security posture (CSP + no external fonts)

This page handles **local files** and **mic audio**, so it ships a strict
same-origin policy and pulls **zero** external resources:

- **No font CDN.** The earlier Google Fonts (`Inter`/`Sora`) link is gone;
  type now uses a **system font stack** — `system-ui, -apple-system, "Segoe
  UI", Roboto, …` for UI/display and a `ui-monospace, "Cascadia Code", "SF
  Mono", …` stack for code. No third-party request, same studio look.
- **A strict `Content-Security-Policy`** `<meta>` tag locks the origin set to
  what the demo actually uses:

  ```
  default-src 'self'; script-src 'self'; style-src 'self';
  img-src 'self' data:; media-src blob:; connect-src 'self';
  font-src 'self'; object-src 'none'; base-uri 'self'; form-action 'none'
  ```

  `script-src 'self'` covers `app.js` + the worklet (both same-origin ES
  modules — there is **no inline JS**); `style-src 'self'` covers
  `styles.css` (no inline `<style>` / `style=""` from markup — the vocal-fill
  and meter are set via the CSSOM `.style` property, which CSP permits);
  `img-src … data:` allows the inline SVG favicon; `media-src blob:` and
  `connect-src 'self'` cover decoded-audio blobs and the worklet module.
  Mic capture uses `getUserMedia` (not a network fetch), so no extra
  `connect-src` origin is needed.

## Honesty note (GPL / LGPL)

This browser preview uses **SoundTouch (WSOLA)**, *not* the desktop app's
rubberband engine, so it demonstrates the *experience* rather than producing
byte-identical output. The desktop app is where **preview == export** is
proven.

We use **SoundTouchJS (LGPL-2.1)** and deliberately **avoid `ffmpeg.wasm`**,
which is GPL and would contaminate this repo. See
[`vendor/soundtouchjs/README.md`](./vendor/soundtouchjs/README.md) for the
exact version, source, and license.

## Links

- Download (Windows): <https://github.com/aayushman-singh/karaoke-buddy/releases/download/v0.3.0/KaraokeBuddy.exe>
- Source repository: <https://github.com/aayushman-singh/karaoke-buddy>
