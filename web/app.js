/* app.js — Surface B controller (ES module, CSP-safe).
 *
 * Single page, no routing. Owns UI state, the Web Audio graph, the synth demo,
 * file loading, and the mic "Match my key" flow. The worklet does the DSP.
 *
 * Failure stance: loud and visible. Every dead-end flips the single #status
 * line; nothing fails silently and the slider never moves on a failed match.
 */

'use strict';

// ---------- human-language labels (identical semantics to desktop _pitch_label) ----------
function pitchLabel(semitones) {
  if (semitones === 0) return 'Normal key';
  const direction = semitones > 0 ? 'Higher' : 'Lower';
  const abs = Math.abs(semitones);
  return `${direction} by ${abs} ${abs === 1 ? 'key' : 'keys'}`;
}
function vocalLabel(pct) {
  if (pct === 0) return 'Singer at full volume';
  if (pct >= 90) return 'Singer almost gone';
  return `Singer turned down ${pct}%`;
}

const NOTE_NAMES = ['C', 'C♯', 'D', 'D♯', 'E', 'F', 'F♯', 'G', 'G♯', 'A', 'A♯', 'B'];
function freqToNote(f) {
  const midi = Math.round(69 + 12 * Math.log2(f / 440));
  const name = NOTE_NAMES[((midi % 12) + 12) % 12];
  const octave = Math.floor(midi / 12) - 1;
  return { midi, label: `${name}${octave}` };
}

// Demo song is built around A — used to resolve "Match my key" into a shift.
const DEMO_ROOT_PC = 9; // A
const MAX_KEY = 6;
const MIN_KEY = -6;

// ---------- element handles ----------
const el = {
  unsupported: document.getElementById('unsupported'),
  play: document.getElementById('playToggle'),
  icPlay: document.querySelector('#playToggle .ic-play'),
  icPause: document.querySelector('#playToggle .ic-pause'),
  cur: document.getElementById('curTime'),
  dur: document.getElementById('durTime'),
  seek: document.getElementById('seekSlider'),
  key: document.getElementById('keySlider'),
  keyRead: document.getElementById('keyReadout'),
  vocal: document.getElementById('vocalSlider'),
  vocalRead: document.getElementById('vocalReadout'),
  match: document.getElementById('matchKey'),
  matchLabel: document.getElementById('matchLabel'),
  matchHint: document.getElementById('matchHint'),
  matchMeter: document.getElementById('matchMeter'),
  matchFill: document.getElementById('matchFill'),
  srcNote: document.getElementById('srcNote'),
  srcSynth: document.getElementById('srcSynth'),
  srcFile: document.getElementById('srcFile'),
  fileInput: document.getElementById('fileInput'),
  status: document.getElementById('status'),
  statusText: document.getElementById('statusText'),
};

// ---------- state ----------
const state = {
  ctx: null,
  node: null,
  ready: false,
  playing: false,
  duration: 0,
  source: 'synth', // 'synth' | 'file'
};

// ---------- status line (single shared channel) ----------
function setStatus(kind, text) {
  el.status.className = 'status ' + (kind === 'error' ? 'is-error' : kind === 'ok' ? '' : 'neutral');
  el.statusText.textContent = text;
}

function setEngineControlsEnabled(enabled) {
  el.play.disabled = !enabled;
  el.seek.disabled = !enabled;
  el.match.disabled = !enabled;
  el.srcSynth.disabled = !enabled;
  el.srcFile.disabled = !enabled;
  el.fileInput.disabled = !enabled;
}

function fmtTime(sec) {
  if (!isFinite(sec)) sec = 0;
  const s = Math.floor(sec);
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
}

function updateRangeFill(input) {
  const min = +input.min, max = +input.max, val = +input.value;
  const pct = ((val - min) / (max - min)) * 100;
  input.classList.add('filled');
  input.style.setProperty('--pct', pct + '%');
}

// ---------- feature gate ----------
function supported() {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  return !!(Ctx && window.AudioWorkletNode && 'audioWorklet' in Ctx.prototype);
}

// ---------- synth demo (stereo: centered lead + detuned side backing) ----------
function buildDemo(sampleRate) {
  const dur = 16;
  const N = Math.floor(dur * sampleRate);
  const left = new Float32Array(N);
  const right = new Float32Array(N);

  // chord pad (A minor → F → C → G), one chord every 4s; detuned per channel so
  // it lives in the stereo "sides" and survives center-channel vocal reduction.
  const chords = [
    [220.0, 261.63, 329.63], // Am
    [174.61, 220.0, 261.63], // F
    [261.63, 329.63, 392.0], // C
    [196.0, 246.94, 392.0],  // G
  ];
  // A-minor-pentatonic lead melody (centered = the "singer"), 0.5s per step.
  const melody = [440, 392, 329.63, 392, 440, 523.25, 440, 392,
                  329.63, 293.66, 261.63, 293.66, 329.63, 392, 329.63, 293.66];

  for (let i = 0; i < N; i++) {
    const t = i / sampleRate;
    const chord = chords[Math.floor(t / 4) % chords.length];
    let padL = 0, padR = 0;
    for (const f of chord) {
      padL += Math.sin(2 * Math.PI * f * t);
      padR += Math.sin(2 * Math.PI * f * 1.004 * t + 0.5); // detune + phase → stereo width
    }
    padL /= chord.length * 3.2;
    padR /= chord.length * 3.2;

    const step = Math.floor(t / 0.5) % melody.length;
    const fm = melody[step];
    const local = (t % 0.5) / 0.5;
    const env = Math.sin(Math.PI * local); // soft per-note envelope
    const lead = 0.42 * env * (Math.sin(2 * Math.PI * fm * t) + 0.3 * Math.sin(4 * Math.PI * fm * t));

    left[i] = padL + lead;
    right[i] = padR + lead;
  }
  return { left, right, sampleRate, duration: dur };
}

// ---------- audio graph ----------
// The AudioContext is constructed at boot (starts 'suspended' — no gesture
// needed) so the demo is synthesised at the real device sample rate. Only
// resume() waits for the first user gesture.
async function initEngine() {
  const Ctx = window.AudioContext || window.webkitAudioContext;
  state.ctx = new Ctx();
  await state.ctx.audioWorklet.addModule('pitch-worklet.js');
  state.node = new AudioWorkletNode(state.ctx, 'pitch-processor', { outputChannelCount: [2] });
  state.node.port.onmessage = (e) => {
    if (e.data.type === 'pos') onPosition(e.data.pos);
  };
  state.node.connect(state.ctx.destination);
  pushParams();
}

// load a freshly built/decoded buffer into the node
function loadBuffer(buf) {
  setPlaying(false);
  state.duration = buf.duration;
  el.dur.textContent = fmtTime(buf.duration);
  el.cur.textContent = '0:00';
  el.seek.value = '0';
  updateRangeFill(el.seek);
  state.node.port.postMessage(
    { type: 'load', left: buf.left, right: buf.right, sampleRate: buf.sampleRate, duration: buf.duration },
    [buf.left.buffer, buf.right.buffer],
  );
}

function pushParams() {
  if (!state.node) return;
  const semis = +el.key.value;
  const vocal = +el.vocal.value / 100;
  state.node.port.postMessage({ type: 'params', pitchRatio: Math.pow(2, semis / 12), vocalAmount: vocal });
}

function setPlaying(on) {
  state.playing = on;
  el.icPlay.toggleAttribute('hidden', on);
  el.icPause.toggleAttribute('hidden', !on);
  el.play.setAttribute('aria-label', on ? 'Pause' : 'Play');
  if (state.node) state.node.port.postMessage({ type: 'play', playing: on });
}

function onPosition(sec) {
  if (state.duration > 0) {
    el.seek.value = String(Math.round((sec / state.duration) * 1000));
    updateRangeFill(el.seek);
  }
  el.cur.textContent = fmtTime(sec);
}

// ---------- transport ----------
el.play.addEventListener('click', async () => {
  if (!state.ready) return;
  if (state.ctx.state === 'suspended') await state.ctx.resume();
  setPlaying(!state.playing);
  if (state.playing) {
    const v = +el.vocal.value;
    setStatus('ok', v === 0 ? 'Playing — sing along!' : 'Playing — original singer turned down.');
  }
});

el.seek.addEventListener('input', () => {
  updateRangeFill(el.seek);
  if (state.node && state.duration > 0) {
    state.node.port.postMessage({ type: 'seek', pos: (+el.seek.value / 1000) * state.duration });
  }
});

// ---------- key + vocal ----------
el.key.addEventListener('input', () => {
  const v = +el.key.value;
  el.keyRead.textContent = pitchLabel(v);
  updateRangeFill(el.key);
  pushParams();
});
el.vocal.addEventListener('input', () => {
  const v = +el.vocal.value;
  el.vocalRead.textContent = vocalLabel(v);
  updateRangeFill(el.vocal);
  pushParams();
  if (state.playing) setStatus('ok', v === 0 ? 'Playing — sing along!' : 'Playing — original singer turned down.');
});

// ---------- source picker ----------
function selectSource(which) {
  state.source = which;
  el.srcSynth.classList.toggle('is-active', which === 'synth');
  el.srcFile.classList.toggle('is-active', which === 'file');
}

el.srcSynth.addEventListener('click', () => {
  if (!state.ready || state.source === 'synth') return;
  selectSource('synth');
  el.srcNote.textContent = 'Demo song';
  loadBuffer(buildDemo(state.ctx.sampleRate));
  setStatus('ok', 'Back to the demo song.');
});

el.srcFile.addEventListener('click', () => {
  if (!state.ready) return;
  el.fileInput.click();
});

el.fileInput.addEventListener('change', async () => {
  const file = el.fileInput.files[0];
  if (!file) return;
  el.fileInput.value = '';
  if (!state.ready) {
    rejectFile('The audio engine is not ready. No change made.');
    return;
  }
  // size gate (40MB)
  if (file.size > 40 * 1024 * 1024) {
    rejectFile('That file is over 40 MB. No change made.');
    return;
  }
  try {
    const data = await file.arrayBuffer();
    const decoded = await state.ctx.decodeAudioData(data);
    if (decoded.duration > 6 * 60) {
      rejectFile('That file is over 6 minutes. No change made.');
      return;
    }
    const left = decoded.getChannelData(0);
    const right = decoded.numberOfChannels > 1 ? decoded.getChannelData(1) : decoded.getChannelData(0);
    selectSource('file');
    el.srcNote.textContent = file.name;
    loadBuffer({ left: Float32Array.from(left), right: Float32Array.from(right), sampleRate: decoded.sampleRate, duration: decoded.duration });
    setStatus('ok', 'Loaded your audio — press play.');
  } catch (err) {
    rejectFile('Couldn’t read that audio file. No change made.');
  }
});

function rejectFile(message) {
  setStatus('error', message);
}

// ---------- Match my key (web-only) ----------
let matching = false;
el.match.addEventListener('click', async () => {
  if (matching) return;
  matching = true;
  setMatchUI('listening');
  setStatus('neutral', 'Listening… sing one steady note.');
  try {
    await runMatch();
  } catch (err) {
    setMatchUI('idle', 'No clear note heard.');
    setStatus('error', 'Didn’t catch a clear note — try again.');
  } finally {
    matching = false;
  }
});

function setMatchUI(stateName, hint) {
  const listening = stateName === 'listening';
  el.match.classList.toggle('is-listening', listening);
  el.matchLabel.textContent = listening ? 'Listening…' : 'Match my key';
  el.matchMeter.hidden = !listening;
  el.matchHint.hidden = listening;
  if (hint) el.matchHint.textContent = hint;
}

async function runMatch() {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const Ctx = window.AudioContext || window.webkitAudioContext;
  const mctx = new Ctx();
  try {
    const src = mctx.createMediaStreamSource(stream);
    const analyser = mctx.createAnalyser();
    analyser.fftSize = 2048;
    src.connect(analyser);
    const frame = new Float32Array(analyser.fftSize);
    const collected = [];
    const t0 = mctx.currentTime;

    await new Promise((resolve) => {
      const tick = () => {
        analyser.getFloatTimeDomainData(frame);
        // live RMS meter
        let rms = 0;
        for (let i = 0; i < frame.length; i++) rms += frame[i] * frame[i];
        rms = Math.sqrt(rms / frame.length);
        el.matchFill.style.width = Math.min(100, Math.round(rms * 280)) + '%';
        collected.push(frame.slice());
        if (mctx.currentTime - t0 >= 2.0) resolve();
        else requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    });

    // use the loudest collected window for detection
    let best = collected[0], bestRms = 0;
    for (const f of collected) {
      let r = 0;
      for (let i = 0; i < f.length; i++) r += f[i] * f[i];
      if (r > bestRms) { bestRms = r; best = f; }
    }
    const f0 = detectPitch(best, mctx.sampleRate);
    if (!f0) throw new Error('no-note');

    const { label } = freqToNote(f0);
    // resolve to the nearest semitone shift that aligns the user's note with the song root
    const userPc = ((Math.round(69 + 12 * Math.log2(f0 / 440)) % 12) + 12) % 12;
    let shift = ((DEMO_ROOT_PC - userPc + 18) % 12) - 6; // wrap into [-6, 6)
    shift = Math.max(MIN_KEY, Math.min(MAX_KEY, shift));

    setMatchUI('idle', 'Got it — your key is set.');
    el.key.value = String(shift);
    el.keyRead.textContent = pitchLabel(shift);
    updateRangeFill(el.key);
    pushParams();
    const sign = shift > 0 ? `+${shift}` : `${shift}`;
    setStatus('ok', `Heard ~${label} (${Math.round(f0)} Hz) → shifting ${sign}.`);
  } finally {
    stream.getTracks().forEach((t) => t.stop());
    mctx.close();
  }
}

// normalized autocorrelation pitch detector (vocal range 80–500 Hz)
function detectPitch(buf, sr) {
  let energy = 0;
  for (let i = 0; i < buf.length; i++) energy += buf[i] * buf[i];
  const rms = Math.sqrt(energy / buf.length);
  if (rms < 0.012) return null; // too quiet to be a sung note

  const minLag = Math.floor(sr / 500);
  const maxLag = Math.floor(sr / 80);
  let bestLag = -1, bestCorr = 0;
  for (let lag = minLag; lag <= maxLag; lag++) {
    let c = 0;
    for (let i = 0; i < buf.length - lag; i++) c += buf[i] * buf[i + lag];
    if (c > bestCorr) { bestCorr = c; bestLag = lag; }
  }
  if (bestLag < 0) return null;
  const clarity = bestCorr / energy;
  if (clarity < 0.35) return null; // not periodic enough → not a clear note

  // parabolic interpolation around the peak for a finer frequency
  const y1 = acf(buf, bestLag - 1), y2 = bestCorr, y3 = acf(buf, bestLag + 1);
  const denom = (y1 - 2 * y2 + y3);
  const shift = denom !== 0 ? (0.5 * (y1 - y3)) / denom : 0;
  return sr / (bestLag + shift);
}
function acf(buf, lag) {
  if (lag < 1) return 0;
  let c = 0;
  for (let i = 0; i < buf.length - lag; i++) c += buf[i] * buf[i + lag];
  return c;
}

// ---------- boot ----------
async function boot() {
  // initialise readouts + fills
  setEngineControlsEnabled(false);
  el.keyRead.textContent = pitchLabel(+el.key.value);
  el.vocalRead.textContent = vocalLabel(+el.vocal.value);
  updateRangeFill(el.key);
  updateRangeFill(el.vocal);
  updateRangeFill(el.seek);

  if (!supported()) {
    el.unsupported.hidden = false;
    setStatus('neutral', 'Live preview unavailable in this browser.');
    return;
  }

  setStatus('neutral', 'Loading the demo song…');
  try {
    await initEngine();
    loadBuffer(buildDemo(state.ctx.sampleRate));
  } catch (err) {
    setStatus('error', 'Couldn’t start the audio engine in this browser.');
    return;
  }

  // transport gated until the demo buffer is ready — now it is
  state.ready = true;
  setEngineControlsEnabled(true);
  setStatus('ok', 'Ready — press play, or tap Match my key.');
}

boot();
