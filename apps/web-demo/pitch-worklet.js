/*
 * pitch-worklet.js — Karaoke Buddy browser preview
 * ------------------------------------------------------------------
 * Real-time pitch shifter + centre-channel ("lead vocal") remover that
 * runs entirely on the audio rendering thread inside an AudioWorklet.
 *
 * Why an AudioWorklet (and not a ScriptProcessorNode)?
 *   SoundTouchJS ships a `PitchShifter` helper built on the deprecated
 *   ScriptProcessorNode, which runs on the main thread and glitches under
 *   load. We instead drive SoundTouch's *core* classes (`SoundTouch` +
 *   `SimpleFilter`) directly from inside `process()`, so all DSP happens
 *   on the dedicated audio thread with no main-thread jank.
 *
 * Signal flow per render quantum (128 frames):
 *   decoded buffer  ──▶  BufferSource.extract()
 *                        │
 *                        ▼
 *                   SimpleFilter  ──▶  SoundTouch (WSOLA pitch shift)
 *                        │  interleaved stereo, tempo-preserving
 *                        ▼
 *                   mid/side centre subtraction  (vocal removal)
 *                        │
 *                        ▼
 *                   output[0] = L', output[1] = R'
 *
 * The vendored SoundTouchJS dist is a real ES module; modern browsers
 * allow `import` inside an AudioWorklet module script, so we pull the
 * core classes straight from the pristine vendor file — no fork, no
 * copy-paste, license stays intact.
 */

import { SoundTouch, SimpleFilter } from './vendor/soundtouchjs/soundtouch.js';

/**
 * Pull-based source that hands interleaved stereo frames to SimpleFilter.
 *
 * SimpleFilter calls `extract(target, numFrames, position)` whenever it
 * needs more input. We back it with the fully-decoded song so SoundTouch
 * can read ahead by whatever its WSOLA window requires. `position` is an
 * absolute frame index into the decoded audio, owned by SimpleFilter.
 */
class InterleavedBufferSource {
  /**
   * @param {Float32Array} left  - de-interleaved left channel
   * @param {Float32Array} right - de-interleaved right channel
   */
  constructor(left, right) {
    this.left = left;
    this.right = right;
    this.frames = left.length;
  }

  /**
   * @param {Float32Array} target   - interleaved [L,R,L,R,...] destination
   * @param {number} numFrames      - frames requested
   * @param {number} position       - absolute start frame in the source
   * @returns {number} frames actually written (0 at end-of-stream)
   */
  extract(target, numFrames = 0, position = 0) {
    const available = Math.max(0, this.frames - position);
    const toCopy = Math.min(numFrames, available);
    for (let i = 0; i < toCopy; i++) {
      target[i * 2] = this.left[position + i];
      target[i * 2 + 1] = this.right[position + i];
    }
    return toCopy;
  }
}

class PitchWorkletProcessor extends AudioWorkletProcessor {
  constructor() {
    super();

    // --- Playback / DSP state -------------------------------------------
    this.source = null; // InterleavedBufferSource once audio is loaded
    this.soundTouch = null; // SoundTouch core engine
    this.filter = null; // SimpleFilter pulling from source
    this.playing = false;
    this.ended = false;

    // Live-controllable parameters (updated via port messages).
    this.pitchSemitones = 0;

    // Centre-channel subtraction mix. Mirrors the desktop contract in
    // src/karaoke_buddy/core/filter_chain.py exactly:
    //   mix = (vocal_reduce_percent / 100) * 0.5
    //   out_L = L - mix * R
    //   out_R = R - mix * L
    this.vocalMix = 0;

    // Scratch buffer for interleaved frames pulled from SimpleFilter.
    // RENDER_QUANTUM is fixed at 128 frames by the Web Audio spec.
    this.RENDER_QUANTUM = 128;
    this.interleaved = new Float32Array(this.RENDER_QUANTUM * 2);

    // For progress reporting we throttle postMessage to ~30 Hz.
    this.lastReportFrame = 0;

    this.port.onmessage = (event) => this._handleMessage(event.data);
  }

  _handleMessage(msg) {
    switch (msg.type) {
      case 'load': {
        // msg.left / msg.right are transferred Float32Arrays (zero-copy).
        const left = new Float32Array(msg.left);
        const right = new Float32Array(msg.right);
        this.source = new InterleavedBufferSource(left, right);

        this.soundTouch = new SoundTouch();
        this.soundTouch.pitchSemitones = this.pitchSemitones;
        this.filter = new SimpleFilter(this.source, this.soundTouch);

        this.ended = false;
        // Lockstep with the UI: a fresh buffer always starts PAUSED. Without
        // this, swapping buffers (demo↔file) while playing left playing=true
        // and the new track could roar to life while the button showed Play.
        // The main thread also sends an explicit 'pause' before 'load'; this
        // makes the worklet self-consistent even if that message is missed.
        this.playing = false;
        this.port.postMessage({ type: 'loaded', frames: this.source.frames });
        break;
      }
      case 'play':
        if (this.ended) this._seekToFrame(0);
        this.playing = true;
        break;
      case 'pause':
        this.playing = false;
        break;
      case 'pitch':
        // Integer semitone shift; applied instantly, tempo preserved.
        this.pitchSemitones = msg.value;
        if (this.soundTouch) this.soundTouch.pitchSemitones = msg.value;
        break;
      case 'vocal':
        // Percentage 0..100 from the "Silence the singer" slider.
        this.vocalMix = (msg.value / 100) * 0.5;
        break;
      case 'seek':
        this._seekToFrame(Math.floor(msg.frame));
        break;
      default:
        // Loud failure: an unknown control message is a programming error,
        // never silently ignored.
        this.port.postMessage({
          type: 'error',
          message: `Unknown worklet message: ${msg.type}`,
        });
    }
  }

  _seekToFrame(frame) {
    if (!this.filter) return;
    // SimpleFilter.sourcePosition setter clears its internal WSOLA history
    // so the shift restarts cleanly at the new playhead.
    this.filter.sourcePosition = frame;
    this.ended = false;
  }

  /**
   * Apply mid/side centre subtraction in place on a de-interleaved pair.
   * Matches build_filter_chain()'s pan math byte-for-byte at the formula
   * level (the desktop renders it via FFmpeg's `pan` filter).
   */
  _removeCentre(outL, outR, count) {
    const mix = this.vocalMix;
    if (mix === 0) return; // nothing to subtract
    for (let i = 0; i < count; i++) {
      const l = outL[i];
      const r = outR[i];
      outL[i] = l - mix * r;
      outR[i] = r - mix * l;
    }
  }

  process(_inputs, outputs) {
    const output = outputs[0];
    const outL = output[0];
    const outR = output[1] || output[0];
    const n = outL.length; // 128 under the current spec

    // Not loaded yet, or paused: emit silence but keep the node alive.
    if (!this.filter || !this.playing) {
      outL.fill(0);
      if (outR !== outL) outR.fill(0);
      return true;
    }

    // Pull `n` pitch-shifted interleaved frames from SoundTouch.
    const framesExtracted = this.filter.extract(this.interleaved, n);

    // De-interleave into the output channels.
    for (let i = 0; i < framesExtracted; i++) {
      outL[i] = this.interleaved[i * 2];
      outR[i] = this.interleaved[i * 2 + 1];
    }
    // Zero-fill any tail if we ran past the end of the song.
    for (let i = framesExtracted; i < n; i++) {
      outL[i] = 0;
      outR[i] = 0;
    }

    // Live "Silence the singer" centre subtraction.
    this._removeCentre(outL, outR, framesExtracted);

    // End-of-stream: tell the main thread once, then idle.
    if (framesExtracted === 0) {
      if (!this.ended) {
        this.ended = true;
        this.playing = false;
        this.port.postMessage({ type: 'ended' });
      }
      return true;
    }

    // Throttled progress updates (~30 Hz) for the playhead UI.
    const pos = this.filter.sourcePosition;
    if (pos - this.lastReportFrame > sampleRate / 30) {
      this.lastReportFrame = pos;
      this.port.postMessage({ type: 'progress', frame: pos });
    }

    return true; // keep processor alive across pause/seek
  }
}

registerProcessor('pitch-worklet', PitchWorkletProcessor);
