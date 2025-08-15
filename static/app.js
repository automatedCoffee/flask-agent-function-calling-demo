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
    let audioContext = null;
    let audioWorkletNode = null;
    let microphoneStream = null;
    let isActive = false;
    let isMuted = true; // Start muted, only speak when button is pressed
    let isAgentSpeaking = false; // Track when agent is playing audio
    let isAgentProcessing = false; // Track when agent is processing user input
    let audioQueue = [];
    let nextPlayTime = 0; // For continuous audio scheduling
    let lastAudioSendTime = 0;
    const AUDIO_SEND_INTERVAL = 20; // Send audio every 20ms (was 100ms - too aggressive)

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

    async function startAudio(socket, logMessage, setStatus, updateSpeakButtonState, isMuted, isAgentSpeaking) {
        if (isActive) return false;
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

            isActive = true;
            startButton.textContent = 'Stop Voice Agent';
            setStatus('Connected, starting agent...');
            logMessage('Audio pipeline ready.');
            logMessage(`Microphone connected - Sample rate: ${audioContext.sampleRate}Hz`);
            logMessage(`Audio mode: Press to Speak button only`);
            
            // Initialize states for new session
            isAgentSpeaking = false;
            isAgentProcessing = false;
            isMuted = true;
            updateSpeakButtonState(isActive, isAgentSpeaking, isAgentProcessing); // This should keep button disabled until agent is ready
            
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
            isActive = false;
            return false;
        }
    }

    function stopAudio(socket) {
        if (!isActive) return;
        isActive = false;
        isAgentSpeaking = false;
        isAgentProcessing = false;
        isMuted = true;
        
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
        audioQueue = [];
        nextPlayTime = 0;
        
        setStatus('Inactive');
        startButton.textContent = 'Start Voice Agent';
        
        // Reset speak button to disabled state
        speakButton.disabled = true;
        speakButton.style.opacity = '0.6';
        speakButton.querySelector('.speak-button-text').textContent = 'Hold to Speak';
        speakButton.style.background = 'linear-gradient(135deg, #007bff, #0056b3)';
    }

    function playNextAudioChunk() {
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
                        updateSpeakButtonState(isActive, isAgentSpeaking, isAgentProcessing);
                    }
                }, 100); // Much shorter delay since AgentAudioDone should handle most cases
            }
            return;
        }

        const audioData = audioQueue.shift();
        
        if (audioContext.state === 'suspended') {
            audioContext.resume().then(() => {
                playRawPCM(audioData);
            });
        } else {
            playRawPCM(audioData);
        }
    }

    function playRawPCM(audioData) {
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

    // --- WebSocket Logic ---

    function connectSocket() {
        if (socket && socket.connected) {
            logMessage('📡 Socket already connected');
            return;
        }

        logMessage('📡 Connecting to socket...');
        socket = io({
            transports: ['websocket', 'polling'], // Try WebSocket first, fallback to polling
            upgrade: true,
            rememberUpgrade: true,
            timeout: 20000,
            forceNew: true
        });

        socket.on('connect', () => {
            logMessage('📡 Socket connected successfully.');
            setStatus('Connected, starting agent...');
            const sessionConfig = {
                voiceModel: voiceModelSelect.value,
            };
            socket.emit('start_voice_agent', sessionConfig);
        });

        socket.on('disconnect', (reason) => {
            logMessage(`📡 Socket disconnected: ${reason}`, 'warn');
            setStatus('Disconnected - Reconnecting...');
            
            // Immediately try to reconnect if we were in the middle of something
            if (isAgentProcessing || !isMuted) {
                logMessage('🚨 CRITICAL: Socket disconnected while active, immediate reconnect');
                socket.connect();
            } else {
                // Normal reconnection after a short delay
                setTimeout(() => {
                    if (!socket.connected) {
                        logMessage('📡 Attempting to reconnect...');
                        socket.connect();
                    }
                }, 1000); // Reduced from 2000ms
            }
        });

        socket.on('connect_error', (error) => {
            logMessage(`📡 Socket connection error: ${error}`, 'error');
            setStatus('Connection Error - Retrying...');
            
            // Retry connection after short delay
            setTimeout(() => {
                if (!socket.connected) {
                    logMessage('🔄 Retrying connection after error...');
                    socket.connect();
                }
            }, 2000);
        });

        socket.on('reconnect', (attemptNumber) => {
            logMessage(`📡 Socket reconnected after ${attemptNumber} attempts`);
            setStatus('Reconnected');
            
            // Restart voice agent if we were active
            if (isActive) {
                const sessionConfig = {
                    voiceModel: voiceModelSelect.value,
                };
                socket.emit('start_voice_agent', sessionConfig);
            }
        });

        socket.on('agent_response', (data) => {
            logMessage(`Agent Response: ${JSON.stringify(data)}`);
            switch (data.type) {
                case 'Welcome':
                    setStatus('Agent Ready');
                    logMessage('🎉 Agent connected - waiting for greeting audio');
                    // Don't enable button yet - wait for greeting audio to finish
                    break;
                case 'ConversationText':
                    addConversationMessage('assistant', data.content);
                    // Agent is responding, so it's no longer processing user input
                    isAgentProcessing = false;
                    logMessage('📝 Agent response received - waiting for AgentAudioDone');
                    break;
                case 'AgentAudioDone':
                    // Agent has finished speaking/responding - enable button immediately
                    isAgentSpeaking = false;
                    isAgentProcessing = false;
                    logMessage('✅ AgentAudioDone received - enabling button immediately');
                    setStatus('Agent Ready - Press button to speak');
                    updateSpeakButtonState(isActive, isAgentSpeaking, isAgentProcessing);
                    break;
                case 'Error':
                    logMessage(`Agent Error: ${data.description}`, 'error');
                    setStatus('Error');
                    isAgentProcessing = false;
                    isAgentSpeaking = false; // Make sure we're not stuck in speaking state
                    updateSpeakButtonState(isActive, isAgentSpeaking, isAgentProcessing);
                    break;
            }
        });

        socket.on('agent_audio', (chunk) => {
            audioQueue.push(new Uint8Array(chunk));
            // Start agent speaking if not already
            if (!isAgentSpeaking) {
                isAgentSpeaking = true;
                isAgentProcessing = false; // Clear processing state when agent starts speaking
                logMessage('🗣️ Agent started speaking');
                setStatus('Agent speaking...');
                updateSpeakButtonState(isActive, isAgentSpeaking, isAgentProcessing); // Disable button while agent speaks
            }
            playNextAudioChunk();
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
        isActive = true;
        isAgentSpeaking = false;
        isAgentProcessing = false;
        updateSpeakButtonState(isActive, isAgentSpeaking, isAgentProcessing);
        logMessage(`🧪 TEST RESULT: Button disabled = ${speakButton.disabled}`);
    };
    
    window.checkStates = function() {
        logMessage(`📊 STATES: isActive=${isActive}, isAgentSpeaking=${isAgentSpeaking}, isAgentProcessing=${isAgentProcessing}, isMuted=${isMuted}`);
        logMessage(`📊 BUTTON: disabled=${speakButton.disabled}, socket=${socket?.connected}`);
    };
    
    window.forceStart = function() {
        logMessage('🔧 FORCE START: Manually starting speaking');
        isMuted = false;
        logMessage(`🔧 isMuted is now: ${isMuted}`);
    };
    
    window.testSpeak = function() {
        logMessage(' TEST: Manual speak test');
        if (isMuted) {
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
        if (socket && !socket.connected && isActive) {
            logMessage('⚠️ HEALTH CHECK: Socket disconnected while active, attempting reconnect');
            socket.connect();
        }
        
        // Also log socket status periodically when active
        if (isActive && Math.random() < 0.1) { // 10% chance each check
            logMessage(`💓 HEALTH: Socket connected: ${socket?.connected}, Active: ${isActive}, Speaking: ${!isMuted}`);
        }
    }, 2000); // Check every 2 seconds instead of 5

    // --- Speaking Logic ---
    function startSpeaking() {
        logMessage(`🎤 startSpeaking() ENTRY - disabled: ${speakButton.disabled}`);
        if (!speakButton.disabled) {
            isMuted = false;
            logMessage(`✅ UNMUTED - isMuted is now: ${isMuted}`, 'user');
            setStatus('🎤 SPEAKING - Hold button and talk');
            speakButton.querySelector('.speak-button-text').textContent = 'Speaking...';
            speakButton.style.background = 'linear-gradient(135deg, #28a745, #1e7e34)';
        } else {
            logMessage(`❌ BUTTON DISABLED - Cannot start speaking`);
        }
    }

    function stopSpeaking() {
        if (!isMuted) {
            isMuted = true;
            isAgentProcessing = true;
            logMessage(`🛑 MUTED - isMuted is now: ${isMuted}`);
            setStatus('Agent processing...');
            speakButton.querySelector('.speak-button-text').textContent = 'Processing...';
            speakButton.style.background = 'linear-gradient(135deg, #ffc107, #e0a800)';
            updateSpeakButtonState(isActive, isAgentSpeaking, isAgentProcessing);
            
            if (socket && socket.connected) {
                logMessage('📡 Sending end-of-speech signal');
                socket.emit('user_audio', new ArrayBuffer(0));
            }
            
            setTimeout(() => {
                if (isAgentProcessing) {
                    logMessage('⚠️ SAFETY: Re-enabling button');
                    isAgentProcessing = false;
                    isAgentSpeaking = false;
                    updateSpeakButtonState(isActive, isAgentSpeaking, isAgentProcessing);
                }
            }, 15000);
        }
    }

    // --- Event Listeners ---
    startButton.addEventListener('click', async () => {
        if (isActive) {
            stopAudio(socket);
            isActive = false;
            isAgentSpeaking = false;
            isAgentProcessing = false;
            isMuted = true;
            setStatus('Inactive');
            startButton.textContent = 'Start Voice Agent';
            updateSpeakButtonState(isActive, isAgentSpeaking, isAgentProcessing);
        } else {
            const audioStarted = await startAudio(socket, logMessage, setStatus, updateSpeakButtonState, isMuted, isAgentSpeaking);
            if (audioStarted) {
                isActive = true;
                startButton.textContent = 'Stop Voice Agent';
                isAgentSpeaking = false;
                isAgentProcessing = false;
                isMuted = true;
                updateSpeakButtonState(isActive, isAgentSpeaking, isAgentProcessing);
                connectSocket();
            }
        }
    });

    speakButton.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (isMuted) {
            startSpeaking();
        } else {
            stopSpeaking();
        }
    });

    speakButton.addEventListener('mousedown', (e) => {
        e.preventDefault();
        startSpeaking();
    });

    speakButton.addEventListener('mouseup', stopSpeaking);
    speakButton.addEventListener('mouseleave', stopSpeaking);
    speakButton.addEventListener('touchstart', (e) => {
        e.preventDefault();
        e.stopPropagation();
        startSpeaking();
    }, { passive: false });

    speakButton.addEventListener('touchend', (e) => {
        e.preventDefault();
        e.stopPropagation();
        stopSpeaking();
    }, { passive: false });

    speakButton.addEventListener('touchcancel', (e) => {
        e.preventDefault();
        e.stopPropagation();
        stopSpeaking();
    }, { passive: false });

    // Initialize speak button state
    speakButton.disabled = true;
    speakButton.style.opacity = '0.6';
    logMessage('Hold to Speak button initialized (disabled)');
    
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