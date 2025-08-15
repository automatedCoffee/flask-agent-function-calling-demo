'use strict';

document.addEventListener("DOMContentLoaded", () => {
    const startButton = document.getElementById('startButton');
    const statusDiv = document.getElementById('status');
    const logsDiv = document.getElementById('logs');
    const conversationDiv = document.getElementById('conversation');
    const voiceModelSelect = document.getElementById('voiceModel');
    const showLogsCheckbox = document.getElementById('showLogs');
    const logsContainer = document.getElementById('logsContainer');
    const speakButton = document.getElementById('speakButton');

    let socket = null;
    let state = {
        isActive: false,
        isMuted: true,
        isAgentSpeaking: false,
        isAgentProcessing: false,
    };

    /**
     * Callback function passed to the audio module.
     * It is called when the audio playback queue is empty.
     */
    function onPlaybackFinished() {
        state.isAgentSpeaking = false;
        state.isAgentProcessing = false;
        setStatus('Agent Ready - Press button to speak');
        updateSpeakButtonState(state.isActive, state.isAgentSpeaking, state.isAgentProcessing);
    }

    // Set the callback in the audio module
    setOnPlaybackFinished(onPlaybackFinished);

    // --- UI and Logging ---

    function setStatus(message) {
        statusDiv.textContent = `Status: ${message}`;
    }

    function logMessage(message, type = 'info') {
        const timestamp = new Date().toLocaleTimeString();
        const logClass = type === 'error' ? 'log-error' : type === 'warn' ? 'log-warn' : type === 'user' ? 'log-user' : 'log-info';
        logsDiv.innerHTML += `<div class="${logClass}">[${timestamp}] ${message}</div>`;
        logsDiv.scrollTop = logsDiv.scrollHeight;
    }

    function addConversationMessage(role, text) {
        const messageBubble = document.createElement('div');
        messageBubble.className = `message-bubble ${role}`;
        messageBubble.textContent = text;
        conversationDiv.appendChild(messageBubble);
        conversationDiv.scrollTop = conversationDiv.scrollHeight;
    }

    // --- Scroll Syncing ---
    const syncScrollContainers = document.querySelectorAll('.syncscroll');
    syncScrollContainers.forEach(el => {
        el.addEventListener('scroll', () => {
            const scrollY = el.scrollTop;
            syncScrollContainers.forEach(otherEl => {
                if (otherEl !== el) {
                    otherEl.scrollTop = scrollY;
                }
            });
        });
    });

    // --- API Calls ---

    async function fetchVoiceModels() {
        try {
            const response = await fetch('/tts-models');
            const data = await response.json();
            if (data.models) {
                voiceModelSelect.innerHTML = '';
                data.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model.name;
                    option.textContent = model.display_name;
                    voiceModelSelect.appendChild(option);
                });
                voiceModelSelect.value = 'aura-2-thalia-en'; // Default
            } else {
                logMessage('Failed to load voice models.', 'error');
            }
        } catch (error) {
            logMessage(`Error fetching voice models: ${error}`, 'error');
        }
    }
    
    // --- Core Audio Logic ---

    async function startAudio(socket, logMessage, getIsMuted, getIsAgentSpeaking) {
        if (state.isActive) return false;
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
                    logMessage(`🎙️ CAPTURED: ${event.data.byteLength} bytes - isMuted: ${getIsMuted()}, socket: ${socket?.connected}`);
                }
                
                // Try to send audio if conditions are right
                if (socket && socket.connected && !getIsMuted() && !getIsAgentSpeaking()) {
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
                                      getIsMuted() ? 'muted' : 
                                      getIsAgentSpeaking() ? 'agent-speaking' : 'unknown';
                        logMessage(`❌ NOT SENT: ${reason}`);
                    }
                }
            };

            state.isActive = true;
            startButton.textContent = 'Stop Voice Agent';
            setStatus('Connected, starting agent...');
            logMessage('Audio pipeline ready.');
            logMessage(`Microphone connected - Sample rate: ${audioContext.sampleRate}Hz`);
            logMessage(`Audio mode: Press to Speak button only`);
            
            // Initialize states for new session
            state.isAgentSpeaking = false;
            state.isAgentProcessing = false;
            state.isMuted = true;
            updateSpeakButtonState(state.isActive, state.isAgentSpeaking, state.isAgentProcessing); // This should keep button disabled until agent is ready
            
            connectSocket();
            return true;

        } catch (error) {
            logMessage(`Failed to start audio: ${error}`, 'error');
            if (error.name === 'NotAllowedError') {
                logMessage('Microphone permission denied. Please allow microphone access and try again.', 'error');
            } else if (error.name === 'NotFoundError') {
                logMessage('No microphone found. Please connect a microphone and try again.', 'error');
            }
            setStatus('Error');
            state.isActive = false;
            return false;
        }
    }

    function stopAudio(socket, logMessage) {
        if (!state.isActive) return;
        state.isActive = false;
        state.isAgentSpeaking = false;
        state.isAgentProcessing = false;
        state.isMuted = true;
        
        logMessage('Stopping audio pipeline...');
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
        // audioQueue = []; // This is now managed by the audio module
        // nextPlayTime = 0; // This is now managed by the audio module
        
        setStatus('Inactive');
        startButton.textContent = 'Start Voice Agent';
        
        // Reset speak button to disabled state
        speakButton.disabled = true;
        speakButton.style.opacity = '0.6';
        speakButton.querySelector('.speak-button-text').textContent = 'Hold to Speak';
        speakButton.style.background = 'linear-gradient(135deg, #007bff, #0056b3)';
    }

    // --- WebSocket Logic ---

    /**
     * Establishes a WebSocket connection and sets up event handlers.
     */
    function connectSocket() {
        if (socket && socket.connected) {
            logMessage('📡 Socket already connected');
            return;
        }

        logMessage('📡 Connecting to socket...');
        socket = io({
            transports: ['websocket', 'polling'],
            upgrade: true,
            rememberUpgrade: true,
            timeout: 20000,
            forceNew: true
        });

        socket.on('connect', () => {
            logMessage('📡 Socket connected successfully.');
            setStatus('Connected, starting agent...');
            socket.emit('start_voice_agent', { voiceModel: voiceModelSelect.value });
        });

        socket.on('disconnect', (reason) => {
            logMessage(`📡 Socket disconnected: ${reason}`, 'warn');
            setStatus('Disconnected');
            // Stop the entire session on disconnect to prevent runaway loops
            if (state.isActive) {
                startButton.click(); 
            }
        });

        socket.on('connect_error', (error) => {
            logMessage(`📡 Socket connection error: ${error}`, 'error');
            setStatus('Connection Error');
            if (state.isActive) {
                startButton.click();
            }
        });

        socket.on('reconnect', (attemptNumber) => {
            logMessage(`📡 Socket reconnected after ${attemptNumber} attempts`);
            setStatus('Reconnected');
            
            // Restart voice agent if we were active
            if (state.isActive) {
                socket.emit('start_voice_agent', { voiceModel: voiceModelSelect.value });
            }
        });

        socket.on('agent_response', (data) => {
            logMessage(`Agent Response: ${JSON.stringify(data)}`);
            switch (data.type) {
                case 'Welcome':
                    setStatus('Agent Ready');
                    logMessage('🎉 Agent connected - waiting for greeting audio');
                    break;
                case 'ConversationText':
                    addConversationMessage('assistant', data.content);
                    break;
                case 'AgentAudioDone':
                    logMessage('✅ AgentAudioDone received (playback is managed by audio queue).');
                    break;
                case 'Error':
                    logMessage(`Agent Error: ${data.description}`, 'error');
                    setStatus('Error');
                    state.isAgentProcessing = false;
                    state.isAgentSpeaking = false;
                    updateSpeakButtonState(state.isActive, state.isAgentSpeaking, state.isAgentProcessing);
                    break;
            }
        });

        socket.on('agent_audio', (chunk) => {
            if (!state.isAgentSpeaking) {
                state.isAgentSpeaking = true;
                state.isAgentProcessing = false;
                logMessage('🗣️ Agent started speaking');
                setStatus('Agent speaking...');
                updateSpeakButtonState(state.isActive, state.isAgentSpeaking, state.isAgentProcessing);
            }
            addAudioToQueue(new Uint8Array(chunk), logMessage);
        });
    }

    // Function to update speak button state based on current conditions
    function updateSpeakButtonState(isActive, isAgentSpeaking, isAgentProcessing) {
        const shouldEnable = isActive && !isAgentSpeaking && !isAgentProcessing;
        speakButton.disabled = !shouldEnable;
        speakButton.style.opacity = shouldEnable ? '1' : '0.6';
        
        logMessage(`Button state check - Active: ${isActive}, Speaking: ${isAgentSpeaking}, Processing: ${isAgentProcessing}, ShouldEnable: ${shouldEnable}`);
        
        if (shouldEnable) {
            logMessage('✅ Hold to Speak button ENABLED');
            speakButton.style.background = 'linear-gradient(135deg, #007bff, #0056b3)';
            speakButton.querySelector('.speak-button-text').textContent = 'Hold to Speak';
        } else {
            logMessage(`❌ Hold to Speak button DISABLED - Active: ${isActive}, Speaking: ${isAgentSpeaking}, Processing: ${isAgentProcessing}`);
        }
    }

    // Manual test function for debugging
    window.testButton = function() {
        logMessage('🧪 MANUAL TEST: Forcing button enable');
        state.isActive = true;
        state.isAgentSpeaking = false;
        state.isAgentProcessing = false;
        updateSpeakButtonState(state.isActive, state.isAgentSpeaking, state.isAgentProcessing);
        logMessage(`🧪 TEST RESULT: Button disabled = ${speakButton.disabled}`);
    };
    
    window.checkStates = function() {
        logMessage(`📊 STATES: isActive=${state.isActive}, isAgentSpeaking=${state.isAgentSpeaking}, isAgentProcessing=${state.isAgentProcessing}, isMuted=${state.isMuted}`);
        logMessage(`📊 BUTTON: disabled=${speakButton.disabled}, socket=${socket?.connected}`);
    };
    
    window.forceStart = function() {
        logMessage('🔧 FORCE START: Manually starting speaking');
        state.isMuted = false;
        logMessage(`🔧 isMuted is now: ${state.isMuted}`);
    };
    
    window.testSpeak = function() {
        logMessage(' TEST: Manual speak test');
        if (state.isMuted) {
            startSpeaking();
            logMessage('🧪 Started speaking for 5 seconds');
            setTimeout(() => {
                stopSpeaking();
                logMessage('🧪 Stopped speaking');
            }, 5000);
        } else {
            stopSpeaking();
            logMessage('🧪 Stopped speaking');
        }
    };
    
    window.checkSocket = function() {
        logMessage(`📡 SOCKET CHECK:`);
        logMessage(`  - exists: ${socket ? 'YES' : 'NO'}`);
        logMessage(`  - connected: ${socket?.connected}`);
        logMessage(`  - id: ${socket?.id || 'N/A'}`);
        if (socket) {
            logMessage(`  - transport: ${socket.io?.engine?.transport?.name || 'N/A'}`);
        }
    };
    

    
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
    

    
    // Periodic socket health check
    setInterval(() => {
        if (socket && !socket.connected && state.isActive) {
            logMessage('⚠️ HEALTH CHECK: Socket disconnected while active, attempting reconnect');
            socket.connect();
        }
        
        // Also log socket status periodically when active
        if (state.isActive && Math.random() < 0.1) { // 10% chance each check
            logMessage(`💓 HEALTH: Socket connected: ${socket?.connected}, Active: ${state.isActive}, Speaking: ${!state.isMuted}`);
        }
    }, 2000); // Check every 2 seconds instead of 5

    // --- Speaking Logic ---
    function startSpeaking() {
        logMessage(`🎤 startSpeaking() ENTRY - disabled: ${speakButton.disabled}`);
        if (!speakButton.disabled) {
            state.isMuted = false;
            logMessage(`✅ UNMUTED - isMuted is now: ${state.isMuted}`, 'user');
            setStatus('🎤 SPEAKING - Hold button and talk');
            speakButton.querySelector('.speak-button-text').textContent = 'Speaking...';
            speakButton.style.background = 'linear-gradient(135deg, #28a745, #1e7e34)';
        } else {
            logMessage(`❌ BUTTON DISABLED - Cannot start speaking`);
        }
    }

    function stopSpeaking() {
        if (!state.isMuted) {
            state.isMuted = true;
            state.isAgentProcessing = true;
            logMessage(`🛑 MUTED - isMuted is now: ${state.isMuted}`);
            setStatus('Agent processing...');
            speakButton.querySelector('.speak-button-text').textContent = 'Processing...';
            speakButton.style.background = 'linear-gradient(135deg, #ffc107, #e0a800)';
            updateSpeakButtonState(state.isActive, state.isAgentSpeaking, state.isAgentProcessing);
            
            if (socket && socket.connected) {
                logMessage('📡 Sending end-of-speech signal');
                socket.emit('user_audio', new ArrayBuffer(0));
            }
        }
    }

    // --- Event Listeners ---
    startButton.addEventListener('click', async () => {
        if (state.isActive) {
            stopAudio(socket, logMessage);
            socket = null;
            state = { isActive: false, isMuted: true, isAgentSpeaking: false, isAgentProcessing: false };
            setStatus('Inactive');
            startButton.textContent = 'Start Voice Agent';
            updateSpeakButtonState(state.isActive, state.isAgentSpeaking, state.isAgentProcessing);
        } else {
            setStatus('Initializing...');
            const audioStarted = await startAudio(socket, logMessage, () => state.isMuted, () => state.isAgentSpeaking);
            if (audioStarted) {
                state.isActive = true;
                startButton.textContent = 'Stop Voice Agent';
                updateSpeakButtonState(state.isActive, state.isAgentSpeaking, state.isAgentProcessing);
                connectSocket();
            } else {
                 setStatus('Error starting audio.');
            }
        }
    });

    // Press-and-hold/click-and-click functionality for speak button
    speakButton.addEventListener('mousedown', startSpeaking);
    speakButton.addEventListener('mouseup', stopSpeaking);
    speakButton.addEventListener('mouseleave', stopSpeaking);
    speakButton.addEventListener('touchstart', (e) => { e.preventDefault(); startSpeaking(); }, { passive: false });
    speakButton.addEventListener('touchend', (e) => { e.preventDefault(); stopSpeaking(); }, { passive: false });
    speakButton.addEventListener('touchcancel', (e) => { e.preventDefault(); stopSpeaking(); }, { passive: false });
    
    // Initialize
    updateSpeakButtonState(state.isActive, state.isAgentSpeaking, state.isAgentProcessing);
    
    // Debug button element
    logMessage(`🔍 Button element found: ${speakButton ? 'YES' : 'NO'}`);
    logMessage(`🔍 Button ID: ${speakButton?.id}`);
    logMessage(`🔍 Button disabled: ${speakButton?.disabled}`);
    
    // Add error handling
    window.addEventListener('error', (e) => {
        logMessage(`❌ JavaScript Error: ${e.message} at ${e.filename}:${e.lineno}`, 'error');
    });

    // --- Other Event Listeners ---

    showLogsCheckbox.addEventListener('change', (e) => {
        if (e.target.checked) {
            logsContainer.style.display = 'block';
            logMessage('Debug logs are now visible');
        } else {
            logsContainer.style.display = 'none';
        }
    });

    fetchVoiceModels();
}); 