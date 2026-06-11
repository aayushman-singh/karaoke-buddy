/* pitch-worklet.js — Surface B DSP, runs on the audio render thread.
 *
 * Pitch shift WITHOUT tempo change (SoundTouch-family / WSOLA approach):
 * two crossfading read taps stream from the loaded buffer at a constant
 * real-time rate while a ramping fractional delay resamples the grain — so
 * the song keeps its tempo but changes key. Vocal reduction is center-channel
 * cancellation applied AFTER the shift so the cancellation stays phase-coherent.
 *
 * All control comes through the port; no fallback values are invented — if no
 * audio is loaded the node emits silence.
 */

class PitchProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this._left = null;
    this._right = null;
    this._len = 0;
    this._sr = sampleRate;
    this._pos = 0; // absolute source index (float), advances 1/output-sample
    this._phase = 0; // grain crossfade phase 0..1
    this._win = Math.round(0.06 * sampleRate); // grain size in samples
    this._pitchRatio = 1;
    this._vocal = 0;
    this._playing = false;
    this._reportCounter = 0;

    this.port.onmessage = (e) => {
      const m = e.data;
      if (m.type === 'load') {
        this._left = m.left;
        this._right = m.right || m.left;
        this._len = m.left.length;
        this._sr = m.sampleRate;
        this._win = Math.round(0.06 * m.sampleRate);
        this._pos = 0;
        this._phase = 0;
      } else if (m.type === 'params') {
        this._pitchRatio = m.pitchRatio;
        this._vocal = m.vocalAmount;
      } else if (m.type === 'play') {
        this._playing = m.playing;
      } else if (m.type === 'seek') {
        this._pos = Math.max(0, Math.min(this._len - 1, m.pos * this._sr));
      }
    };
  }

  _read(buf, idx) {
    if (idx < 0) idx = 0;
    const i0 = idx | 0;
    if (i0 >= this._len - 1) return buf[this._len - 1] || 0;
    const frac = idx - i0;
    return buf[i0] * (1 - frac) + buf[i0 + 1] * frac;
  }

  process(_inputs, outputs) {
    const out = outputs[0];
    const oL = out[0];
    const oR = out.length > 1 ? out[1] : out[0];
    const n = oL.length;

    if (!this._left || !this._playing) {
      oL.fill(0);
      if (oR !== oL) oR.fill(0);
      return true;
    }

    const win = this._win;
    const p = this._pitchRatio;
    const k = this._vocal;
    const inc = (1 - p) / win; // phase increment per output sample

    for (let s = 0; s < n; s++) {
      let ph = this._phase;
      let ph2 = ph + 0.5;
      if (ph2 >= 1) ph2 -= 1;
      const g1 = Math.sin(Math.PI * ph);
      const g2 = Math.sin(Math.PI * ph2);
      const d1 = ph * win;
      const d2 = ph2 * win;

      const pos = this._pos;
      let lo = g1 * this._read(this._left, pos - d1) + g2 * this._read(this._left, pos - d2);
      let ro = g1 * this._read(this._right, pos - d1) + g2 * this._read(this._right, pos - d2);

      if (k > 0) {
        const center = (lo + ro) * 0.5;
        lo -= k * center;
        ro -= k * center;
      }

      oL[s] = lo;
      if (oR !== oL) oR[s] = ro;

      // advance
      this._phase = ph + inc;
      if (this._phase >= 1) this._phase -= 1;
      else if (this._phase < 0) this._phase += 1;

      this._pos += 1;
      if (this._pos >= this._len - 1) this._pos = 0; // loop the demo
    }

    // report position back to the UI ~ every 21ms
    if (++this._reportCounter >= 8) {
      this._reportCounter = 0;
      this.port.postMessage({ type: 'pos', pos: this._pos / this._sr });
    }
    return true;
  }
}

registerProcessor('pitch-processor', PitchProcessor);
