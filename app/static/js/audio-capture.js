'use strict';
(() => {
  async function wavBlob(chunks, sampleRate) {
    const length = chunks.reduce((sum, chunk) => sum + chunk.length, 0);
    if (!length) throw new Error('No audio was recorded. Please try again.');
    const mono = new Float32Array(length);
    let offset = 0;
    for (const chunk of chunks) { mono.set(chunk, offset); offset += chunk.length; }
    // OfflineAudioContext performs real sample-rate conversion, including filtering.
    const offline = new OfflineAudioContext(1, Math.max(1, Math.floor(length * 16000 / sampleRate)), 16000);
    const buffer = offline.createBuffer(1, length, sampleRate);
    buffer.copyToChannel(mono, 0);
    const source = offline.createBufferSource();
    source.buffer = buffer;
    source.connect(offline.destination);
    source.start();
    const samples = (await offline.startRendering()).getChannelData(0);
    const bytes = new ArrayBuffer(44 + samples.length * 2);
    const view = new DataView(bytes);
    const ascii = (at, value) => [...value].forEach((char, i) => view.setUint8(at + i, char.charCodeAt(0)));
    ascii(0, 'RIFF'); view.setUint32(4, bytes.byteLength - 8, true);
    ascii(8, 'WAVE'); ascii(12, 'fmt '); view.setUint32(16, 16, true);
    view.setUint16(20, 1, true); view.setUint16(22, 1, true);
    view.setUint32(24, 16000, true); view.setUint32(28, 32000, true);
    view.setUint16(32, 2, true); view.setUint16(34, 16, true);
    ascii(36, 'data'); view.setUint32(40, samples.length * 2, true);
    samples.forEach((value, i) => view.setInt16(44 + i * 2, Math.round(Math.max(-1, Math.min(1, value)) * (value < 0 ? 32768 : 32767)), true));
    return new Blob([bytes], {type: 'audio/wav'});
  }
  class AudioCapture {
    constructor() { this.cancelled = false; this.chunks = []; this.ended = false; }
    async start(maxSeconds, onLevel, onLimit) {
      try {
        this.stream = await navigator.mediaDevices.getUserMedia({audio: {channelCount: 1, echoCancellation: true, noiseSuppression: true}, video: false});
        if (this.cancelled) throw new DOMException('Cancelled', 'AbortError');
        this.context = new AudioContext();
        await this.context.resume();
        await this.context.audioWorklet.addModule('/static/js/audio-capture-worklet.js');
        if (this.cancelled) throw new DOMException('Cancelled', 'AbortError');
        this.sampleRate = this.context.sampleRate;
        this.node = new AudioWorkletNode(this.context, 'mindcare-capture', {processorOptions: {maxSeconds}});
        this.node.port.onmessage = event => {
          if (this.cancelled) return;
          if (event.data.samples) {
            this.chunks.push(event.data.samples);
            const rms = Math.sqrt(event.data.samples.reduce((sum, value) => sum + value * value, 0) / event.data.samples.length);
            onLevel(Math.min(1, rms * 5));
          }
          if (event.data.stopped) { this.ended = true; this.stopResolve?.(); }
          if (event.data.limitReached) onLimit();
        };
        this.source = this.context.createMediaStreamSource(this.stream);
        this.gain = this.context.createGain();
        this.gain.gain.value = 0;
        this.source.connect(this.node).connect(this.gain).connect(this.context.destination);
      } catch (error) { this.cancel(); throw error; }
    }
    async finish() {
      if (this.cancelled) throw new DOMException('Cancelled', 'AbortError');
      if (!this.ended) await new Promise(resolve => {
        const timer = setTimeout(resolve, 500);
        this.stopResolve = () => { clearTimeout(timer); resolve(); };
        this.node.port.postMessage('stop');
      });
      this.release();
      if (this.cancelled) throw new DOMException('Cancelled', 'AbortError');
      const blob = await wavBlob(this.chunks, this.sampleRate);
      this.chunks = [];
      return blob;
    }
    release() {
      this.stream?.getTracks().forEach(track => track.stop());
      this.source?.disconnect(); this.node?.disconnect(); this.gain?.disconnect();
      if (this.context && this.context.state !== 'closed') this.context.close().catch(() => {});
      if (this.node) this.node.port.onmessage = null;
    }
    cancel() { this.cancelled = true; this.stopResolve?.(); this.release(); this.chunks = []; }
  }
  window.mindcare.AudioCapture = AudioCapture;
})();
