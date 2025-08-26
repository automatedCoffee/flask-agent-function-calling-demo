'use strict';

document.addEventListener("DOMContentLoaded", () => {
    // --- DOM Elements ---
    const startButton = document.getElementById('startButton');
    const voiceModelSelect = document.getElementById('voiceModel');
    const speakButton = document.getElementById('speakButton');

    // --- Session State ---
    let session = {
        socket: null,
        isActive: false,
        isMuted: true,
        isAgentSpeaking: false,
        isAgentProcessing: false,
        isConnecting: false,
        currentSessionId: null,
        availableSessions: []
    };

    /**
     * Callback from the audio module when the playback queue is empty.
     * This is the primary way the agent signals it has finished speaking.
     */
    function onPlaybackFinished() {
        logMessage('Playback finished callback received.');
        session.isAgentSpeaking = false;
        session.isAgentProcessing = false;
        setStatus('Agent Ready');
        updateSpeakButtonState(session, logMessage);
    }

    // Register the callback with the audio module
    setOnPlaybackFinished(onPlaybackFinished);

    // --- Socket.IO Connection ---
    
    /**
     * Establishes a WebSocket connection and sets up all event handlers.
     */
    function connectSocket(resumeSessionId = null) {
        if (session.isConnecting || (session.socket && session.socket.connected)) {
            logMessage('📡 Connection attempt blocked: already connecting or connected.', 'warn');
            return;
        }

        session.isConnecting = true;
        logMessage('📡 Connecting to socket...');

        session.socket = io({
            transports: ['websocket'],
            upgrade: true,
            timeout: 10000,
            forceNew: true // Ensures a clean connection
        });

        session.socket.on('connect', () => {
            session.isConnecting = false;
            logMessage('📡 Socket connected successfully.');
            setStatus('Connected, starting agent...');

            // Send session data for potential recovery
            const startData = {
                voiceModel: voiceModelSelect.value
            };

            if (resumeSessionId) {
                startData.session_id = resumeSessionId;
                logMessage(`🔄 Resuming session: ${resumeSessionId}`);
            }

            session.socket.emit('start_voice_agent', startData);
        });

        session.socket.on('disconnect', (reason) => {
            logMessage(`📡 Socket disconnected: ${reason}`, 'warn');
            // If the session was active, perform a clean shutdown.
            if (session.isActive) {
                stopSession();
            }
        });

        session.socket.on('connect_error', (error) => {
            logMessage(`📡 Socket connection error: ${error}`, 'error');
            session.isConnecting = false;
            if (session.isActive) {
                stopSession();
            }
        });

        session.socket.on('agent_response', (data) => {
            logMessage(`Agent Response: ${JSON.stringify(data)}`);
            switch (data.type) {
                case 'Welcome':
                    logMessage('🎉 Agent connected and ready.');
                    // The agent is now ready to be spoken to.
                    session.isAgentProcessing = false;
                    session.isAgentSpeaking = false;
                    updateSpeakButtonState(session, logMessage);
                    break;
                case 'ConversationText':
                    addConversationMessage('assistant', data.content);
                    break;
                case 'AgentAudioDone':
                    logMessage('✅ AgentAudioDone received (playback is managed by the audio queue).');
                    break;
                case 'Error':
                    logMessage(`Agent Error: ${data.description}`, 'error');
                    session.isAgentProcessing = false;
                    session.isAgentSpeaking = false;
                    updateSpeakButtonState(session, logMessage);
                    break;
            }
        });

        session.socket.on('agent_audio', (chunk) => {
            if (!session.isAgentSpeaking) {
                session.isAgentSpeaking = true;
                session.isAgentProcessing = false;
                logMessage('🗣️ Agent started speaking');
                setStatus('Agent speaking...');
                updateSpeakButtonState(session, logMessage);
            }
            // The audio module handles the queuing and playback
            addAudioToQueue(new Uint8Array(chunk), logMessage);
        });

        session.socket.on('session_started', (data) => {
            session.currentSessionId = data.session_id;
            logMessage(`📝 Session started: ${data.session_id} (messages: ${data.message_count})`);
        });

        session.socket.on('connection_status', (data) => {
            const status = data.connected ? '🟢 Connected' : '🔴 Disconnected';
            logMessage(`📊 ${status} - Session: ${data.session_id || 'None'} (${data.message_count || 0} messages)`);
            if (data.last_error) {
                logMessage(`⚠️ Connection error: ${data.last_error}`, 'warn');
            }
        });
    }

    // --- Session Management Functions ---

    async function loadAvailableSessions() {
        try {
            const response = await fetch('/sessions');
            const data = await response.json();
            session.availableSessions = data.sessions || [];
            return session.availableSessions;
        } catch (error) {
            logMessage(`Failed to load sessions: ${error}`, 'error');
            return [];
        }
    }

    function showSessionRecovery(sessions) {
        const recoveryDiv = document.getElementById('sessionRecovery');
        const sessionListDiv = document.getElementById('sessionList');

        if (sessions.length === 0) {
            recoveryDiv.style.display = 'none';
            return;
        }

        sessionListDiv.innerHTML = '';
        sessions.forEach(sess => {
            const sessionItem = document.createElement('div');
            sessionItem.className = 'session-item';
            sessionItem.dataset.sessionId = sess.session_id;

            const lastUpdated = new Date(sess.last_updated * 1000).toLocaleString();
            sessionItem.innerHTML = `
                <div><strong>${sess.industry} - ${sess.voiceModel}</strong></div>
                <div class="session-info">
                    Messages: ${sess.message_count} | Updated: ${lastUpdated}
                </div>
            `;

            sessionItem.addEventListener('click', () => {
                document.querySelectorAll('.session-item').forEach(item => {
                    item.classList.remove('selected');
                });
                sessionItem.classList.add('selected');
            });

            sessionListDiv.appendChild(sessionItem);
        });

        recoveryDiv.style.display = 'block';
    }

    function hideSessionRecovery() {
        document.getElementById('sessionRecovery').style.display = 'none';
    }

    // --- Speaking Logic (User Input) ---

    function startSpeaking() {
        if (!speakButton.disabled) {
            session.isMuted = false;
            logMessage('✅ UNMUTED - User started speaking.', 'user');
            setStatus('🎤 User speaking...');
            speakButton.querySelector('.speak-button-text').textContent = 'Speaking...';
            speakButton.style.background = 'linear-gradient(135deg, #28a745, #1e7e34)';
        } else {
            logMessage('❌ Cannot start speaking, button is disabled.');
        }
    }

    function stopSpeaking() {
        if (!session.isMuted) {
            session.isMuted = true;
            session.isAgentProcessing = true; // Agent will now process the input
            logMessage('🛑 MUTED - User stopped speaking.');
            setStatus('Agent processing...');
            updateSpeakButtonState(session, logMessage); // This will show "Processing..."
            
            // Send an empty buffer to signal the end of speech
            if (session.socket && session.socket.connected) {
                session.socket.emit('user_audio', new ArrayBuffer(0));
                logMessage("Sent end-of-speech signal.");
            }
        }
    }
    
    // --- Session Management ---

    async function startSession(resumeSessionId = null) {
        if (session.isActive) return;

        logMessage('Session starting...');
        setStatus('Initializing...');

        // Check for available sessions if not resuming a specific one
        if (!resumeSessionId) {
            const availableSessions = await loadAvailableSessions();
            if (availableSessions.length > 0) {
                showSessionRecovery(availableSessions);
                return; // Wait for user to choose
            }
        }

        const audioStarted = await startAudio(
            () => session.socket,
            logMessage,
            () => session.isMuted,
            () => session.isAgentSpeaking
        );

        if (audioStarted) {
            session.isActive = true;
            startButton.textContent = 'Stop Voice Agent';
            updateSpeakButtonState(session, logMessage); // Initial state should be disabled
            connectSocket(resumeSessionId);
        } else {
            setStatus('Error starting audio.');
            logMessage('Failed to initialize audio, session aborted.', 'error');
        }
    }

    function stopSession() {
        if (!session.isActive) return;

        logMessage('Session stopping...');
        
        // Disconnect socket first
        if (session.socket) {
            session.socket.emit('stop_voice_agent');
            session.socket.disconnect();
            session.socket = null;
        }

        // Stop audio hardware
        stopAudio(logMessage);

        // Reset session state completely
        session = { 
            socket: null, 
            isActive: false, 
            isMuted: true, 
            isAgentSpeaking: false, 
            isAgentProcessing: false, 
            isConnecting: false 
        };

        setStatus('Inactive');
        startButton.textContent = 'Start Voice Agent';
        updateSpeakButtonState(session, logMessage); // Should be disabled
        logMessage('Session stopped.');
    }

    // --- Main Event Listeners ---

    startButton.addEventListener('click', () => {
        if (session.isActive) {
            stopSession();
        } else {
            startSession();
        }
    });

    // Session recovery event handlers
    document.getElementById('resumeSessionBtn').addEventListener('click', () => {
        const selectedSession = document.querySelector('.session-item.selected');
        if (selectedSession) {
            const sessionId = selectedSession.dataset.sessionId;
            hideSessionRecovery();
            startSession(sessionId);
        } else {
            logMessage('Please select a session to resume.', 'warn');
        }
    });

    document.getElementById('newSessionBtn').addEventListener('click', async () => {
        hideSessionRecovery();
        // Force start a new session by passing null explicitly
        const audioStarted = await startAudio(
            () => session.socket,
            logMessage,
            () => session.isMuted,
            () => session.isAgentSpeaking
        );

        if (audioStarted) {
            session.isActive = true;
            startButton.textContent = 'Stop Voice Agent';
            updateSpeakButtonState(session, logMessage);
            connectSocket(null); // Explicitly pass null for new session
        } else {
            setStatus('Error starting audio.');
            logMessage('Failed to initialize audio, session aborted.', 'error');
        }
    });

    // Press-and-hold functionality for the speak button
    speakButton.addEventListener('mousedown', startSpeaking);
    speakButton.addEventListener('mouseup', stopSpeaking);
    speakButton.addEventListener('mouseleave', stopSpeaking); // Stop if mouse leaves button area
    speakButton.addEventListener('touchstart', (e) => { e.preventDefault(); startSpeaking(); }, { passive: false });
    speakButton.addEventListener('touchend', (e) => { e.preventDefault(); stopSpeaking(); }, { passive: false });
    speakButton.addEventListener('touchcancel', (e) => { e.preventDefault(); stopSpeaking(); }, { passive: false });
    
    // --- Initial Page Load ---

    // Set up UI event listeners from ui.js (for log toggling, etc.)
    setupUIEventListeners(logMessage);

    // Set initial button state to disabled
    updateSpeakButtonState(session, logMessage);
    
    // Global error handler
    window.addEventListener('error', (e) => {
        logMessage(`❌ Uncaught JavaScript Error: ${e.message} at ${e.filename}:${e.lineno}`, 'error');
    });

    // --- Debugging hooks ---
    window.checkAppStates = function() {
        logMessage(`📊 APP STATES: isActive=${session.isActive}, isAgentSpeaking=${session.isAgentSpeaking}, isAgentProcessing=${session.isAgentProcessing}, isMuted=${session.isMuted}`);
        logMessage(`📊 SOCKET: connected=${session.socket?.connected}`);
        checkAudio(logMessage); // Call the debug function from audio.js
    };
}); 