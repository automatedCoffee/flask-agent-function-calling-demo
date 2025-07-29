from flask import Flask, render_template, jsonify, send_from_directory
from flask_socketio import SocketIO
import asyncio
import websockets
import os
import json
import threading
import queue
import sys
import time
import requests
from datetime import datetime
from dotenv import load_dotenv
from common.agent_functions import FUNCTION_MAP
from common.agent_templates import AgentTemplates, AGENT_AUDIO_SAMPLE_RATE
import logging
from common.business_logic import MOCK_DATA
from common.log_formatter import CustomFormatter

# Load environment variables from .env file
load_dotenv()

# Configure Flask and SocketIO
app = Flask(__name__, static_folder="./static", static_url_path="/")
socketio = SocketIO(app, cors_allowed_origins="*")  # Allow CORS for WebSocket

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Create console handler with the custom formatter
console_handler = logging.StreamHandler()
console_handler.setFormatter(CustomFormatter(socketio=socketio))
logger.addHandler(console_handler)

# Remove any existing handlers from the root logger to avoid duplicate messages
logging.getLogger().handlers = []

# Check if running in Docker
is_docker = os.environ.get('DOCK_CONTAINER', '').lower() == 'true'
host = '0.0.0.0'
port = 5000

# Serve the audio processor worklet file with the correct MIME type
@app.route('/audio-processor.js')
def serve_audio_processor():
    return send_from_directory('static', 'audio-processor.js', mimetype='application/javascript')

class VoiceAgent:
    def __init__(self, industry="tech_support", voiceModel="aura-2-thalia-en", voiceName=""):
        self.mic_audio_queue = asyncio.Queue()
        self.ws = None
        self.is_running = False
        self.loop = None
        self.agent_templates = AgentTemplates(industry, voiceName, voiceModel)
        self.last_pong = time.time()
        self.heartbeat_task = None

    def set_loop(self, loop):
        self.loop = loop

    async def _heartbeat(self):
        while self.is_running and self.ws:
            try:
                await self.ws.ping()
                await asyncio.sleep(15)
            except Exception as e:
                logger.error(f"Error in heartbeat: {e}")
                break

    async def setup(self):
        dg_api_key = os.environ.get("DEEPGRAM_API_KEY")
        if dg_api_key is None:
            logger.error("DEEPGRAM_API_KEY env var not present")
            return False

        settings = self.agent_templates.settings
        logger.info("Connecting to Deepgram Voice Agent API...")
        try:
            self.ws = await websockets.connect(
                self.agent_templates.voice_agent_url,
                extra_headers={"Authorization": f"Token {dg_api_key}"},
                ping_interval=20, ping_timeout=20, close_timeout=20
            )
            logger.info("Successfully connected to Deepgram")
            self.heartbeat_task = asyncio.create_task(self._heartbeat())
            
            logger.info("Sending initial settings...")
            await self.ws.send(json.dumps(settings))
            logger.info("Settings sent successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram: {e}")
            if self.ws:
                await self.ws.close()
            self.ws = None
            return False

    async def sender(self):
        try:
            while self.is_running:
                data = await self.mic_audio_queue.get()
                if self.ws and data:
                    await self.ws.send(data)
        except Exception as e:
            logger.error(f"Error in sender: {e}")

    async def receiver(self):
        try:
            logger.info("Starting receiver...")
            async for message in self.ws:
                try:
                    if isinstance(message, str):
                        message_json = json.loads(message)
                        message_type = message_json.get("type")

                        if message_type in ["Welcome", "SettingsApplied", "UserStartedSpeaking", "ConversationText", "FunctionCalling", "FunctionCallRequest", "Error", "AgentAudioDone"]:
                            logger.info(f"Server: {message}")
                            socketio.emit("agent_response", message_json)
                        
                        if message_type == "FunctionCallRequest":
                            functions = message_json.get("functions", [])
                            if functions:
                                function_call = functions[0]
                                function_name = function_call.get("name")
                                function_call_id = function_call.get("id")
                                try:
                                    arguments = json.loads(function_call.get("arguments", "{}"))
                                    func = FUNCTION_MAP.get(function_name)
                                    if func:
                                        result = func(arguments)
                                        response = {
                                            "type": "FunctionCallResponse", "id": function_call_id, "name": function_name,
                                            "content": json.dumps(result)
                                        }
                                        await self.ws.send(json.dumps(response))
                                    else:
                                        raise Exception(f"Function {function_name} not found")
                                except Exception as e:
                                    logger.error(f"Error executing function: {e}")
                                    error_response = {
                                        "type": "FunctionCallResponse", "id": function_call_id, "name": function_name,
                                        "content": json.dumps({"error": str(e), "success": False})
                                    }
                                    await self.ws.send(json.dumps(error_response))

                    elif isinstance(message, bytes):
                        # Forward audio bytes directly to the browser client
                        socketio.emit("agent_audio", message)
                except Exception as e:
                    logger.error(f"Error processing message: {e}")
        except Exception as e:
            logger.error(f"Error in receiver: {e}")
        finally:
            logger.info("Receiver loop ended")

    async def run(self):
        logger.info("Starting voice agent...")
        if not await self.setup():
            logger.error("Failed to set up voice agent")
            return

        self.is_running = True
        try:
            await asyncio.gather(self.sender(), self.receiver())
        except Exception as e:
            logger.error(f"Error in run: {e}")
        finally:
            self.is_running = False
            logger.info("Cleaning up resources...")
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
            if self.ws:
                await self.ws.close()
            logger.info("Voice agent stopped")

# Flask routes
@app.route("/")
def index():
    return render_template("index.html")

# No longer need audio device routes, as audio is handled by the browser
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
        )
        data = response.json()
        formatted_models = []
        if "tts" in data:
            for model in data["tts"]:
                if model.get("architecture") == "aura-2":
                    formatted_models.append({
                        "name": model.get("canonical_name", model.get("name")),
                        "display_name": model.get("name"),
                        "language": model.get("languages", ["en"])[0],
                    })
        return jsonify({"models": formatted_models})
    except Exception as e:
        logger.error(f"Error fetching TTS models: {e}")
        return jsonify({"error": str(e)}), 500

voice_agent = None

def run_async_voice_agent():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    if voice_agent:
        voice_agent.set_loop(loop)
        voice_agent.is_running = True
        try:
            loop.run_until_complete(voice_agent.run())
        except Exception as e:
            logger.error(f"Error in voice agent thread: {e}")
        finally:
            loop.close()

@socketio.on("start_voice_agent")
def handle_start_voice_agent(data=None):
    global voice_agent
    logger.info(f"Starting voice agent with data: {data}")
    if voice_agent is None:
        industry = data.get("industry", "tech_support") if data else "tech_support"
        voiceModel = data.get("voiceModel", "aura-2-thalia-en") if data else "aura-2-thalia-en"
        voiceName = data.get("voiceName", "") if data else ""
        voice_agent = VoiceAgent(industry=industry, voiceModel=voiceModel, voiceName=voiceName)
        socketio.start_background_task(target=run_async_voice_agent)

@socketio.on("stop_voice_agent")
def handle_stop_voice_agent():
    global voice_agent
    if voice_agent:
        voice_agent.is_running = False
        if voice_agent.loop and not voice_agent.loop.is_closed():
            for task in asyncio.all_tasks(voice_agent.loop):
                task.cancel()
        voice_agent = None

@socketio.on('user_audio')
def handle_user_audio(audio_chunk):
    """Receives audio chunks from the browser and queues them for sending to Deepgram."""
    if voice_agent and voice_agent.mic_audio_queue:
        try:
            # We need to run this in the agent's event loop
            future = asyncio.run_coroutine_threadsafe(
                voice_agent.mic_audio_queue.put(audio_chunk), voice_agent.loop
            )
            future.result(timeout=1) # Don't block forever
        except Exception as e:
            logger.error(f"Error queueing user audio: {e}")

if __name__ == "__main__":
    run_host = '0.0.0.0'
    print("\n" + "=" * 60)
    print("🚀 Voice Agent Demo Starting!")
    print("=" * 60)
    print(f"\n1. Open this link in your browser to start the demo:")
    print(f"   http://{run_host}:{port}")
    print("\n2. Click 'Start Voice Agent' when the page loads")
    print("\n3. Speak with the agent using your microphone")
    print("\nPress Ctrl+C to stop the server\n")
    print("=" * 60 + "\n")
    socketio.run(app, host=run_host, port=port, debug=False, use_reloader=False)
