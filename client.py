from flask import Flask, render_template, jsonify, send_from_directory
from flask_socketio import SocketIO
import asyncio
import websockets
import os
import json
import queue
import requests
from dotenv import load_dotenv
from common.agent_functions import FUNCTION_MAP
from common.agent_templates import AgentTemplates
import logging
from common.log_formatter import CustomFormatter

# Load environment variables from .env file
load_dotenv()

# Configure Flask and SocketIO
app = Flask(__name__, static_folder="./static", static_url_path="/")
# The async_mode must be 'aiohttp' for the latest library versions.
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='aiohttp')

# --- Logging Setup ---
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if logger.hasHandlers():
    logger.handlers.clear()
console_handler = logging.StreamHandler()
console_handler.setFormatter(CustomFormatter())
logger.addHandler(console_handler)
logger.propagate = False


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
            headers={"Authorization": f"Token {dg_api_key}"}
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


# --- Voice Agent Class ---
class VoiceAgent:
    def __init__(self, industry="tech_support", voiceModel="aura-2-thalia-en", voiceName=""):
        self.industry = industry
        self.voiceModel = voiceModel
        self.voiceName = voiceName
        self.dg_client = None
        self.audio_queue = queue.Queue()
        self.is_running = False
        self.agent_templates = AgentTemplates(industry, voiceModel, voiceName)

    def send_audio(self, audio_chunk):
        self.audio_queue.put(audio_chunk)

    async def _audio_sender(self, ws):
        try:
            while self.is_running:
                try:
                    audio_chunk = self.audio_queue.get_nowait()
                    if audio_chunk:
                        await ws.send(audio_chunk)
                except queue.Empty:
                    await asyncio.sleep(0.01)
        except asyncio.CancelledError:
            logger.info("Audio sender task cancelled.")
        except Exception as e:
            logger.error(f"Error in audio sender: {e}")

    async def _receiver(self, ws):
        try:
            async for message in ws:
                try:
                    if isinstance(message, str):
                        msg_json = json.loads(message)
                        socketio.emit("agent_response", msg_json)
                        logger.info(f"Server -> Browser: {json.dumps(msg_json)}")
                        if msg_json.get("type") == 'FunctionCall':
                            await self._handle_function_call(ws, msg_json)
                    elif isinstance(message, bytes):
                        socketio.emit('agent_audio', message)
                except Exception as e:
                    logger.error(f"Error processing received message: {e}")
        except Exception as e:
            logger.error(f"Receiver loop error: {e}")

    async def _handle_function_call(self, ws, function_call_msg):
        function_name = function_call_msg.get('name')
        request_id = function_call_msg.get("request_id")
        
        if function_name in FUNCTION_MAP:
            try:
                arguments = json.loads(function_call_msg.get('arguments', '{}'))
                result = FUNCTION_MAP[function_name](**arguments)
                response = {"type": "FunctionResult", "request_id": request_id, "result": json.dumps(result)}
            except Exception as e:
                logger.error(f"Error executing function {function_name}: {e}")
                response = {"type": "FunctionResult", "request_id": request_id, "result": json.dumps({"error": str(e), "success": False})}
        else:
            logger.error(f"Function {function_name} not found.")
            response = {"type": "FunctionResult", "request_id": request_id, "result": json.dumps({"error": f"Function {function_name} not found.", "success": False})}
        
        await ws.send(json.dumps(response))

    async def run(self):
        api_key = os.environ.get("DEEPGRAM_API_KEY")
        if not api_key:
            logger.error("DEEPGRAM_API_KEY environment variable not set.")
            return

        try:
            logger.info("Connecting to Deepgram...")
            self.dg_client = await websockets.connect(
                self.agent_templates.voice_agent_url,
                extra_headers={"Authorization": f"Token {api_key}"}
            )
            logger.info("Successfully connected to Deepgram.")
            self.is_running = True

            settings = {"type": "Settings", "prompt": self.agent_templates.prompt, "model": self.voiceModel}
            await self.dg_client.send(json.dumps(settings))

            sender_task = asyncio.create_task(self._audio_sender(self.dg_client))
            receiver_task = asyncio.create_task(self._receiver(self.dg_client))
            await asyncio.gather(sender_task, receiver_task)
        except Exception as e:
            logger.error(f"Error during agent run: {e}")
        finally:
            self.is_running = False
            if self.dg_client:
                await self.dg_client.close()
            logger.info("Agent run loop finished.")

# --- SocketIO Event Handlers ---
voice_agent = None

@socketio.on('start_voice_agent')
async def handle_start_voice_agent(data):
    global voice_agent
    if voice_agent and voice_agent.is_running:
        logger.info("Voice agent is already running.")
        return

    logger.info(f"Starting voice agent with data: {data}")
    industry = data.get("industry", "tech_support")
    voiceModel = data.get("voiceModel", "aura-2-thalia-en")
    voiceName = data.get("voiceName", "")
    
    voice_agent = VoiceAgent(industry, voiceModel, voiceName)
    socketio.start_background_task(voice_agent.run)

@socketio.on('user_audio')
def handle_user_audio(audio_data):
    if voice_agent:
        voice_agent.send_audio(audio_data)

@socketio.on('stop_voice_agent')
def handle_stop_voice_agent():
    global voice_agent
    if voice_agent:
        voice_agent.is_running = False
    voice_agent = None

@socketio.on('disconnect')
def handle_disconnect():
    global voice_agent
    logger.info("Client disconnected.")
    if voice_agent:
        voice_agent.is_running = False
    voice_agent = None

# --- Main Execution ---
if __name__ == "__main__":
    host = '0.0.0.0'
    port = 5000
    logger.info(f"Starting Flask server on {host}:{port}")
    socketio.run(app, host=host, port=port)
