from flask import Flask, render_template, jsonify, send_from_directory
from flask_socketio import SocketIO
import asyncio
import websockets
import os
import json
import queue
import requests
import random
import time
from dotenv import load_dotenv

# Try to import gevent for compatibility, fallback gracefully
try:
    import gevent
    HAS_GEVENT = True
except ImportError:
    HAS_GEVENT = False
from common.agent_functions import FUNCTION_MAP
from common.agent_templates import AgentTemplates
import logging
from common.log_formatter import CustomFormatter
import threading
import signal # Import the signal module
import time # Import the time module

# Load environment variables from .env file
load_dotenv()

# Configure Flask and SocketIO
app = Flask(__name__, static_folder="./static", static_url_path="/")
# Explicitly use the 'threading' async mode. This is the most robust and
# avoids conflicts with the asyncio code running in the background.
# Add even larger packet size limits to prevent "Too many packets in payload" errors
socketio = SocketIO(
    app, 
    cors_allowed_origins="*", 
    # Let Flask-SocketIO auto-select the best async mode (eventlet preferred)
    async_mode=None,
    max_http_buffer_size=32*1024*1024,  # 32MB buffer (was 16MB)
    ping_timeout=180,  # 3 minutes (was 2 minutes)
    ping_interval=30   # 30 seconds (was 25 seconds)
)

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
console_handler = logging.StreamHandler()
console_handler.setFormatter(CustomFormatter())
logger.addHandler(console_handler)
logger.propagate = False


# --- Graceful Shutdown Handler ---
# This ensures that background threads and loops are terminated correctly
_shutdown_event = threading.Event()

def cleanup_old_sessions(max_age_hours=24):
    """Clean up old session files to prevent disk space issues"""
    try:
        sessions_dir = "sessions"
        if not os.path.exists(sessions_dir):
            return

        current_time = time.time()
        max_age_seconds = max_age_hours * 3600

        for session_dir in os.listdir(sessions_dir):
            session_path = os.path.join(sessions_dir, session_dir)
            state_file = os.path.join(session_path, "state.json")

            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r') as f:
                        state = json.load(f)

                    last_updated = state.get("timestamp", current_time)
                    if current_time - last_updated > max_age_seconds:
                        import shutil
                        shutil.rmtree(session_path)
                        logger.info(f"Cleaned up old session: {session_dir}")
                except Exception as e:
                    logger.warning(f"Error checking session {session_dir}: {e}")
    except Exception as e:
        logger.warning(f"Error during session cleanup: {e}")

def _safe_sleep(seconds):
    """Sleep function that works with both threading and gevent"""
    try:
        if HAS_GEVENT:
            gevent.sleep(seconds)
        else:
            time.sleep(seconds)
    except Exception as e:
        logger.warning(f"Sleep interrupted: {e}")

def _graceful_shutdown_handler(signum, frame):
    """Signal handler for graceful shutdown."""
    logger.info("Shutdown signal received. Cleaning up...")

    # Stop voice agent gracefully
    global voice_agent, _agent_thread
    if voice_agent:
        voice_agent.stop()
    if _agent_thread and _agent_thread.is_alive():
        _agent_thread.join(timeout=5)

    _shutdown_event.set()

    # Clean up old sessions before shutdown
    cleanup_old_sessions()

    # Allow some time for cleanup (gevent-compatible)
    _safe_sleep(0.1)  # Much shorter sleep to avoid blocking
    os._exit(0)

# Register signal handlers for graceful termination
signal.signal(signal.SIGINT, _graceful_shutdown_handler)
signal.signal(signal.SIGTERM, _graceful_shutdown_handler)


# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/audio-processor.js')
def serve_audio_processor():
    return send_from_directory('static', 'audio-processor.js', mimetype='application/javascript')

@app.route("/industries")
def get_industries():
    return AgentTemplates.get_available_industries()

@app.route("/tts-models")
def get_tts_models():
    try:
        dg_api_key = os.environ.get("DEEPGRAM_API_KEY")
        if not dg_api_key:
            return jsonify({"error": "DEEPGRAM_API_KEY not set"}), 500
        response = requests.get(
            "https://api.deepgram.com/v1/models",
            headers={"Authorization": f"Token {dg_api_key}"},
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        formatted_models = [
            {
                "name": model.get("canonical_name", model.get("name")),
                "display_name": model.get("name"),
                "language": model.get("languages", ["en"])[0],
            }
            for model in data.get("tts", [])
            if model.get("architecture") == "aura-2"
        ]
        return jsonify({"models": formatted_models})
    except Exception as e:
        logger.error(f"Error fetching TTS models: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/sessions")
def get_sessions():
    """Get list of available sessions for recovery"""
    try:
        sessions_dir = "sessions"
        if not os.path.exists(sessions_dir):
            return jsonify({"sessions": []})

        sessions = []
        for session_dir in os.listdir(sessions_dir):
            state_file = os.path.join(sessions_dir, session_dir, "state.json")
            if os.path.exists(state_file):
                try:
                    with open(state_file, 'r') as f:
                        state = json.load(f)
                    sessions.append({
                        "session_id": state.get("session_id"),
                        "industry": state.get("industry", "unknown"),
                        "voiceModel": state.get("voiceModel", "unknown"),
                        "message_count": state.get("message_count", 0),
                        "start_time": state.get("start_time"),
                        "last_updated": state.get("timestamp"),
                        "is_connected": state.get("is_connected", False)
                    })
                except Exception as e:
                    logger.warning(f"Error reading session {session_dir}: {e}")

        # Sort by last updated, most recent first
        sessions.sort(key=lambda x: x.get("last_updated", 0), reverse=True)
        return jsonify({"sessions": sessions})
    except Exception as e:
        logger.error(f"Error listing sessions: {e}")
        return jsonify({"error": str(e)}), 500


# --- Voice Agent Class ---
class VoiceAgent:
    def __init__(self, industry="tech_support", voiceModel="aura-2-thalia-en", voiceName="", session_id=None):
        self.industry = industry
        self.voiceModel = voiceModel
        self.voiceName = voiceName
        self.session_id = session_id or f"session_{int(time.time())}"
        self.dg_client = None
        self.audio_queue = queue.Queue(maxsize=1000)  # Prevent memory issues
        self.is_running = False
        self.is_connected = False
        self.connection_attempts = 0
        self.max_connection_attempts = 5
        self.reconnect_delay = 1.0  # Start with 1 second delay
        self.max_reconnect_delay = 30.0  # Max 30 seconds
        self.last_connection_error = None
        self.message_count = 0
        self.start_time = time.time()

        # FIX: pass keyword args to avoid parameter order mismatch
        self.agent_templates = AgentTemplates(industry=industry, voiceModel=voiceModel, voiceName=voiceName)

        # Create session directory for persistence
        self.session_dir = os.path.join("sessions", self.session_id)
        os.makedirs(self.session_dir, exist_ok=True)
        self.state_file = os.path.join(self.session_dir, "state.json")

        # Load previous state if available
        self.load_state()

    def save_state(self):
        """Save current session state to disk"""
        try:
            state = {
                "session_id": self.session_id,
                "industry": self.industry,
                "voiceModel": self.voiceModel,
                "voiceName": self.voiceName,
                "message_count": self.message_count,
                "start_time": self.start_time,
                "connection_attempts": self.connection_attempts,
                "last_connection_error": str(self.last_connection_error) if self.last_connection_error else None,
                "is_connected": self.is_connected,
                "timestamp": time.time()
            }
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save session state: {e}")

    def load_state(self):
        """Load previous session state from disk"""
        try:
            if os.path.exists(self.state_file):
                with open(self.state_file, 'r') as f:
                    state = json.load(f)

                # Restore state
                self.message_count = state.get("message_count", 0)
                self.connection_attempts = state.get("connection_attempts", 0)
                if state.get("last_connection_error"):
                    self.last_connection_error = Exception(state["last_connection_error"])

                logger.info(f"Restored session state for {self.session_id}")
        except Exception as e:
            logger.warning(f"Failed to load session state: {e}")

    def send_audio(self, audio_chunk):
        if self.is_running and self.is_connected:
            try:
                self.audio_queue.put(audio_chunk, timeout=0.1)  # Non-blocking with timeout
            except queue.Full:
                logger.warning("Audio queue full, dropping audio chunk")
        elif not self.is_connected:
            logger.debug("Not connected, audio chunk ignored")

    async def _audio_sender(self, ws):
        try:
            while self.is_running and not _shutdown_event.is_set():
                try:
                    audio_chunk = self.audio_queue.get_nowait()
                    if audio_chunk is not None:
                        try:
                            # Coerce to bytes for the Deepgram WS client
                            if isinstance(audio_chunk, (bytes, bytearray, memoryview)):
                                data_bytes = bytes(audio_chunk)
                            elif isinstance(audio_chunk, list):
                                data_bytes = bytes(audio_chunk)
                            else:
                                data_bytes = bytes(audio_chunk)

                            await ws.send(data_bytes)

                            # Log when sending empty buffer (end-of-speech signal)
                            if len(data_bytes) == 0:
                                logger.info("Sent end-of-speech signal to Deepgram")
                        except Exception as send_err:
                            logger.error(f"Failed to send audio chunk to Deepgram: {send_err}")
                except queue.Empty:
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            logger.info("Audio sender task cancelled.")
        except Exception as e:
            logger.error(f"Error in audio sender: {e}")
        finally:
            logger.info("Audio sender loop finished.")

    async def _receiver(self, ws):
        try:
            async for message in ws:
                if not self.is_running or _shutdown_event.is_set():
                    break
                try:
                    if isinstance(message, str):
                        msg_json = json.loads(message)
                        socketio.emit("agent_response", msg_json)
                        logger.info(f"Server -> Browser: {json.dumps(msg_json)}")

                        # Track messages for state management
                        self.message_count += 1

                        if msg_json.get("type") == 'FunctionCallRequest':
                            # Clear any lingering audio chunks from the queue. This is crucial to prevent
                            # a race condition where an old "end-of-speech" signal gets sent after
                            # the function call response, confusing the Deepgram API.
                            while not self.audio_queue.empty():
                                try:
                                    self.audio_queue.get_nowait()
                                except queue.Empty:
                                    break
                            logger.info("Audio queue cleared for function call.")
                            await self._handle_function_call(ws, msg_json)

                        # Save state periodically (every 10 messages)
                        if self.message_count % 10 == 0:
                            self.save_state()

                    elif isinstance(message, bytes):
                        socketio.emit('agent_audio', message)
                except Exception as e:
                    logger.error(f"Error processing received message: {e}")
                    self.last_connection_error = e
                    self.save_state()
        except websockets.exceptions.ConnectionClosed as e:
            logger.warning(f"WebSocket connection closed: {e}")
            self.is_connected = False
            self.last_connection_error = e
            self.save_state()
        except Exception as e:
            logger.error(f"Receiver loop error: {e}")
            self.is_connected = False
            self.last_connection_error = e
            self.save_state()
        finally:
            logger.info("Receiver loop finished.")
            self.is_connected = False
            self.save_state()

    async def _handle_function_call(self, ws, function_call_msg):
        logger.info(f"Received function call request: {json.dumps(function_call_msg, indent=2)}")
        functions = function_call_msg.get('functions', [])
        
        if not functions:
            logger.error("No functions found in function call request")
            return
        
        for function_def in functions:
            function_name = function_def.get('name')
            function_id = function_def.get('id')  # Use id as request_id
            arguments_str = function_def.get('arguments', '{}')
            
            logger.info(f"Processing function: {function_name} with id: {function_id}")
            logger.info(f"Raw arguments: {arguments_str}")
            
            if function_name in FUNCTION_MAP:
                try:
                    arguments = json.loads(arguments_str)
                    logger.info(f"Parsed arguments: {arguments}")
                    
                    # Pass arguments as a single params dict, matching function signatures
                    logger.info(f"Calling function {function_name} with arguments: {arguments}")
                    result = FUNCTION_MAP[function_name](arguments)
                    logger.info(f"Function {function_name} returned: {result}")
                    
                    # Format response to match Deepgram's expected structure
                    response = {
                        "type": "FunctionCallResponse",
                        "id": function_id,
                        "name": function_name,
                        "content": json.dumps(result)
                    }
                except json.JSONDecodeError as e:
                    logger.error(f"Error parsing arguments for {function_name}: {e}")
                    response = {
                        "type": "FunctionCallResponse",
                        "id": function_id,
                        "name": function_name,
                        "content": json.dumps({"error": f"Invalid arguments format: {str(e)}", "success": False})
                    }
                except Exception as e:
                    logger.error(f"Error executing function {function_name}: {e}")
                    logger.error(f"Function signature expects: params dict, got: {type(arguments)}")
                    response = {
                        "type": "FunctionCallResponse",
                        "id": function_id,
                        "name": function_name,
                        "content": json.dumps({"error": str(e), "success": False})
                    }
            else:
                logger.error(f"Function {function_name} not found in FUNCTION_MAP: {list(FUNCTION_MAP.keys())}")
                response = {
                    "type": "FunctionCallResponse",
                    "id": function_id,
                    "name": function_name,
                    "content": json.dumps({"error": f"Function {function_name} not found.", "success": False})
                }
            
            logger.info(f"Sending function response: {json.dumps(response, indent=2)}")
            await ws.send(json.dumps(response))

    async def _connect_with_retry(self):
        """Connect to Deepgram with exponential backoff retry logic"""
        api_key = os.environ.get("DEEPGRAM_API_KEY")
        if not api_key:
            logger.error("DEEPGRAM_API_KEY environment variable not set.")
            logger.error("Please set your Deepgram API key in the environment or .env file")
            logger.error("Get your API key from: https://console.deepgram.com/")
            return None

        # Validate API key format (basic check)
        if len(api_key.strip()) < 10:
            logger.error("DEEPGRAM_API_KEY appears to be invalid (too short)")
            return None

        logger.info(f"Using Deepgram API key: {api_key[:8]}...")

        while self.is_running and not _shutdown_event.is_set() and self.connection_attempts < self.max_connection_attempts:
            try:
                logger.info(f"Connecting to Deepgram... (attempt {self.connection_attempts + 1}/{self.max_connection_attempts})")
                self.dg_client = await websockets.connect(
                    self.agent_templates.voice_agent_url,
                    extra_headers={"Authorization": f"Token {api_key}"},
                    open_timeout=20,
                    close_timeout=20,
                    ping_interval=10,
                    ping_timeout=30
                )
                logger.info("Successfully connected to Deepgram.")
                self.is_connected = True
                self.connection_attempts = 0  # Reset on successful connection
                self.reconnect_delay = 1.0  # Reset delay
                self.last_connection_error = None
                self.save_state()
                return self.dg_client

            except websockets.exceptions.InvalidStatusCode as e:
                self.connection_attempts += 1
                self.last_connection_error = e
                self.is_connected = False
                self.save_state()

                if e.status_code == 401:
                    logger.error("❌ Deepgram authentication failed (HTTP 401)")
                    logger.error("Please check your DEEPGRAM_API_KEY environment variable")
                    logger.error("1. Make sure you've set the correct API key")
                    logger.error("2. Check that your API key is active and has sufficient credits")
                    logger.error("3. Verify your .env file is being loaded properly")
                    return None  # Don't retry on auth errors
                else:
                    logger.warning(f"WebSocket connection failed with status {e.status_code}: {e}")

                if self.connection_attempts >= self.max_connection_attempts:
                    logger.error(f"Failed to connect after {self.max_connection_attempts} attempts")
                    return None

                # Exponential backoff with jitter
                delay = min(self.reconnect_delay * (2 ** (self.connection_attempts - 1)), self.max_reconnect_delay)
                jitter = delay * 0.1 * (2 * random.random() - 1)  # ±10% jitter
                actual_delay = delay + jitter

                logger.info(f"Retrying in {actual_delay:.1f} seconds...")
                await asyncio.sleep(actual_delay)

            except Exception as e:
                self.connection_attempts += 1
                self.last_connection_error = e
                self.is_connected = False
                self.save_state()

                if self.connection_attempts >= self.max_connection_attempts:
                    logger.error(f"Failed to connect after {self.max_connection_attempts} attempts: {e}")
                    return None

                # Exponential backoff with jitter
                delay = min(self.reconnect_delay * (2 ** (self.connection_attempts - 1)), self.max_reconnect_delay)
                jitter = delay * 0.1 * (2 * random.random() - 1)  # ±10% jitter
                actual_delay = delay + jitter

                logger.warning(f"Connection attempt {self.connection_attempts} failed: {e}")
                logger.info(f"Retrying in {actual_delay:.1f} seconds...")

                await asyncio.sleep(actual_delay)

        return None

    async def run(self):
        try:
            self.is_running = True
            self.save_state()

            while self.is_running and not _shutdown_event.is_set():
                # Attempt to connect
                client = await self._connect_with_retry()
                if not client:
                    logger.error("Could not establish connection to Deepgram")
                    break

                try:
                    # Send initial settings
                    await client.send(json.dumps(self.agent_templates.settings))

                    # Start sender and receiver tasks
                    sender_task = asyncio.create_task(self._audio_sender(client))
                    receiver_task = asyncio.create_task(self._receiver(client))

                    # Wait for tasks to complete or for the agent to be stopped
                    done, pending = await asyncio.wait(
                        {sender_task, receiver_task},
                        return_when=asyncio.FIRST_COMPLETED,
                    )

                    # Cancel any remaining tasks
                    for task in pending:
                        task.cancel()
                        try:
                            await task
                        except asyncio.CancelledError:
                            pass

                    # If we're still running but connection dropped, attempt to reconnect
                    if self.is_running and not _shutdown_event.is_set():
                        logger.info("Connection lost, attempting to reconnect...")
                        self.is_connected = False
                        self.save_state()
                        continue
                    else:
                        break

                except websockets.exceptions.ConnectionClosed as e:
                    logger.warning(f"Connection closed: {e}")
                    self.is_connected = False
                    self.last_connection_error = e
                    self.save_state()

                    if self.is_running and not _shutdown_event.is_set():
                        logger.info("Attempting to reconnect...")
                        continue
                    else:
                        break
                except asyncio.CancelledError:
                    logger.info("Agent run task was cancelled.")
                    break
                except Exception as e:
                    logger.error(f"Error during agent run: {e}")
                    self.is_connected = False
                    self.last_connection_error = e
                    self.save_state()

                    if self.is_running and not _shutdown_event.is_set():
                        logger.info("Attempting to reconnect...")
                        continue
                    else:
                        break
                finally:
                    # Clean up connection
                    if client and client.open:
                        try:
                            await client.close()
                        except Exception as e:
                            logger.warning(f"Error closing connection: {e}")

        except Exception as e:
            logger.error(f"Fatal error in agent run: {e}")
            self.last_connection_error = e
            self.save_state()
        finally:
            self.is_running = False
            self.is_connected = False
            self.save_state()
            logger.info("Agent run loop finished and connection closed.")

    def stop(self):
        """Signals the agent to stop its loops gracefully."""
        logger.info("Stop signal received for voice agent.")
        self.is_running = False


# --- SocketIO Event Handlers ---
voice_agent = None
# Guard to prevent concurrent starts
_start_lock = threading.Lock()
_agent_starting = False
_agent_thread = None # Keep track of the agent thread


def run_agent_in_background(agent: VoiceAgent) -> None:
    """Run the agent's async loop in a dedicated OS thread with its own event loop."""
    global _agent_starting, voice_agent
    loop = None
    try:
        logger.info(f"Starting new background thread for agent: {threading.current_thread().name}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(agent.run())
    except Exception as e:
        logger.error(f"Error in agent background thread: {e}")
    finally:
        if loop:
            loop.close()
        logger.info(f"Background thread finished for agent: {threading.current_thread().name}")
        with _start_lock:
            _agent_starting = False
            if voice_agent is agent: # Only clear if it's the same instance
                voice_agent = None


@socketio.on('start_voice_agent')
def handle_start_voice_agent(data):
    global voice_agent, _agent_starting, _agent_thread
    with _start_lock:
        if _agent_starting:
            logger.info("Voice agent start already in progress; ignoring duplicate start request.")
            return
        if voice_agent is not None:
            logger.info("Voice agent instance already exists; ignoring start request.")
            return
        _agent_starting = True

    logger.info(f"Starting voice agent with data: {data}")
    industry = data.get("industry", "tech_support")
    # Default if missing or empty string
    voiceModel = data.get("voiceModel") or "aura-2-thalia-en"
    voiceName = data.get("voiceName", "")
    session_id = data.get("session_id")  # Optional session ID for recovery

    voice_agent = VoiceAgent(industry, voiceModel, voiceName, session_id)
    # Start the agent in a new OS thread so asyncio loop doesn't conflict with eventlet
    _agent_thread = threading.Thread(target=run_agent_in_background, args=(voice_agent,), daemon=True)
    _agent_thread.start()

    # Send session info back to client
    socketio.emit("session_started", {
        "session_id": voice_agent.session_id,
        "industry": voice_agent.industry,
        "voiceModel": voice_agent.voiceModel,
        "voiceName": voice_agent.voiceName,
        "message_count": voice_agent.message_count,
        "start_time": voice_agent.start_time
    })


@socketio.on('user_audio')
def handle_user_audio(audio_data):
    if voice_agent:
        voice_agent.send_audio(audio_data)
        # Emit status update if connection state changed
        if hasattr(voice_agent, 'is_connected') and voice_agent.is_connected:
            socketio.emit("connection_status", {
                "connected": voice_agent.is_connected,
                "session_id": voice_agent.session_id,
                "message_count": voice_agent.message_count
            })

@socketio.on('get_connection_status')
def handle_get_connection_status():
    if voice_agent:
        socketio.emit("connection_status", {
            "connected": getattr(voice_agent, 'is_connected', False),
            "session_id": getattr(voice_agent, 'session_id', None),
            "message_count": getattr(voice_agent, 'message_count', 0),
            "last_error": str(getattr(voice_agent, 'last_connection_error', None)) if getattr(voice_agent, 'last_connection_error', None) else None
        })
    else:
        socketio.emit("connection_status", {
            "connected": False,
            "session_id": None,
            "message_count": 0,
            "last_error": "No voice agent running"
        })

@socketio.on('stop_voice_agent')
def handle_stop_voice_agent():
    global voice_agent, _agent_thread
    logger.info("Received stop_voice_agent event.")
    if voice_agent:
        voice_agent.stop() # Gracefully stop the agent's loops
        voice_agent = None
    if _agent_thread and _agent_thread.is_alive():
        logger.info("Waiting for agent thread to finish.")
        _agent_thread.join(timeout=5) # Wait for thread to finish
        if _agent_thread.is_alive():
            logger.warning("Agent thread did not finish in time.")
    _agent_thread = None


@socketio.on('disconnect')
def handle_disconnect():
    global voice_agent, _agent_thread
    logger.info("Client disconnected.")
    if voice_agent:
        voice_agent.stop()
    if _agent_thread and _agent_thread.is_alive():
        _agent_thread.join(timeout=2)
    voice_agent = None
    _agent_thread = None


# --- Main Execution ---
if __name__ == "__main__":
    host = '0.0.0.0'
    port = 5000
    logger.info(f"Starting Flask server on {host}:{port}")
    # Use eventlet when available for WebSocket support in dev
    try:
        socketio.run(app, host=host, port=port)
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt received, shutting down.")
        _shutdown_event.set()
    finally:
        logger.info("Server has been shut down.")
