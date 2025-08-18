'use strict';

// --- Core Audio Logic ---
let audioContext = null;
let audioWorkletNode = null;
let microphoneStream = null;
let audioQueue = [];
let isAudioPlaying = false;
let onPlaybackFinishedCallback = null;
let nextPlayTime = 0; // Time tracker for scheduling audio chunks

/**
 * Sets the callback function to be invoked when the audio playback queue is empty.
 * @param {Function} callback - The function to call when playback finishes.
 */
function setOnPlaybackFinished(callback) {
    onPlaybackFinishedCallback = callback;
}

/**
 * Processes the audio queue, playing the next available audio buffer with precise scheduling.
 * @param {Function} logMessage - The logging function from the main app.
 */
function playFromQueue(logMessage) {
    if (audioQueue.length === 0) {
        isAudioPlaying = false;
        if (onPlaybackFinishedCallback) {
            // Add a small delay to ensure the last chunk has finished
            setTimeout(() => {
                logMessage('🏁 Audio playback queue finished.');
                onPlaybackFinishedCallback();
            }, 200); // 200ms delay
        }
        return;
    }

    isAudioPlaying = true;
    const audioData = audioQueue.shift();

    try {
        if (!audioContext || audioContext.state === 'closed') {
            logMessage('Audio context is not available for playback.', 'error');
            isAudioPlaying = false; 
            return;
        }

        // The audio from the agent is 24kHz, 16-bit PCM
        const numSamples = audioData.length / 2; // 2 bytes per sample
        const pcmData = new Int16Array(audioData.buffer, audioData.byteOffset, numSamples);
        const audioBuffer = audioContext.createBuffer(1, numSamples, 24000); 
        const channelData = audioBuffer.getChannelData(0);
        
        for (let i = 0; i < numSamples; i++) {
            channelData[i] = pcmData[i] / 32768.0; // Convert to Float32 range [-1, 1]
        }

        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);

        // --- Precise Scheduling ---
        const now = audioContext.currentTime;
        if (now > nextPlayTime) {
            nextPlayTime = now;
        }

        source.start(nextPlayTime);
        // Schedule the next chunk to start right after this one ends
        nextPlayTime += audioBuffer.duration;
        
        // Continue processing the queue without waiting for 'onended'
        playFromQueue(logMessage);

    } catch (error) {
        logMessage(`Error playing raw PCM: ${error}`, 'error');
        console.error('Raw PCM playback error:', error);
        // Try to continue with the next item
        playFromQueue(logMessage); 
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
        // Reset scheduling time and start the playback loop
        nextPlayTime = audioContext.currentTime;
        playFromQueue(logMessage);
    }
}

/**
 * Initializes the AudioContext, microphone stream, and audio worklet.
 * @param {Function} getSocket - A function that returns the current Socket.IO client instance.
 * @param {Function} logMessage - The logging function.
 * @param {Function} getIsMuted - A function that returns the current muted state.
 * @param {Function} getIsAgentSpeaking - A function that returns the agent's speaking state.
 * @returns {Promise<boolean>} - True if successful, false otherwise.
 */
async function startAudio(getSocket, logMessage, getIsMuted, getIsAgentSpeaking) {
    if (audioContext) {
        logMessage('Audio pipeline already active.');
        return true;
    }
    logMessage('Starting audio pipeline...');

    try {
        // Use a consistent sample rate for user input
        audioContext = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 16000 });
        if (audioContext.state === 'suspended') {
            await audioContext.resume();
        }

        await audioContext.audioWorklet.addModule('/audio-processor.js');
        audioWorkletNode = new AudioWorkletNode(audioContext, 'audio-processor');

        microphoneStream = await navigator.mediaDevices.getUserMedia({
            audio: { sampleRate: 16000, channelCount: 1 }
        });
        const microphone = audioContext.createMediaStreamSource(microphoneStream);
        microphone.connect(audioWorkletNode);

        audioWorkletNode.port.onmessage = (event) => {
            const socket = getSocket();
            // Send audio only when not muted and the agent isn't speaking
            if (socket && socket.connected && !getIsMuted() && !getIsAgentSpeaking()) {
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
        // Clean up on failure
        if (audioContext) {
            audioContext.close();
            audioContext = null;
        }
        return false;
    }
}

/**
 * Stops the audio pipeline, closes the microphone stream, and resets the audio context.
 * @param {Function} logMessage - The logging function.
 */
function stopAudio(logMessage) {
    if (microphoneStream) {
        microphoneStream.getTracks().forEach(track => track.stop());
        microphoneStream = null;
    }
    if (audioWorkletNode) {
        audioWorkletNode.disconnect();
        audioWorkletNode = null;
    }
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close().then(() => {
            audioContext = null;
            logMessage('Audio context closed.');
        });
    } else {
        audioContext = null;
    }
    
    // Clear any pending audio and reset state
    audioQueue = [];
    isAudioPlaying = false;
    nextPlayTime = 0;
    onPlaybackFinishedCallback = null;
    logMessage('Audio pipeline stopped.');
}

// --- Debugging ---

window.checkAudio = function(logMessage) {
    if (!logMessage || typeof logMessage !== 'function') {
        console.error("logMessage function not provided to checkAudio");
        return;
    }
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