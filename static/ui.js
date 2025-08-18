// DOM Elements are now initialized in app.js and passed to functions
// const startButton = document.getElementById('startButton');
// const statusDiv = document.getElementById('status');
// const logsDiv = document.getElementById('logs');
// const conversationDiv = document.getElementById('conversation');
// const voiceModelSelect = document.getElementById('voiceModel');
// const showLogsCheckbox = document.getElementById('showLogs');
// const logsContainer = document.getElementById('logsContainer');
// const speakButton = document.getElementById('speakButton');

// --- UI and Logging ---

function setStatus(message) {
    const statusDiv = document.getElementById('status');
    statusDiv.textContent = `Status: ${message}`;
}

function logMessage(message, type = 'info') {
    const logsDiv = document.getElementById('logs');
    const timestamp = new Date().toLocaleTimeString();
    const logClass = type === 'error' ? 'log-error' : type === 'warn' ? 'log-warn' : type === 'user' ? 'log-user' : 'log-info';
    logsDiv.innerHTML += `<div class="${logClass}">[${timestamp}] ${message}</div>`;
    logsDiv.scrollTop = logsDiv.scrollHeight;
}

function addConversationMessage(role, text) {
    const conversationDiv = document.getElementById('conversation');
    const messageBubble = document.createElement('div');
    messageBubble.className = `message-bubble ${role}`;
    messageBubble.textContent = text;
    conversationDiv.appendChild(messageBubble);
    conversationDiv.scrollTop = conversationDiv.scrollHeight;
}

// --- Scroll Syncing ---
function setupScrollSync() {
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
}

// --- API Calls ---

async function fetchVoiceModels(logMessage) {
    try {
        const response = await fetch('/tts-models');
        const data = await response.json();
        const voiceModelSelect = document.getElementById('voiceModel');
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

function updateSpeakButtonState({ isActive, isAgentSpeaking, isAgentProcessing }, logMessage) {
    const speakButton = document.getElementById('speakButton');
    const shouldEnable = isActive && !isAgentSpeaking && !isAgentProcessing;
    speakButton.disabled = !shouldEnable;
    speakButton.style.opacity = shouldEnable ? '1' : '0.6';

    const textEl = speakButton.querySelector('.speak-button-text');

    if (shouldEnable) {
        speakButton.style.background = 'linear-gradient(135deg, #007bff, #0056b3)';
        textEl.textContent = 'Hold to Speak';
    } else if (isAgentProcessing) {
        speakButton.style.background = 'linear-gradient(135deg, #ffc107, #e0a800)';
        textEl.textContent = 'Processing...';
    } else if (isAgentSpeaking) {
        speakButton.style.background = 'linear-gradient(135deg, #6c757d, #5a6268)';
        textEl.textContent = 'Agent Speaking...';
    } else {
        speakButton.style.background = 'linear-gradient(135deg, #6c757d, #5a6268)';
        textEl.textContent = 'Hold to Speak';
    }
    
    logMessage(`Button state update: enabled=${shouldEnable} (Active: ${isActive}, Speaking: ${isAgentSpeaking}, Processing: ${isAgentProcessing})`);
}


// --- Event Listener Setup ---

function setupUIEventListeners(logMessage) {
    const showLogsCheckbox = document.getElementById('showLogs');
    const logsContainer = document.getElementById('logsContainer');

    showLogsCheckbox.addEventListener('change', (e) => {
        if (e.target.checked) {
            logsContainer.style.display = 'block';
            logMessage('Debug logs are now visible');
        } else {
            logsContainer.style.display = 'none';
        }
    });

    // Initial setup
    fetchVoiceModels(logMessage);
    setupScrollSync();
} 