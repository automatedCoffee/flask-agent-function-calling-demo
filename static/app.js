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

    let session = {
        socket: null,
        isActive: false,
        isMuted: true,
        isAgentSpeaking: false,
        isAgentProcessing: false,
        isConnecting: false, // Add a lock to prevent race conditions
    };

    /**
     * Callback function passed to the audio module.
     * It is called when the audio playback queue is empty.
     */
    function onPlaybackFinished() {
        session.isAgentSpeaking = false;
        session.isAgentProcessing = false;
        setStatus('Agent Ready');
        updateSpeakButtonState(session);
    }

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
        if (session.isActive) return false;
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

            session.isActive = true;
            startButton.textContent = 'Stop Voice Agent';
            setStatus('Connected, starting agent...');
            logMessage('Audio pipeline ready.');
            logMessage(`Microphone connected - Sample rate: ${audioContext.sampleRate}Hz`);
            logMessage(`Audio mode: Press to Speak button only`);
            
            // Initialize states for new session
            session.isAgentSpeaking = false;
            session.isAgentProcessing = false;
            session.isMuted = true;
            updateSpeakButtonState(session); // This should keep button disabled until agent is ready
            
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
            session.isActive = false;
            return false;
        }
    }

    function stopAudio(logMessage) {
        if (!session.isActive) return;
        session.isActive = false;
        session.isAgentSpeaking = false;
        session.isAgentProcessing = false;
        session.isMuted = true;
        
        logMessage('Stopping audio pipeline...');
        if (session.socket) {
            session.socket.emit('stop_voice_agent');
            session.socket.disconnect();
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

    /**
     * Establishes a WebSocket connection and sets up event handlers.
     */
    function connectSocket() {
        if (session.isConnecting || (session.socket && session.socket.connected)) {
            logMessage('📡 Connection attempt blocked: already connecting or connected.', 'warn');
            return;
        }

        session.isConnecting = true;
        logMessage('📡 Connecting to socket...');
        session.socket = io({
            transports: ['websocket'],
            upgrade: true,
            rememberUpgrade: true,
            timeout: 10000,
            forceNew: true
        });

        session.socket.on('connect', () => {
            session.isConnecting = false;
            logMessage('📡 Socket connected successfully.');
            setStatus('Connected, starting agent...');
            session.socket.emit('start_voice_agent', { voiceModel: voiceModelSelect.value });
        });

        session.socket.on('disconnect', (reason) => {
            logMessage(`📡 Socket disconnected: ${reason}`, 'warn');
            // On a clean disconnect, shut down the session.
            if (session.isActive) {
                startButton.click();
            }
        });

        session.socket.on('connect_error', (error) => {
            logMessage(`📡 Socket connection error: ${error}`, 'error');
            session.isConnecting = false;
            if (session.isActive) {
                startButton.click();
            }
        });

        session.socket.on('agent_response', (data) => {
            logMessage(`Agent Response: ${JSON.stringify(data)}`);
            switch (data.type) {
                case 'Welcome':
                    logMessage('🎉 Agent connected.');
                    break;
                case 'ConversationText':
                    addConversationMessage('assistant', data.content);
                    break;
                case 'AgentAudioDone':
                    logMessage('✅ AgentAudioDone received (playback is managed by audio queue).');
                    break;
                case 'Error':
                    logMessage(`Agent Error: ${data.description}`, 'error');
                    session.isAgentProcessing = false;
                    session.isAgentSpeaking = false;
                    updateSpeakButtonState(session);
                    break;
            }
        });

        session.socket.on('agent_audio', (chunk) => {
            if (!session.isAgentSpeaking) {
                session.isAgentSpeaking = true;
                session.isAgentProcessing = false;
                logMessage('🗣️ Agent started speaking');
                setStatus('Agent speaking...');
                updateSpeakButtonState(session);
            }
            addAudioToQueue(new Uint8Array(chunk), logMessage);
        });
    }

    // Function to update speak button state based on current conditions
    function updateSpeakButtonState(session) {
        const shouldEnable = session.isActive && !session.isAgentSpeaking && !session.isAgentProcessing;
        speakButton.disabled = !shouldEnable;
        speakButton.style.opacity = shouldEnable ? '1' : '0.6';
        
        logMessage(`Button state check - Active: ${session.isActive}, Speaking: ${session.isAgentSpeaking}, Processing: ${session.isAgentProcessing}, ShouldEnable: ${shouldEnable}`);
        
        if (shouldEnable) {
            logMessage('✅ Hold to Speak button ENABLED');
            speakButton.style.background = 'linear-gradient(135deg, #007bff, #0056b3)';
            speakButton.querySelector('.speak-button-text').textContent = 'Hold to Speak';
        } else {
            logMessage(`❌ Hold to Speak button DISABLED - Active: ${session.isActive}, Speaking: ${session.isAgentSpeaking}, Processing: ${session.isAgentProcessing}`);
        }
    }

    // Manual test function for debugging
    window.testButton = function() {
        logMessage('🧪 MANUAL TEST: Forcing button enable');
        session.isActive = true;
        session.isAgentSpeaking = false;
        session.isAgentProcessing = false;
        updateSpeakButtonState(session);
        logMessage(`🧪 TEST RESULT: Button disabled = ${speakButton.disabled}`);
    };
    
    window.checkStates = function() {
        logMessage(`📊 STATES: isActive=${session.isActive}, isAgentSpeaking=${session.isAgentSpeaking}, isAgentProcessing=${session.isAgentProcessing}, isMuted=${session.isMuted}`);
        logMessage(`📊 BUTTON: disabled=${speakButton.disabled}, socket=${session.socket?.connected}`);
    };
    
    window.forceStart = function() {
        logMessage('🔧 FORCE START: Manually starting speaking');
        session.isMuted = false;
        logMessage(`🔧 isMuted is now: ${session.isMuted}`);
    };
    
    window.testSpeak = function() {
        logMessage(' TEST: Manual speak test');
        if (session.isMuted) {
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
        logMessage(`  - exists: ${session.socket ? 'YES' : 'NO'}`);
        logMessage(`  - connected: ${session.socket?.connected}`);
        logMessage(`  - id: ${session.socket?.id || 'N/A'}`);
        if (session.socket) {
            logMessage(`  - transport: ${session.socket.io?.engine?.transport?.name || 'N/A'}`);
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
        if (session.socket && !session.socket.connected && session.isActive) {
            logMessage('⚠️ HEALTH CHECK: Socket disconnected while active, attempting reconnect');
            session.socket.connect();
        }
        
        // Also log socket status periodically when active
        if (session.isActive && Math.random() < 0.1) { // 10% chance each check
            logMessage(`💓 HEALTH: Socket connected: ${session.socket?.connected}, Active: ${session.isActive}, Speaking: ${!session.isMuted}`);
        }
    }, 2000); // Check every 2 seconds instead of 5

    // --- Speaking Logic ---
    function startSpeaking() {
        logMessage(`🎤 startSpeaking() ENTRY - disabled: ${speakButton.disabled}`);
        if (!speakButton.disabled) {
            session.isMuted = false;
            logMessage(`✅ UNMUTED - isMuted is now: ${session.isMuted}`, 'user');
            setStatus('🎤 SPEAKING - Hold button and talk');
            speakButton.querySelector('.speak-button-text').textContent = 'Speaking...';
            speakButton.style.background = 'linear-gradient(135deg, #28a745, #1e7e34)';
        } else {
            logMessage(`❌ BUTTON DISABLED - Cannot start speaking`);
        }
    }

    function stopSpeaking() {
        if (!session.isMuted) {
            session.isMuted = true;
            session.isAgentProcessing = true;
            logMessage(`🛑 MUTED - isMuted is now: ${session.isMuted}`);
            setStatus('Agent processing...');
            speakButton.querySelector('.speak-button-text').textContent = 'Processing...';
            speakButton.style.background = 'linear-gradient(135deg, #ffc107, #e0a800)';
            updateSpeakButtonState(session);
            
            if (session.socket && session.socket.connected) {
                session.socket.emit('user_audio', new ArrayBuffer(0));
            }
        }
    }

    // --- Event Listeners ---
    startButton.addEventListener('click', async () => {
        if (session.isActive) {
            // --- Stop the session ---
            logMessage('Session stopping...');
            if (session.socket) {
                session.socket.emit('stop_voice_agent');
                session.socket.disconnect();
                session.socket = null;
            }
            stopAudio(logMessage);
            session = { isActive: false, isMuted: true, isAgentSpeaking: false, isAgentProcessing: false, isConnecting: false };
            setStatus('Inactive');
            startButton.textContent = 'Start Voice Agent';
            updateSpeakButtonState(session);
            logMessage('Session stopped.');
        } else {
            // --- Start the session ---
            logMessage('Session starting...');
            setStatus('Initializing...');
            
            const audioStarted = await startAudio(
                () => session.socket,
                logMessage,
                () => session.isMuted,
                () => session.isAgentSpeaking
            );

            if (audioStarted) {
                session.isActive = true;
                startButton.textContent = 'Stop Voice Agent';
                updateSpeakButtonState(session);
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
    updateSpeakButtonState(session);
    
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