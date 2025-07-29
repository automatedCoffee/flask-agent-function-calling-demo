// This script provides a WebAssembly-based processor for converting audio streams 
// from the browser's default format into the raw PCM format required by Deepgram.
// It uses a separate worker thread to avoid blocking the main UI thread.

class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.sampleCount = 0;
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (input.length > 0) {
            const channelData = input[0];
            // Log every 16000 samples (roughly every second)
            this.sampleCount += channelData.length;
            if (this.sampleCount >= 16000) {
                console.log(`[Worklet] Processed ${this.sampleCount} audio samples.`);
                this.sampleCount = 0;
            }

            const pcmData = this.convertToPcm(channelData);
            this.port.postMessage(pcmData, [pcmData]);
        }
        return true;
    }

    convertToPcm(channelData) {
        const output = new Int16Array(channelData.length);
        for (let i = 0; i < channelData.length; i++) {
            const s = Math.max(-1, Math.min(1, channelData[i]));
            output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return output.buffer;
    }
}

registerProcessor('audio-processor', AudioProcessor); 