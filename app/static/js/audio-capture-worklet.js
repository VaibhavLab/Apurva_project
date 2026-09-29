'use strict';
class MindCareCapture extends AudioWorkletProcessor {
  constructor(options) {
    super();
    this.limit = Math.ceil((options.processorOptions.maxSeconds || 30) * sampleRate);
    this.chunk = new Float32Array(2048);
    this.offset = 0;
    this.total = 0;
    this.stopped = false;
    this.port.onmessage = event => {
      if (event.data === 'stop') {
        this.flush();
        this.stopped = true;
        this.port.postMessage({stopped: true});
      }
    };
  }
  flush() {
    if (!this.offset) return;
    const samples = this.chunk.slice(0, this.offset);
    this.port.postMessage({samples}, [samples.buffer]);
    this.offset = 0;
  }
  process(inputs) {
    if (this.stopped) return false;
    const channels = inputs[0];
    if (!channels?.length) return true;
    for (let i = 0; i < channels[0].length && this.total < this.limit; i++) {
      let sample = 0;
      for (const channel of channels) sample += channel[i] / channels.length;
      this.chunk[this.offset++] = sample;
      this.total++;
      if (this.offset === this.chunk.length) this.flush();
    }
    if (this.total >= this.limit) {
      this.flush();
      this.stopped = true;
      this.port.postMessage({limitReached: true, stopped: true});
      return false;
    }
    return true;
  }
}
registerProcessor('mindcare-capture', MindCareCapture);
