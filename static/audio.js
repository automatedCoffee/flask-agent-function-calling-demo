// --- Core Audio Logic ---
let audioContext = null;
let audioWorkletNode = null;
let microphoneStream = null;
let audioQueue = [];
let nextPlayTime = 0; // For continuous audio scheduling

async function startAudio(socket, logMessage, setStatus, updateSpeakButtonState, isMuted, isAgentSpeaking) {
    setStatus('Initializing...');
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
            // Simple audio capture logging
            if (Math.random() < 0.1) { // 10% of chunks
                logMessage(`🎙️ CAPTURED: ${event.data.byteLength} bytes - isMuted: ${isMuted}, socket: ${socket?.connected}`);
            }

            // Try to send audio if conditions are right
            if (socket && socket.connected && !isMuted && !isAgentSpeaking) {
                try {
                    // Ensure we send an ArrayBuffer-only payload
                    const buf = event.data instanceof ArrayBuffer ? event.data : event.data.buffer;
                    socket.emit('user_audio', buf);

                    // Log successful sending
                    if (Math.random() < 0.05) { // 5% of chunks
                        logMessage(`📤 SENT: ${buf.byteLength} bytes`);
                    }
                } catch (error) {
                    logMessage(`❌ SEND ERROR: ${error}`, 'error');
                }
            } else {
                // Log why we're NOT sending (less frequently)
                if (Math.random() < 0.02) { // 2% of chunks
                    const reason = !socket ? 'no-socket' :
                                  !socket.connected ? 'disconnected' :
                                  isMuted ? 'muted' :
                                  isAgentSpeaking ? 'agent-speaking' : 'unknown';
                    logMessage(`❌ NOT SENT: ${reason}`);
                }
            }
        };

        setStatus('Connected, starting agent...');
        logMessage('Audio pipeline ready.');
        logMessage(`Microphone connected - Sample rate: ${audioContext.sampleRate}Hz`);
        logMessage(`Audio mode: Press to Speak button only`);

    } catch (error) {
        logMessage(`Failed to start audio: ${error}`, 'error');
        if (error.name === 'NotAllowedError') {
            logMessage('Microphone permission denied. Please allow microphone access and try again.', 'error');
        } else if (error.name === 'NotFoundError') {
            logMessage('No microphone found. Please connect a microphone and try again.', 'error');
        }
        setStatus('Error');
        return false;
    }
    return true;
}

function stopAudio(socket) {
    if (socket) {
        socket.emit('stop_voice_agent');
        socket.disconnect();
    }
    if (microphoneStream) {
        microphoneStream.getTracks().forEach(track => track.stop());
    }
    if (audioContext && audioContext.state !== 'closed') {
        audioContext.close();
    }
    audioQueue = [];
    nextPlayTime = 0;
}

function playNextAudioChunk(logMessage, setStatus, updateSpeakButtonState) {
    if (audioQueue.length === 0 || !audioContext) {
        // Audio queue is empty, but we'll rely primarily on AgentAudioDone message
        if (isAgentSpeaking) {
            logMessage(`🔄 Audio queue empty, checking for remaining audio...`);
            setTimeout(() => {
                logMessage(`🔍 Checking conditions: audioQueue.length=${audioQueue.length}, isAgentSpeaking=${isAgentSpeaking}`);
                if (audioQueue.length === 0) { // Double check after delay
                    isAgentSpeaking = false;
                    isAgentProcessing = false;
                    logMessage('🏁 Audio playback finished - ready for user input');
                    setStatus('Agent Ready - Press button to speak');
                    updateSpeakButtonState();
                }
            }, 100); // Much shorter delay since AgentAudioDone should handle most cases
        }
        return;
    }

    const audioData = audioQueue.shift();

    if (audioContext.state === 'suspended') {
        audioContext.resume().then(() => {
            playRawPCM(audioData, logMessage);
        });
    } else {
        playRawPCM(audioData, logMessage);
    }
}

function playRawPCM(audioData, logMessage) {
    try {
        // Convert Uint8Array to Int16Array (16-bit PCM)
        const numSamples = audioData.length / 2;
        const pcmData = new Int16Array(audioData.buffer, audioData.byteOffset, numSamples);

        // Create AudioBuffer
        const audioBuffer = audioContext.createBuffer(1, numSamples, 24000); // Agent audio output is 24kHz
        const channelData = audioBuffer.getChannelData(0);

        // Convert Int16 to Float32 and fill the buffer
        for (let i = 0; i < numSamples; i++) {
            const sample = pcmData[i];
            channelData[i] = sample / 32768.0;
        }

        // Schedule the buffer for continuous playback
        const source = audioContext.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(audioContext.destination);

        // Calculate when to start this chunk for smooth playback
        const currentTime = audioContext.currentTime;
        if (nextPlayTime <= currentTime) {
            nextPlayTime = currentTime + 0.05; // Larger buffer (50ms) to prevent cutoff
        }

        source.start(nextPlayTime);
        nextPlayTime += audioBuffer.duration; // Schedule next chunk right after this one

        // Log less frequently
        if (Math.random() < 0.02) { // 2% of chunks
            logMessage(`Playing audio chunk: ${numSamples} samples, scheduled at ${nextPlayTime.toFixed(3)}s`);
        }

    } catch (error) {
        logMessage(`Error playing raw PCM: ${error}`, 'error');
        console.error('Raw PCM playback error:', error);
    }
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