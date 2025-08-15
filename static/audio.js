'use strict';

// --- Core Audio Logic ---
let audioContext = null;
let audioWorkletNode = null;
let microphoneStream = null;
let audioQueue = [];
let isAudioPlaying = false;
let onPlaybackFinishedCallback = null;

/**
 * Sets the callback function to be invoked when the audio playback queue is empty.
 * @param {Function} callback - The function to call when playback finishes.
 */
function setOnPlaybackFinished(callback) {
    onPlaybackFinishedCallback = callback;
}

/**
 * Processes the audio queue, playing the next available audio buffer.
 * This function is self-referential via the `onended` event of the AudioBufferSourceNode.
 * @param {Function} logMessage - The logging function from the main app.
 */
function playFromQueue(logMessage) {
    if (audioQueue.length === 0) {
        isAudioPlaying = false;
        if (onPlaybackFinishedCallback) {
            logMessage('🏁 Audio playback queue finished.');
            onPlaybackFinishedCallback();
        }
        return;
    }

    isAudioPlaying = true;
    const audioData = audioQueue.shift();

    try {
        const numSamples = audioData.length / 2;
        const pcmData = new Int16Array(audioData.buffer, audioData.byteOffset, numSamples);
        const audioBuffer = audioContext.createBuffer(1, numSamples, 24000); // Agent audio is 24kHz
        const channelData = audioBuffer.getChannelData(0);
        for (let i = 0; i < numSamples; i++) {
            channelData[i] = pcmData[i] / 32768.0;
        }

        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);
        source.onended = () => playFromQueue(logMessage);
        source.start();
    } catch (error) {
        logMessage(`Error playing raw PCM: ${error}`, 'error');
        console.error('Raw PCM playback error:', error);
        playFromQueue(logMessage); // Try to continue with the next item
    }
}

/**
 * Adds a new audio chunk to the playback queue.
 * @param {Uint8Array} audioData - The raw PCM audio data chunk.
 * @param {Function} logMessage - The logging function from the main app.
 */
function addAudioToQueue(audioData, logMessage) {
    if (!audioContext) {
        logMessage('Audio context not ready, cannot queue audio.', 'warn');
        return;
    }
    if (audioContext.state === 'suspended') {
        audioContext.resume();
    }
    audioQueue.push(audioData);
    if (!isAudioPlaying) {
        playFromQueue(logMessage);
    }
}

/**
 * Initializes the AudioContext and microphone stream.
 * @param {Object} socket - The Socket.IO client instance.
 * @param {Function} logMessage - The logging function.
 * @param {Function} getMutedState - A function that returns the current muted state.
 * @param {Function} getAgentSpeakingState - A function that returns the agent's speaking state.
 * @returns {Promise<boolean>} - True if successful, false otherwise.
 */
async function startAudio(socket, logMessage, getMutedState, getAgentSpeakingState) {
    if (audioContext) {
        return true;
    }
    logMessage('Starting audio pipeline...');

    try {
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        if (audioContext.state === 'suspended') await audioContext.resume();

        await audioContext.audioWorklet.addModule('/audio-processor.js');
        audioWorkletNode = new AudioWorkletNode(audioContext, 'audio-processor');

        microphoneStream = await navigator.mediaDevices.getUserMedia({
            audio: { sampleRate: 16000, channelCount: 1 }
        });
        const microphone = audioContext.createMediaStreamSource(microphoneStream);
        microphone.connect(audioWorkletNode);

        audioWorkletNode.port.onmessage = (event) => {
            if (socket && socket.connected && !getMutedState() && !getAgentSpeakingState()) {
                const buf = event.data instanceof ArrayBuffer ? event.data : event.data.buffer;
                socket.emit('user_audio', buf);
            }
        };

        logMessage('Audio pipeline ready.');
        logMessage(`Microphone connected - Sample rate: ${audioContext.sampleRate}Hz`);
        return true;
    } catch (error) {
        logMessage(`Failed to start audio: ${error}`, 'error');
        if (error.name === 'NotAllowedError') {
            logMessage('Microphone permission denied. Please allow microphone access and try again.', 'error');
        } else if (error.name === 'NotFoundError') {
            logMessage('No microphone found. Please connect a microphone and try again.', 'error');
        }
        audioContext = null;
        return false;
    }
}

/**
 * Stops the audio pipeline and closes the microphone stream.
 * @param {Object} socket - The Socket.IO client instance.
 * @param {Function} logMessage - The logging function.
 */
function stopAudio(socket, logMessage) {
    if (socket) {
        socket.emit('stop_voice_agent');
        socket.disconnect();
    }
    if (microphoneStream) {
        microphoneStream.getTracks().forEach(track => track.stop());
        microphoneStream = null;
    }
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close().then(() => {
            audioContext = null;
        });
    }
    audioQueue = [];
    isAudioPlaying = false;
    onPlaybackFinishedCallback = null;
    logMessage('Audio pipeline stopped.');
}

window.checkAudio = function() {
    logMessage(`🎙️ AUDIO STATUS:`);
    logMessage(`  - audioContext: ${audioContext ? 'EXISTS' : 'NULL'}`);
    logMessage(`  - audioContext.state: ${audioContext?.state}`);
    logMessage(`  - audioWorkletNode: ${audioWorkletNode ? 'EXISTS' : 'NULL'}`);
    logMessage(`  - microphoneStream: ${microphoneStream ? 'EXISTS' : 'NULL'}`);
    logMessage(`  - microphoneStream.active: ${microphoneStream?.active}`);
    if (microphoneStream) {
        logMessage(`  - microphone tracks: ${microphoneStream.getTracks().length}`);
        microphoneStream.getTracks().forEach((track, i) => {
            logMessage(`    Track ${i}: ${track.kind}, enabled: ${track.enabled}, readyState: ${track.readyState}`);
        });
    }
}; 