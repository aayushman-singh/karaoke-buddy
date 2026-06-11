/*
 * app.js — Karaoke Buddy browser preview controller
 * ------------------------------------------------------------------
 * Owns the page: builds the audio graph, synthesizes the demo track,
 * wires the sliders to the AudioWorklet, and reflects playback state in
 * the UI. All DSP lives in pitch-worklet.js; this file is glue + UX.
 *
 * Failure stance (per repo policy): no silent degradation. If the
 * environment can't run the engine we surface an explicit, visible error
 * instead of quietly doing something half-right.
 */

// ── DOM handles ──────────────────────────────────────────────────────
const $ = (id) => document.getElementById(id);

const els = {
  unsupported: $("unsupported"),
  stage: $("stage"),
  play: $("playToggle"),
  scrub: $("scrub"),
  timeNow: $("timeNow"),
  timeTotal: $("timeTotal"),
  trackLabel: $("trackLabel"),
  keySlider: $("keySlider"),
  keyValue: $("keyValue"),
  vocalSlider: $("vocalSlider"),
  vocalValue: $("vocalValue"),
  useDemo: $("useDemo"),
  fileInput: $("fileInput"),
  status: $("status"),
  matchKey: $("matchKey"),
  matchMeter: $("matchMeter"),
  matchMeterFill: $("matchMeterFill"),
};

// ── Upload guardrails (explicit, no silent truncation) ───────────────
// Enforced BEFORE we read bytes / after we decode. A huge file decoded in
// full can freeze or OOM the tab, so we reject loudly instead.
const MAX_FILE_BYTES = 40 * 1024 * 1024; // 40 MB on disk
const MAX_DURATION_SECONDS = 6 * 60; // 6 minutes after decode

// ── Capability gate (explicit, no fallback) ──────────────────────────
if (typeof AudioWorkletNode === "undefined" || !window.AudioContext) {
  els.unsupported.hidden = false;
  els.stage.setAttribute("aria-hidden", "true");
  throw new Error("AudioWorklet unsupported — preview cannot run.");
}

// ── Engine state ─────────────────────────────────────────────────────
let ctx = null; // AudioContext (created lazily on first interaction)
let workletNode = null; // the pitch-worklet AudioWorkletNode
let totalFrames = 0; // length of the loaded buffer, in frames
let sampleRate = 44100; // updated to ctx.sampleRate once ctx exists
let isPlaying = false;
let scrubbing = false; // true while the user drags the seek bar

// ── Source state machine ─────────────────────────────────────────────
// Replaces the old `demoRequested` boolean, which conflated "has the user
// asked for the demo" with "is *any* buffer loaded". That conflation was
// the data-loss bug: picking a file before first Play left demoRequested
// false, so the first Play happily synthesized the demo OVER the file.
//
//   loadedSource — what's *intended* to be in the engine right now.
//     'none' : nothing requested yet (fresh page)
//     'demo' : the synthesized demo track
//     'file' : a user-uploaded file
//   bufferReady — has the worklet confirmed a buffer is actually loaded?
//
// First-play priming asks one question only: "is a buffer ready?". A
// successful loadFile() flips loadedSource to 'file' and (on the worklet's
// 'loaded' ack) bufferReady to true — so Play can never clobber a user file.
let loadedSource = "none"; // 'none' | 'demo' | 'file'
let bufferReady = false;

// Resolves once the worklet reports a buffer is loaded and ready to play.
let readyResolve = null;
let readyPromise = new Promise((res) => (readyResolve = res));
function resetReady() {
  readyPromise = new Promise((res) => (readyResolve = res));
}

// ── Status helpers ───────────────────────────────────────────────────
function setStatus(text, isError = false) {
  els.status.textContent = text;
  els.status.classList.toggle("is-error", isError);
  if (isError) console.error(`[karaoke-buddy] ${text}`);
}

function formatTime(seconds) {
  if (!isFinite(seconds)) return "0:00";
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  return `${m}:${String(s).padStart(2, "0")}`;
}

/*
 * Single error path for every user-triggered async action (play, load,
 * mic). Previously a rejected ctx.audioWorklet.addModule() or worklet
 * import vanished and the UI just sat there looking idle despite the
 * "no silent degradation" promise. Now: one wrapper, one visible failure.
 *
 * `fallbackMsg` is shown when the thrown error carries no message of its
 * own. The action's own `await`ed code is free to throw — that's the point.
 */
async function runAction(fallbackMsg, fn) {
  try {
    await fn();
  } catch (err) {
    const detail = err && err.message ? err.message : fallbackMsg;
    setStatus(detail, true);
    console.error("[karaoke-buddy]", err);
    throw err; // let callers disable their specific control if they need to
  }
}

// ── Demo-track synthesis ─────────────────────────────────────────────
/*
 * We never ship copyrighted audio. Instead we render a self-contained
 * ~24 s stereo clip from oscillators so BOTH controls are demonstrable:
 *
 *   • A warm chord arpeggio panned HARD LEFT/RIGHT — the "backing band".
 *     Because it lives in the sides, centre-subtraction leaves it intact.
 *   • A clear lead "vocal" melody panned DEAD CENTRE — identical in L and
 *     R. The mid/side remover cancels exactly this, so "Silence the
 *     singer" is audibly effective.
 *
 * The result proves the pitch slider (shifts everything) and the vocal
 * slider (removes only the centre) independently.
 */
function synthesizeDemo(audioCtx) {
  const seconds = 24;
  const sr = audioCtx.sampleRate;
  const length = Math.floor(seconds * sr);
  const buffer = audioCtx.createBuffer(2, length, sr);
  const left = buffer.getChannelData(0);
  const right = buffer.getChannelData(1);

  // Helper: pleasant, slightly rounded tone (sine + a touch of 3rd harm).
  const tone = (t, freq) =>
    Math.sin(2 * Math.PI * freq * t) +
    0.18 * Math.sin(2 * Math.PI * freq * 3 * t);

  // A4-based equal temperament so the demo is musically in tune.
  const note = (semisFromA4) => 440 * Math.pow(2, semisFromA4 / 12);

  // Backing arpeggio: A minor 7 (A C E G), one note every 1/3 s.
  // Hard-panned by alternating L/R so it reads as a stereo "band".
  const arp = [note(0), note(3), note(7), note(10)]; // A C E G
  const arpStep = 1 / 3;

  // Lead "vocal": a singable melody over the chord, centred.
  // Phrase of scale degrees (semitones from A4), looped.
  const melody = [0, 2, 3, 5, 7, 5, 3, 2, 0, -2, 0, 3, 7, 5, 3, 0];
  const melStep = 0.75; // a note every 0.75 s

  // Soft attack/decay so notes don't click.
  const env = (localT, dur) => {
    const a = 0.012;
    const r = 0.08;
    if (localT < a) return localT / a;
    if (localT > dur - r) return Math.max(0, (dur - localT) / r);
    return 1;
  };

  for (let i = 0; i < length; i++) {
    const t = i / sr;

    // --- Backing arpeggio, hard-panned --------------------------------
    const arpIdx = Math.floor(t / arpStep) % arp.length;
    const arpLocal = t % arpStep;
    const arpFreq = arp[arpIdx] / 2; // an octave down: a bassy bed
    const arpEnv = env(arpLocal, arpStep) * 0.22;
    const arpSample = tone(t, arpFreq) * arpEnv;
    // Alternate hard L / hard R every step for an obvious stereo image.
    const onLeft = arpIdx % 2 === 0;

    // --- Lead vocal, centred ------------------------------------------
    const melIdx = Math.floor(t / melStep) % melody.length;
    const melLocal = t % melStep;
    const melFreq = note(melody[melIdx] + 12); // an octave up: clearly lead
    // Light vibrato to make it feel "sung".
    const vib = 1 + 0.006 * Math.sin(2 * Math.PI * 5.5 * t);
    const melEnv = env(melLocal, melStep) * 0.32;
    const lead = tone(t, melFreq * vib) * melEnv;

    // --- Mix ----------------------------------------------------------
    const l = (onLeft ? arpSample : 0) + lead;
    const r = (onLeft ? 0 : arpSample) + lead;

    // Gentle soft-clip to keep peaks polite.
    left[i] = Math.tanh(l);
    right[i] = Math.tanh(r);
  }

  return buffer;
}

// ── AudioContext + worklet bootstrap ─────────────────────────────────
async function ensureContext() {
  if (ctx) return ctx;
  ctx = new AudioContext();
  sampleRate = ctx.sampleRate;

  // Load the worklet module. A failure here is fatal and surfaced.
  await ctx.audioWorklet.addModule("pitch-worklet.js");

  workletNode = new AudioWorkletNode(ctx, "pitch-worklet", {
    numberOfInputs: 0,
    numberOfOutputs: 1,
    outputChannelCount: [2],
  });
  workletNode.connect(ctx.destination);
  workletNode.port.onmessage = (e) => handleWorkletMessage(e.data);

  // Push current control positions so the engine starts in sync.
  postPitch(parseInt(els.keySlider.value, 10));
  postVocal(parseInt(els.vocalSlider.value, 10));

  return ctx;
}

function handleWorkletMessage(msg) {
  switch (msg.type) {
    case "loaded":
      totalFrames = msg.frames;
      bufferReady = true; // a real buffer is now in the engine
      els.timeTotal.textContent = formatTime(totalFrames / sampleRate);
      els.play.disabled = false;
      setStatus("Ready — press play and try the sliders.");
      if (readyResolve) readyResolve();
      break;
    case "progress":
      if (!scrubbing) {
        const ratio = totalFrames ? msg.frame / totalFrames : 0;
        els.scrub.value = String(Math.round(ratio * 1000));
        els.timeNow.textContent = formatTime(msg.frame / sampleRate);
      }
      break;
    case "ended":
      setPlaying(false);
      els.scrub.value = "0";
      els.timeNow.textContent = "0:00";
      break;
    case "error":
      setStatus(msg.message, true);
      break;
  }
}

// ── Loading audio into the worklet ───────────────────────────────────
function loadBufferIntoWorklet(audioBuffer) {
  // Swapping the buffer underneath a *playing* worklet used to desync
  // state: the worklet kept playing=true and could start the new buffer
  // while the button still showed Play. Lockstep fix — always stop first:
  //   • tell the worklet to pause (the worklet's 'load' handler also resets
  //     playing=false, so this is double-locked), and
  //   • reflect Paused in the UI immediately.
  workletNode.port.postMessage({ type: "pause" });
  setPlaying(false);

  // A new buffer is in flight; it is NOT ready until the worklet acks.
  bufferReady = false;

  // De-interleave to two plain Float32Arrays and transfer (zero-copy).
  const left = audioBuffer.getChannelData(0).slice();
  const right =
    audioBuffer.numberOfChannels > 1
      ? audioBuffer.getChannelData(1).slice()
      : left.slice();

  workletNode.port.postMessage(
    { type: "load", left: left.buffer, right: right.buffer },
    [left.buffer, right.buffer]
  );
}

async function loadDemo() {
  await ensureContext();
  resetReady();
  setStatus("Synthesizing demo track…");
  const buffer = synthesizeDemo(ctx);
  loadBufferIntoWorklet(buffer);
  loadedSource = "demo";
  els.trackLabel.textContent = "Demo track — synthesized in-browser";
}

async function loadFile(file) {
  await ensureContext();

  // Guardrail 1 — size, checked BEFORE we read a single byte. A multi-
  // hundred-MB file fully decoded to Float32 PCM can OOM the tab; we refuse
  // it loudly rather than freeze. No silent truncation.
  if (file.size > MAX_FILE_BYTES) {
    const mb = (file.size / (1024 * 1024)).toFixed(0);
    throw new Error(
      `"${file.name}" is ${mb} MB — over the ${MAX_FILE_BYTES / (1024 * 1024)} MB limit. Trim it and try again.`
    );
  }

  resetReady();
  setStatus(`Decoding ${file.name}…`);

  // decodeAudioData failures (corrupt / unsupported codec) are surfaced by
  // the caller's central error path — no local swallow, no fallback to demo.
  const arrayBuffer = await file.arrayBuffer();
  const audioBuffer = await ctx.decodeAudioData(arrayBuffer);

  // Guardrail 2 — duration, checked AFTER decode (we only know real length
  // once decoded). Reject over-long clips so the engine isn't choked.
  if (audioBuffer.duration > MAX_DURATION_SECONDS) {
    const mins = (audioBuffer.duration / 60).toFixed(1);
    throw new Error(
      `"${file.name}" is ${mins} min — over the ${MAX_DURATION_SECONDS / 60}-minute limit for this preview.`
    );
  }

  loadBufferIntoWorklet(audioBuffer);
  loadedSource = "file";
  els.trackLabel.textContent = file.name;
}

// ── Transport ────────────────────────────────────────────────────────
function setPlaying(state) {
  isPlaying = state;
  els.play.classList.toggle("is-playing", state);
  els.play.setAttribute("aria-label", state ? "Pause" : "Play");
}

async function togglePlay() {
  await runAction("Couldn't start audio — see console for details.", async () => {
    await ensureContext();
    if (ctx.state === "suspended") await ctx.resume();

    if (isPlaying) {
      workletNode.port.postMessage({ type: "pause" });
      setPlaying(false);
      return;
    }

    // First-play priming asks ONE question: is a buffer ready? If the user
    // already picked a file (bufferReady true / pending), we never synth the
    // demo over it. Only a truly empty engine gets the demo.
    await primeIfEmpty();
    await readyPromise;
    workletNode.port.postMessage({ type: "play" });
    setPlaying(true);
  });
}

// ── Control → worklet bridges ────────────────────────────────────────
function postPitch(semitones) {
  if (workletNode) workletNode.port.postMessage({ type: "pitch", value: semitones });
}
function postVocal(percent) {
  if (workletNode) workletNode.port.postMessage({ type: "vocal", value: percent });
}

// Mirror the desktop's _pitch_label() vocabulary exactly.
function keyLabel(semitones) {
  if (semitones === 0) return "Normal key";
  const direction = semitones > 0 ? "Higher" : "Lower";
  const n = Math.abs(semitones);
  return `${direction} by ${n} ${n === 1 ? "key" : "keys"}`;
}

// Slider bounds, read once from the DOM so JS and HTML can't drift.
const KEY_MIN = parseInt(els.keySlider.min, 10); // -6
const KEY_MAX = parseInt(els.keySlider.max, 10); // +6

/*
 * The single key-shift entry point. BOTH the manual slider and the
 * "Match my key" feature funnel through here, so there's exactly one path
 * that (a) clamps to the slider's range, (b) updates the slider position,
 * (c) repaints the label, and (d) drives the worklet. No second code path
 * to fall out of sync.
 */
function applyKeyShift(semitones) {
  const clamped = Math.max(KEY_MIN, Math.min(KEY_MAX, Math.round(semitones)));
  els.keySlider.value = String(clamped);
  els.keyValue.textContent = keyLabel(clamped);
  postPitch(clamped);
  return clamped;
}

// Lazily put *something* in the engine on the first user gesture (browser
// autoplay policy forbids audio before a gesture, so all AudioContext work
// is deferred until then). Crucially this is keyed on the SOURCE STATE, not
// a one-shot boolean: if the user already loaded a file ('file') or the demo
// ('demo'), we leave it alone. Only 'none' triggers the demo synth.
async function primeIfEmpty() {
  if (loadedSource !== "none") return;
  await loadDemo();
}

// ── Wiring ───────────────────────────────────────────────────────────
els.play.addEventListener("click", togglePlay);

els.keySlider.addEventListener("input", () => {
  const semis = parseInt(els.keySlider.value, 10); // snaps to integers (step=1)
  els.keyValue.textContent = keyLabel(semis);
  postPitch(semis);
});

// Wire the Match-my-key button (definition lives in the mic section below).
els.matchKey.addEventListener("click", matchMyKey);

els.vocalSlider.addEventListener("input", () => {
  const pct = parseInt(els.vocalSlider.value, 10);
  els.vocalValue.textContent = `${pct}%`;
  // Paint the WebKit fill (Firefox uses ::-moz-range-progress automatically).
  els.vocalSlider.style.setProperty("--fill", `${pct}%`);
  postVocal(pct);
});

// Seek bar: pause progress updates while dragging, commit on release.
els.scrub.addEventListener("input", () => {
  scrubbing = true;
  const ratio = parseInt(els.scrub.value, 10) / 1000;
  els.timeNow.textContent = formatTime((ratio * totalFrames) / sampleRate);
});
els.scrub.addEventListener("change", () => {
  const ratio = parseInt(els.scrub.value, 10) / 1000;
  if (workletNode) {
    workletNode.port.postMessage({ type: "seek", frame: ratio * totalFrames });
  }
  scrubbing = false;
});

// Source picker — "Synth demo" explicitly (re)loads the demo. Selecting it
// sets loadedSource='demo' via loadDemo(), coherent with the state machine.
els.useDemo.addEventListener("click", () => {
  els.useDemo.classList.add("chip--active");
  els.useDemo.setAttribute("aria-pressed", "true");
  runAction("Couldn't load the demo track.", () => loadDemo());
});
// "Use my audio" — a successful loadFile() flips loadedSource to 'file', so
// a subsequent first Play can never overwrite it with the demo. A rejected
// load (too big / too long / undecodable) surfaces visibly and leaves state
// untouched; we do NOT silently fall back to the demo.
els.fileInput.addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  if (!file) return;
  els.useDemo.classList.remove("chip--active");
  els.useDemo.setAttribute("aria-pressed", "false");
  runAction(`Could not load "${file.name}". Try a WAV/MP3/M4A file.`, () =>
    loadFile(file)
  ).catch(() => {
    // Load failed and nothing usable is in the engine for this pick. Restore
    // the demo chip as the active selection so the picker reflects reality.
    if (loadedSource !== "file") {
      els.useDemo.classList.add("chip--active");
      els.useDemo.setAttribute("aria-pressed", "true");
    }
  });
  // Allow re-picking the same file later (change won't fire on identical value).
  e.target.value = "";
});
// Allow keyboard activation of the file <label> chip.
document.querySelector(".chip--file").addEventListener("keydown", (e) => {
  if (e.key === "Enter" || e.key === " ") {
    e.preventDefault();
    els.fileInput.click();
  }
});

// ═════════════════════════════════════════════════════════════════════
// "Match my key" — mic auto-key-detect
// ─────────────────────────────────────────────────────────────────────
// One tap: the user hums/sings a sustained note for ~2 s; we detect their
// fundamental (f0) from the mic, map it to the nearest musical note, and
// shift the SONG so its reference pitch lands as close as possible to that
// note — moving the backing track into the user's comfortable register.
//
// Honesty stance: we DETECT, we don't guess. If the input is too quiet or
// too non-periodic to trust, we reject with a visible message rather than
// snapping the slider to a number we made up. No fallback to "probably 0".
//
// Pitch-detection method: time-domain AUTOCORRELATION (clean-room).
//   A periodic signal x[n] with period P correlates strongly with itself
//   shifted by P samples. We compute the normalized autocorrelation across
//   a band of candidate lags, find the strongest peak away from lag 0, and
//   take f0 = sampleRate / peakLag. Parabolic interpolation around the peak
//   refines the lag to sub-sample precision. We also gate on RMS (must be
//   loud enough) and on peak strength (must be periodic enough) — those two
//   gates are the whole reason this can fail loudly instead of lying.

const MATCH_CAPTURE_MS = 2000; // listening window length
const MATCH_MIN_RMS = 0.01; // below this the mic is effectively silent
const MATCH_MIN_CLARITY = 0.9; // normalized autocorr peak must clear this
const MATCH_F0_MIN = 70; // Hz — below ~C2, almost certainly not a sung note
const MATCH_F0_MAX = 1000; // Hz — above ~B5, treat as noise for this UX

// The song's reference pitch. The synth demo and most pop vocals sit around
// A3 (220 Hz); we anchor "best fit" to that. Shifting so this reference
// lands nearest the user's detected note is a simple, honest definition of
// "fits their range" that we can show the user verbatim.
const SONG_REFERENCE_HZ = 220; // A3

let micActive = false; // re-entrancy guard for the button

const NOTE_NAMES = [
  "C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B",
];

// Convert a frequency to a note name + octave (e.g. 196 Hz → "G3").
// MIDI 69 == A4 == 440 Hz; each semitone is a factor of 2^(1/12).
function hzToNoteName(hz) {
  const midi = Math.round(69 + 12 * Math.log2(hz / 440));
  const name = NOTE_NAMES[((midi % 12) + 12) % 12];
  const octave = Math.floor(midi / 12) - 1;
  return `${name}${octave}`;
}

// Whole-semitone distance between two frequencies (signed, rounded).
function semitonesBetween(fromHz, toHz) {
  return Math.round(12 * Math.log2(toHz / fromHz));
}

/**
 * Estimate the fundamental frequency of a mono Float32 frame via normalized
 * autocorrelation. Returns { hz, clarity, rms } where clarity ∈ [0,1] is the
 * strength of the best periodic peak. Returns hz=null when no peak is found
 * within the searched lag band (the caller decides if that's a failure).
 *
 * @param {Float32Array} buf  - time-domain samples
 * @param {number} sr         - sample rate of `buf`
 */
function detectPitchAutocorr(buf, sr) {
  const n = buf.length;

  // --- Loudness gate: RMS over the window ---------------------------------
  let sumSq = 0;
  for (let i = 0; i < n; i++) sumSq += buf[i] * buf[i];
  const rms = Math.sqrt(sumSq / n);
  if (rms < MATCH_MIN_RMS) return { hz: null, clarity: 0, rms };

  // --- Search only musically plausible lags -------------------------------
  // lag = sr / f0, so the f0 band [MIN,MAX] maps to a lag band. Clamp the
  // max lag to half the window so the correlation has enough overlap.
  const minLag = Math.floor(sr / MATCH_F0_MAX);
  const maxLag = Math.min(Math.floor(sr / MATCH_F0_MIN), Math.floor(n / 2));

  // Energy at lag 0 normalizes the correlation into [-1, 1].
  let zeroLagEnergy = 0;
  for (let i = 0; i < n; i++) zeroLagEnergy += buf[i] * buf[i];
  if (zeroLagEnergy === 0) return { hz: null, clarity: 0, rms };

  let bestLag = -1;
  let bestCorr = 0;
  for (let lag = minLag; lag <= maxLag; lag++) {
    let corr = 0;
    const limit = n - lag;
    for (let i = 0; i < limit; i++) corr += buf[i] * buf[i + lag];
    // Normalize by lag-0 energy; for a clean periodic signal this nears 1.
    const norm = corr / zeroLagEnergy;
    if (norm > bestCorr) {
      bestCorr = norm;
      bestLag = lag;
    }
  }
  if (bestLag < 0) return { hz: null, clarity: 0, rms };

  // --- Parabolic interpolation for sub-sample lag precision ---------------
  // Fit a parabola through the correlation at (bestLag-1, bestLag, bestLag+1)
  // and take its vertex; this sharpens the f0 estimate considerably.
  let refinedLag = bestLag;
  if (bestLag > minLag && bestLag < maxLag) {
    const corrAt = (lag) => {
      let c = 0;
      const limit = n - lag;
      for (let i = 0; i < limit; i++) c += buf[i] * buf[i + lag];
      return c / zeroLagEnergy;
    };
    const a = corrAt(bestLag - 1);
    const b = bestCorr;
    const c = corrAt(bestLag + 1);
    const denom = a - 2 * b + c;
    if (denom !== 0) refinedLag = bestLag + (0.5 * (a - c)) / denom;
  }

  return { hz: sr / refinedLag, clarity: bestCorr, rms };
}

// Live level meter while listening. Driven from the analyser time-domain
// data each animation frame; tears down with the mic.
function paintLevel(fraction) {
  const pct = Math.max(0, Math.min(1, fraction)) * 100;
  els.matchMeterFill.style.width = `${pct}%`;
}

/**
 * Capture ~MATCH_CAPTURE_MS of mic audio, run autocorrelation over the
 * window, and resolve with a confident { hz, noteName } — or reject with an
 * explicit Error if permission is denied or no clear note is heard.
 *
 * The mic stream is ALWAYS torn down (finally) so we never leave it hot.
 */
async function captureUserPitch() {
  if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
    throw new Error("This browser can't access the microphone.");
  }

  // getUserMedia rejects on permission-denied; that bubbles to runAction.
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });

  // Reuse the playback AudioContext so sample rates line up.
  await ensureContext();
  const micCtx = ctx;
  const sourceNode = micCtx.createMediaStreamSource(stream);
  const analyser = micCtx.createAnalyser();
  analyser.fftSize = 2048; // 2048-sample time-domain window per read
  sourceNode.connect(analyser);
  // NOTE: analyser is deliberately NOT connected to destination — we don't
  // want to monitor the mic back through the speakers (feedback).

  const frame = new Float32Array(analyser.fftSize);
  const estimates = []; // collected per-frame f0 estimates that pass gates
  const start = performance.now();
  let rafId = 0;
  let deadline = 0;

  try {
    setStatus("Listening… hum or sing one steady note.");

    await new Promise((resolve) => {
      // Hard deadline independent of requestAnimationFrame. Browsers throttle
      // or fully pause RAF for backgrounded/hidden tabs, so an RAF-only stop
      // condition can hang forever — leaving the mic hot. This setTimeout
      // guarantees we always resolve (and therefore tear down) on time.
      deadline = setTimeout(resolve, MATCH_CAPTURE_MS + 250);
      const tick = () => {
        analyser.getFloatTimeDomainData(frame);

        const { hz, clarity, rms } = detectPitchAutocorr(frame, micCtx.sampleRate);
        // Feed the level meter off RMS (scaled so quiet→0, loud→1-ish).
        paintLevel(rms * 8);

        // Only keep estimates that clear BOTH gates — loud and periodic.
        if (
          hz !== null &&
          clarity >= MATCH_MIN_CLARITY &&
          hz >= MATCH_F0_MIN &&
          hz <= MATCH_F0_MAX
        ) {
          estimates.push(hz);
        }

        if (performance.now() - start < MATCH_CAPTURE_MS) {
          rafId = requestAnimationFrame(tick);
        } else {
          clearTimeout(deadline);
          resolve();
        }
      };
      rafId = requestAnimationFrame(tick);
    });
  } finally {
    if (deadline) clearTimeout(deadline);
    // Tear EVERYTHING down — stop the RAF loop, disconnect nodes, and most
    // importantly stop every mic track so the browser's "recording" dot goes
    // away. Leaving the mic hot would be a privacy bug.
    if (rafId) cancelAnimationFrame(rafId);
    try {
      sourceNode.disconnect();
    } catch {
      /* node may already be GC-eligible; disconnect is best-effort cleanup */
    }
    stream.getTracks().forEach((t) => t.stop());
    paintLevel(0);
  }

  // Need a quorum of confident frames; otherwise it was noise/silence.
  if (estimates.length < 5) {
    throw new Error("Didn't catch a clear note — try again, louder and steadier.");
  }

  // Median is robust to the odd octave-jump or transient outlier.
  estimates.sort((a, b) => a - b);
  const medianHz = estimates[Math.floor(estimates.length / 2)];
  return { hz: medianHz, noteName: hzToNoteName(medianHz) };
}

/**
 * Top-level "Match my key" handler. Wired to the button. Drives the SAME
 * pitch path as the slider via applyKeyShift(), so the engine, slider, and
 * label stay perfectly consistent. Shows the user exactly what it heard.
 */
async function matchMyKey() {
  if (micActive) return; // ignore double-taps mid-capture
  micActive = true;
  els.matchKey.classList.add("is-listening");
  els.matchKey.setAttribute("aria-busy", "true");
  els.matchMeter.hidden = false;

  try {
    await runAction("Microphone unavailable — check permissions and try again.", async () => {
      const { hz, noteName } = await captureUserPitch();

      // "Best fit": shift the song so its reference pitch lands nearest the
      // user's detected note, then clamp into the slider's ±6 range. We show
      // the raw suggestion AND the applied value when clamping bit.
      const suggested = semitonesBetween(SONG_REFERENCE_HZ, hz);
      const applied = applyKeyShift(suggested);

      const heardHz = hz.toFixed(0);
      const sign = applied > 0 ? `+${applied}` : `${applied}`;
      let msg = `Heard ~${noteName} (${heardHz} Hz) → shifting ${sign}.`;
      if (applied !== suggested) {
        // The honest-truth case: we wanted more than the slider allows.
        const want = suggested > 0 ? `+${suggested}` : `${suggested}`;
        msg = `Heard ~${noteName} (${heardHz} Hz) → wanted ${want}, capped at ${sign}.`;
      }
      setStatus(msg);
    });
  } catch {
    // runAction already surfaced the message + logged; nothing to add here.
    // We swallow only to keep the button-reset code in finally clean.
  } finally {
    micActive = false;
    els.matchKey.classList.remove("is-listening");
    els.matchKey.removeAttribute("aria-busy");
    els.matchMeter.hidden = true;
  }
}

// ── First paint ──────────────────────────────────────────────────────
els.keyValue.textContent = keyLabel(0);
els.vocalValue.textContent = "0%";
setStatus("Click play to start — the demo track loads on first interaction.");
els.play.disabled = false;

// If the user reaches for a slider before pressing play, we still need a
// buffer in the engine so they hear the change. primeIfEmpty() only loads
// the demo when the engine is empty, so it never clobbers a chosen file.
const primeOnFirstFiddle = () =>
  runAction("Couldn't prepare the audio engine.", () => primeIfEmpty());
els.keySlider.addEventListener("input", primeOnFirstFiddle, { once: true });
els.vocalSlider.addEventListener("input", primeOnFirstFiddle, { once: true });
