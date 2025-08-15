// DOM Elements
const startButton = document.getElementById('startButton');
const statusDiv = document.getElementById('status');
const logsDiv = document.getElementById('logs');
const conversationDiv = document.getElementById('conversation');
const voiceModelSelect = document.getElementById('voiceModel');
const showLogsCheckbox = document.getElementById('showLogs');
const logsContainer = document.getElementById('logsContainer');
const speakButton = document.getElementById('speakButton');

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
    updateSpeakButtonState(true, false, false);
    logMessage(`🧪 TEST RESULT: Button disabled = ${speakButton.disabled}`);
};

window.checkStates = function(isActive, isAgentSpeaking, isAgentProcessing, isMuted, socket) {
    logMessage(`📊 STATES: isActive=${isActive}, isAgentSpeaking=${isAgentSpeaking}, isAgentProcessing=${isAgentProcessing}, isMuted=${isMuted}`);
    logMessage(`📊 BUTTON: disabled=${speakButton.disabled}, socket=${socket?.connected}`);
};

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