# Karaoke Buddy — web demo (Surface B)

A fully static, try-before-you-download preview. Open any audio, drop the key in
whole semitones without changing tempo, turn the original singer down, and
auto-match your key by singing a note. All DSP runs in a Web Audio
`AudioWorklet`; the page ships no build step and no third-party runtime.

## Run it

The worklet module and the strict Content-Security-Policy mean this must be
**served over HTTP** — opening `index.html` from `file://` will not work.

```bash
cd web
python -m http.server 8777
# then open http://localhost:8777/
```

## Files

| File | Role |
| --- | --- |
| `index.html` | Single page. Hero, console, source picker, status line, footer, unsupported-browser gate. |
| `styles.css` | The "bold & joyful" skin — shares the desktop palette, system-font stack only (CSP-safe). |
| `app.js` | Controller: state, Web Audio graph, synth demo, file load/validate, mic "Match my key". |
| `pitch-worklet.js` | DSP on the audio thread: WSOLA-style pitch shift (tempo-preserving) + center-channel vocal reduction. |

## Behaviour preserved from the cited source

- Key slider **−6…+6** (default 0); vocal slider **0…100%** (default 0). Both
  read in plain words (`Higher by 2 keys`, `Singer turned down 60%`).
- Transport is **disabled until the demo is ready**.
- **Match my key**: requests the mic, listens ~2 s, runs autocorrelation, and on
  success shifts the slider with a status like `Heard ~G3 (196 Hz) → shifting +2.`
  On a failed read it shows a visible error and **does not move the slider**.
- A rejected file (> 40 MB, > 6 min, or undecodable) surfaces a visible error and
  **restores the demo song**.
- The single `#status` line is the only message channel and flips to `.is-error`
  on any failure — nothing fails silently.

## Honesty note

The in-browser pitch shift uses a SoundTouch-style WSOLA engine. The desktop app
uses a higher-quality engine (rubberband), so the desktop result sounds a little
cleaner than this preview.
