// This script provides a WebAssembly-based processor for converting audio streams 
// from the browser's default format into the raw PCM format required by Deepgram.
// It uses a separate worker thread to avoid blocking the main UI thread.

class AudioProcessor extends AudioWorkletProcessor {
    constructor() {
        super();
        this.sampleCount = 0;
        // Actual sample rate of the AudioContext driving this worklet
        this.inputSampleRate = sampleRate; // Provided by AudioWorkletGlobalScope
        this.targetSampleRate = 16000; // Must match server/agent SETTINGS input sample rate
    }

    process(inputs, outputs, parameters) {
        const input = inputs[0];
        if (input.length > 0) {
            const channelData = input[0];
            // Log roughly once per second of input at the input sample rate
            this.sampleCount += channelData.length;
            if (this.sampleCount >= this.inputSampleRate) {
                // eslint-disable-next-line no-console
                console.log(`[Worklet] Processed ~${this.sampleCount} samples @ ${this.inputSampleRate} Hz`);
                this.sampleCount = 0;
            }

            const pcmData = this.resampleAndConvertToPcm(channelData, this.inputSampleRate, this.targetSampleRate);
            this.port.postMessage(pcmData, [pcmData]);
        }
        return true;
    }

    resampleAndConvertToPcm(channelData, inputRate, targetRate) {
        if (inputRate === targetRate) {
            return this.convertToPcm(channelData);
        }

        const sampleRatio = inputRate / targetRate;
        const outLength = Math.max(1, Math.round(channelData.length / sampleRatio));

        // First resample to Float32 using linear interpolation
        const resampled = new Float32Array(outLength);
        for (let i = 0; i < outLength; i++) {
            const inPos = i * sampleRatio;
            const idx = Math.floor(inPos);
            const frac = inPos - idx;
            const s1 = channelData[idx] || 0;
            const s2 = channelData[idx + 1] || s1;
            resampled[i] = s1 + (s2 - s1) * frac;
        }

        // Then convert to PCM16
        const output = new Int16Array(resampled.length);
        for (let i = 0; i < resampled.length; i++) {
            const s = Math.max(-1, Math.min(1, resampled[i]));
            output[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return output.buffer;
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