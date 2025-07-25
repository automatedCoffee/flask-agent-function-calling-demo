from flask import Flask, render_template, jsonify
from flask_socketio import SocketIO
import pyaudio
import asyncio
import websockets
import os
import json
import threading
import janus
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
is_docker = os.environ.get('DOCKER_CONTAINER', '').lower() == 'true'
host = '0.0.0.0' if is_docker else '127.0.0.1'
port = 5000


class VoiceAgent:
    def __init__(
        self,
        industry="tech_support",
        voiceModel="aura-2-thalia-en",
        voiceName="",
    ):
        self.mic_audio_queue = asyncio.Queue()
        self.speaker = None
        self.ws = None
        self.is_running = False
        self.loop = None
        self.audio = None
        self.stream = None
        self.input_device_id = None
        self.output_device_id = None
        self.agent_templates = AgentTemplates(industry, voiceName, voiceModel)
        self.last_pong = time.time()
        self.heartbeat_task = None
        # Audio feedback prevention
        self.is_agent_outputting = False

    def set_loop(self, loop):
        self.loop = loop

    def set_audio_devices(self, input_device_id=None, output_device_id=None):
        """Set specific audio devices to avoid feedback"""
        self.input_device_id = input_device_id
        self.output_device_id = output_device_id
        if input_device_id is not None and output_device_id is not None:
            logger.info(f"Audio devices set - Input: {input_device_id}, Output: {output_device_id}")
        else:
            logger.info("Using default audio devices")



    async def _heartbeat(self):
        """Send periodic pings to keep the connection alive"""
        while self.is_running and self.ws:
            try:
                await self.ws.ping()
                await asyncio.sleep(15)  # Send ping every 15 seconds
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
        logger.info(f"Using voice model: {settings.get('voiceModel', 'default')}")

        try:
            self.ws = await websockets.connect(
                self.agent_templates.voice_agent_url,
                extra_headers={"Authorization": f"Token {dg_api_key}"},
                ping_interval=20,
                ping_timeout=20,
                close_timeout=20
            )
            logger.info("Successfully connected to Deepgram")
            
            # Start heartbeat task
            self.heartbeat_task = asyncio.create_task(self._heartbeat())
            
            try:
                logger.info("Sending initial settings...")
                await self.ws.send(json.dumps(settings))
                logger.info("Settings sent successfully")
                return True
            except Exception as e:
                logger.error(f"Error sending initial settings: {e}")
                await self.ws.close()
                self.ws = None
                return False
                
        except Exception as e:
            logger.error(f"Failed to connect to Deepgram: {e}")
            if self.ws:
                await self.ws.close()
                self.ws = None
            return False

    def audio_callback(self, input_data, frame_count, time_info, status_flag):
        if self.is_running and self.loop and not self.loop.is_closed():
            # If agent is outputting, send silence instead of actual audio
            if self.is_agent_outputting:
                # Send silence to prevent feedback
                silence = b'\x00' * len(input_data)
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.mic_audio_queue.put(silence), self.loop
                    )
                    future.result(timeout=1)
                except Exception as e:
                    logger.error(f"Error sending silence: {e}")
            else:
                # Send actual audio when agent is not outputting
                try:
                    future = asyncio.run_coroutine_threadsafe(
                        self.mic_audio_queue.put(input_data), self.loop
                    )
                    future.result(timeout=1)  # Add timeout to prevent blocking
                except Exception as e:
                    logger.error(f"Error in audio callback: {e}")
        return (input_data, pyaudio.paContinue)

    async def start_microphone(self):
        try:
            self.audio = pyaudio.PyAudio()

            # List available input devices
            info = self.audio.get_host_api_info_by_index(0)
            numdevices = info.get("deviceCount")
            logger.info(f"Number of devices: {numdevices}")
            logger.info(
                f"Selected input device index from frontend: {self.input_device_id}"
            )

            # Log all available input devices
            available_devices = []
            for i in range(0, numdevices):
                device_info = self.audio.get_device_info_by_host_api_device_index(0, i)
                if device_info.get("maxInputChannels") > 0:
                    available_devices.append(i)
                    logger.info(f"Input Device {i}: {device_info.get('name')}")

            # If a specific device index was provided from the frontend, use it
            input_device_index = None
            if self.input_device_id and str(self.input_device_id).isdigit():
                requested_index = int(self.input_device_id)
                # Verify the requested index is valid
                if requested_index in available_devices:
                    input_device_index = requested_index
                    logger.info(f"Using selected device index: {input_device_index}")
                else:
                    logger.warning(
                        f"Requested device index {requested_index} not available"
                    )

            # If no valid device selected, use default device
            if input_device_index is None:
                try:
                    default_device = self.audio.get_default_input_device_info()
                    input_device_index = default_device['index']
                    logger.info(f"Using default input device index: {input_device_index}")
                except IOError:
                    # If no default device, use first available
                    if available_devices:
                        input_device_index = available_devices[0]
                        logger.info(f"Using first available device index: {input_device_index}")
                    else:
                        raise Exception("No input devices found")

            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.agent_templates.user_audio_sample_rate,
                input=True,
                input_device_index=input_device_index,
                frames_per_buffer=self.agent_templates.user_audio_samples_per_chunk,
                stream_callback=self.audio_callback,
            )

            self.stream.start_stream()
            logger.info("Microphone started successfully")
            return self.stream, self.audio
        except Exception as e:
            logger.error(f"Error starting microphone: {e}")
            if self.audio:
                self.audio.terminate()
            raise

    def cleanup(self):
        """Clean up audio resources"""
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error closing audio stream: {e}")

        if self.audio:
            try:
                self.audio.terminate()
            except Exception as e:
                logger.error(f"Error terminating audio: {e}")

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
            self.speaker = Speaker(output_device_id=self.output_device_id)
            last_user_message = None
            last_function_response_time = None
            in_function_chain = False

            with self.speaker:
                logger.info("Entering WebSocket message loop...")
                async for message in self.ws:
                    try:
                        if isinstance(message, str):
                            logger.info(f"Server: {message}")
                            message_json = json.loads(message)
                            message_type = message_json.get("type")
                            current_time = time.time()

                            if message_type == "Welcome":
                                logger.info(f"Connected with session ID: {message_json.get('request_id')}")
                            elif message_type == "SettingsApplied":
                                logger.info("Voice agent settings applied successfully")
                            elif message_type == "UserStartedSpeaking":
                                logger.info("User started speaking, stopping audio playback")
                                # Don't reset is_agent_outputting here - let AgentAudioDone handle it
                                self.speaker.stop()
                            elif message_type == "ConversationText":
                                logger.info(f"Received conversation text: {message_json.get('content')}")
                                # Emit the conversation text to the client
                                socketio.emit("conversation_update", message_json)

                                if message_json.get("role") == "user":
                                    last_user_message = current_time
                                    in_function_chain = False
                                elif message_json.get("role") == "assistant":
                                    in_function_chain = False

                            elif message_type == "FunctionCalling":
                                logger.info("Function calling event received")
                                if in_function_chain and last_function_response_time:
                                    latency = current_time - last_function_response_time
                                    logger.info(
                                        f"LLM Decision Latency (chain): {latency:.3f}s"
                                    )
                                elif last_user_message:
                                    latency = current_time - last_user_message
                                    logger.info(
                                        f"LLM Decision Latency (initial): {latency:.3f}s"
                                    )
                                    in_function_chain = True

                            elif message_type == "FunctionCallRequest":
                                logger.info("Processing function call request...")
                                # Get the function from the functions array if it exists
                                functions = message_json.get("functions", [])
                                if functions and len(functions) > 0:
                                    function_call = functions[0]
                                    function_name = function_call.get("name")
                                    function_call_id = function_call.get("id")
                                    try:
                                        arguments = function_call.get("arguments", "{}")
                                        parameters = json.loads(arguments)
                                    except json.JSONDecodeError as e:
                                        logger.error(f"Error parsing function arguments: {e}")
                                        parameters = {}

                                    logger.info(f"Function call received: {function_name}")
                                    logger.info(f"Parameters: {parameters}")

                                    start_time = time.time()
                                    try:
                                        func = FUNCTION_MAP.get(function_name)
                                        if not func:
                                            raise Exception(f"Function {function_name} not found")

                                        result = func(parameters)
                                        end_time = time.time()
                                        latency = end_time - start_time
                                        logger.info(
                                            f"Function Execution Latency: {latency:.3f}s"
                                        )
                                        logger.info(f"Function result: {result}")

                                        # Send the function result back to the websocket
                                        response = {
                                            "type": "FunctionCallResponse",
                                            "id": function_call_id,
                                            "name": function_name,
                                            "content": json.dumps(result)
                                        }
                                        logger.info(f"Sending function response: {response}")
                                        await self.ws.send(json.dumps(response))
                                        last_function_response_time = time.time()

                                    except Exception as e:
                                        logger.error(f"Error executing function: {e}")
                                        # Send error response
                                        error_response = {
                                            "type": "FunctionCallResponse",
                                            "id": function_call_id,
                                            "name": function_name,
                                            "content": json.dumps({"error": str(e), "success": False})
                                        }
                                        logger.info(f"Sending error response: {error_response}")
                                        await self.ws.send(json.dumps(error_response))

                            elif message_type == "Error":
                                logger.error(f"Received error from server: {message_json.get('description')}")
                            elif message_type == "AgentAudioDone":
                                logger.info("Agent finished outputting audio - microphone will be active shortly")
                                # Add a small delay before reactivating microphone to prevent feedback
                                await asyncio.sleep(0.5)
                                self.is_agent_outputting = False
                                logger.info("Microphone now active")
                            else:
                                logger.info(f"Received message of type: {message_type}")

                        elif isinstance(message, bytes):
                            logger.info("Received audio data, playing...")
                            self.is_agent_outputting = True
                            await self.speaker.play(message)
                        else:
                            logger.warning(f"Received unknown message type: {type(message)}")
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
            logger.info("Initializing audio devices...")
            stream, audio = await self.start_microphone()
            logger.info("Starting main processing loops...")
            await asyncio.gather(
                self.sender(),
                self.receiver(),
            )
        except Exception as e:
            logger.error(f"Error in run: {e}")
        finally:
            self.is_running = False
            logger.info("Cleaning up resources...")
            if self.heartbeat_task:
                self.heartbeat_task.cancel()
            self.cleanup()
            if self.ws:
                await self.ws.close()
            logger.info("Voice agent stopped")


def _play(audio_out, stream, stop):
    """Play audio data through the stream."""
    try:
        if isinstance(audio_out, bytes):
            # Direct bytes data
            if not stop():
                stream.write(audio_out)
        else:
            # Queue-based audio data
            while not stop():
                try:
                    data = audio_out.sync_q.get(True, 0.05)
                    stream.write(data)
                except queue.Empty:
                    pass
    except Exception as e:
        logger.error(f"Error in audio playback: {e}")


class Speaker:
    def __init__(self, agent_audio_sample_rate=None, output_device_id=None):
        self.agent_audio_sample_rate = agent_audio_sample_rate or AGENT_AUDIO_SAMPLE_RATE
        self.output_device_id = output_device_id
        self.audio = None
        self.stream = None
        self.stop_flag = False
        self.audio_queue = queue.Queue()

    def __enter__(self):
        try:
            self.audio = pyaudio.PyAudio()
            
            # Use specified output device or find default/available one
            output_device_index = None
            if self.output_device_id is not None:
                # Verify the specified device exists and is valid
                try:
                    device_info = self.audio.get_device_info_by_index(self.output_device_id)
                    if device_info.get("maxOutputChannels") > 0:
                        output_device_index = self.output_device_id
                        logger.info(f"Using specified output device index: {output_device_index} - {device_info.get('name')}")
                    else:
                        logger.warning(f"Specified output device {self.output_device_id} has no output channels")
                except Exception as e:
                    logger.warning(f"Specified output device {self.output_device_id} not available: {e}")
            
            if output_device_index is None:
                # Try to get default output device
                try:
                    default_device = self.audio.get_default_output_device_info()
                    output_device_index = default_device['index']
                    logger.info(f"Using default output device index: {output_device_index}")
                except IOError:
                    # If no default device, find first available output device
                    info = self.audio.get_host_api_info_by_index(0)
                    numdevices = info.get("deviceCount")
                    
                    for i in range(0, numdevices):
                        device_info = self.audio.get_device_info_by_host_api_device_index(0, i)
                        if device_info.get("maxOutputChannels") > 0:
                            output_device_index = i
                            logger.info(f"Using first available output device index: {output_device_index}")
                            break
                    
                    if output_device_index is None:
                        raise Exception("No output devices found")

            self.stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=self.agent_audio_sample_rate,
                output=True,
                output_device_index=output_device_index,
                frames_per_buffer=1024
            )
            
            # Start the audio playback thread
            self.playback_thread = threading.Thread(target=self._audio_playback_thread)
            self.playback_thread.daemon = True
            self.playback_thread.start()
            
            return self
        except Exception as e:
            logger.error(f"Error initializing audio: {e}")
            if self.audio:
                self.audio.terminate()
            raise

    def __exit__(self, exc_type, exc_value, traceback):
        """Clean up audio resources"""
        self.stop_flag = True
        if hasattr(self, 'playback_thread'):
            self.playback_thread.join(timeout=1.0)
            
        if self.stream:
            try:
                self.stream.stop_stream()
                self.stream.close()
            except Exception as e:
                logger.error(f"Error closing audio stream: {e}")

        if self.audio:
            try:
                self.audio.terminate()
            except Exception as e:
                logger.error(f"Error terminating audio: {e}")

    def _audio_playback_thread(self):
        """Background thread for audio playback"""
        while not self.stop_flag:
            try:
                # Get audio data from queue with timeout
                try:
                    audio_data = self.audio_queue.get(timeout=0.1)
                    if self.stream and not self.stop_flag:
                        self.stream.write(audio_data)
                except queue.Empty:
                    continue
            except Exception as e:
                logger.error(f"Error in audio playback thread: {e}")
                time.sleep(0.1)

    async def play(self, data):
        """Queue audio data for playback"""
        if not self.stop_flag:
            self.audio_queue.put(data)

    def stop(self):
        """Stop playing audio"""
        logger.info("Stopping audio playback and clearing queue")
        self.stop_flag = True
        # Clear the audio queue to stop playback immediately
        with self.audio_queue.mutex:
            self.audio_queue.queue.clear()
        # Reset stop flag after clearing queue
        self.stop_flag = False


async def inject_agent_message(ws, inject_message):
    """Simple helper to inject an agent message."""
    logger.info(f"Sending InjectAgentMessage: {json.dumps(inject_message)}")
    await ws.send(json.dumps(inject_message))


async def close_websocket_with_timeout(ws, timeout=5):
    """Close websocket with timeout to avoid hanging if no close frame is received."""
    try:
        await asyncio.wait_for(ws.close(), timeout=timeout)
    except Exception as e:
        logger.error(f"Error during websocket closure: {e}")


async def wait_for_farewell_completion(ws, speaker, inject_message):
    """Wait for the farewell message to be spoken completely by the agent."""
    # Send the farewell message
    await inject_agent_message(ws, inject_message)

    # First wait for either AgentStartedSpeaking or matching ConversationText
    speaking_started = False
    while not speaking_started:
        message = await ws.recv()
        if isinstance(message, bytes):
            await speaker.play(message)
            continue

        try:
            message_json = json.loads(message)
            logger.info(f"Server: {message}")
            if message_json.get("type") == "AgentStartedSpeaking" or (
                message_json.get("type") == "ConversationText"
                and message_json.get("role") == "assistant"
                and message_json.get("content") == inject_message["message"]
            ):
                speaking_started = True
        except json.JSONDecodeError:
            continue

    # Then wait for AgentAudioDone
    audio_done = False
    while not audio_done:
        message = await ws.recv()
        if isinstance(message, bytes):
            await speaker.play(message)
            continue

        try:
            message_json = json.loads(message)
            logger.info(f"Server: {message}")
            if message_json.get("type") == "AgentAudioDone":
                audio_done = True
        except json.JSONDecodeError:
            continue

    # Give audio time to play completely
    await asyncio.sleep(3.5)


# Get available audio devices
def get_audio_devices():
    try:
        audio = pyaudio.PyAudio()
        info = audio.get_host_api_info_by_index(0)
        numdevices = info.get("deviceCount")

        input_devices = []
        output_devices = []
        
        for i in range(0, numdevices):
            device_info = audio.get_device_info_by_host_api_device_index(0, i)
            device_entry = {"index": i, "name": device_info.get("name")}
            
            if device_info.get("maxInputChannels") > 0:
                input_devices.append(device_entry.copy())
            if device_info.get("maxOutputChannels") > 0:
                output_devices.append(device_entry.copy())

        audio.terminate()
        return {"input": input_devices, "output": output_devices}
    except Exception as e:
        logger.error(f"Error getting audio devices: {e}")
        return {"input": [], "output": []}


# Flask routes
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/audio-devices")
def audio_devices():
    # Get available audio devices
    devices = get_audio_devices()
    return devices


@app.route("/industries")
def get_industries():
    # Get available industries from AgentTemplates
    return AgentTemplates.get_available_industries()


@app.route("/tts-models")
def get_tts_models():
    # Get TTS models from Deepgram API
    try:
        dg_api_key = os.environ.get("DEEPGRAM_API_KEY")
        if not dg_api_key:
            return jsonify({"error": "DEEPGRAM_API_KEY not set"}), 500

        response = requests.get(
            "https://api.deepgram.com/v1/models",
            headers={"Authorization": f"Token {dg_api_key}"},
        )

        if response.status_code != 200:
            return (
                jsonify(
                    {"error": f"API request failed with status {response.status_code}"}
                ),
                500,
            )

        data = response.json()

        # Process TTS models
        formatted_models = []

        # Check if 'tts' key exists in the response
        if "tts" in data:
            # Filter for only aura-2 models
            for model in data["tts"]:
                if model.get("architecture") == "aura-2":
                    # Extract language from languages array if available
                    language = "en"
                    if model.get("languages") and len(model.get("languages")) > 0:
                        language = model["languages"][0]

                    # Extract metadata for additional information
                    metadata = model.get("metadata", {})
                    accent = metadata.get("accent", "")
                    tags = ", ".join(metadata.get("tags", []))

                    formatted_models.append(
                        {
                            "name": model.get("canonical_name", model.get("name")),
                            "display_name": model.get("name"),
                            "language": language,
                            "accent": accent,
                            "tags": tags,
                            "description": f"{accent} accent. {tags}",
                        }
                    )

        return jsonify({"models": formatted_models})
    except Exception as e:
        logger.error(f"Error fetching TTS models: {e}")
        return jsonify({"error": str(e)}), 500


voice_agent = None


def run_async_voice_agent():
    try:
        # Create a new event loop for this thread
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        # Set the loop in the voice agent
        if voice_agent:
            voice_agent.set_loop(loop)
            voice_agent.is_running = True

            try:
                # Run the voice agent
                loop.run_until_complete(voice_agent.run())
            except asyncio.CancelledError:
                logger.info("Voice agent task was cancelled")
            except Exception as e:
                logger.error(f"Error in voice agent thread: {e}")
            finally:
                # Clean up the loop
                try:
                    # Cancel all running tasks
                    pending = asyncio.all_tasks(loop)
                    for task in pending:
                        task.cancel()

                    # Allow cancelled tasks to complete
                    if pending:
                        loop.run_until_complete(
                            asyncio.gather(*pending, return_exceptions=True)
                        )

                    loop.run_until_complete(loop.shutdown_asyncgens())
                finally:
                    loop.close()
        else:
            logger.error("Voice agent is None")
    except Exception as e:
        logger.error(f"Error in voice agent thread setup: {e}")


@socketio.on("start_voice_agent")
def handle_start_voice_agent(data=None):
    global voice_agent
    logger.info(f"Starting voice agent with data: {data}")
    if voice_agent is None:
        # Get industry from data or default to tech_support
        industry = data.get("industry", "tech_support") if data else "tech_support"
        voiceModel = (
            data.get("voiceModel", "aura-2-thalia-en") if data else "aura-2-thalia-en"
        )
        # Get voice name from data or default to empty string, which uses the Model's voice name in the backend
        voiceName = data.get("voiceName", "") if data else ""
        voice_agent = VoiceAgent(
            industry=industry,
            voiceModel=voiceModel,
            voiceName=voiceName,
        )
        if data:
            voice_agent.input_device_id = data.get("inputDeviceId")
            voice_agent.output_device_id = data.get("outputDeviceId")
        # Start the voice agent in a background thread
        socketio.start_background_task(target=run_async_voice_agent)


@socketio.on("stop_voice_agent")
def handle_stop_voice_agent():
    global voice_agent
    if voice_agent:
        voice_agent.is_running = False
        if voice_agent.loop and not voice_agent.loop.is_closed():
            try:
                # Cancel all running tasks
                for task in asyncio.all_tasks(voice_agent.loop):
                    task.cancel()
            except Exception as e:
                logger.error(f"Error stopping voice agent: {e}")
        voice_agent = None




if __name__ == "__main__":
    # Determine if running in production (e.g., via start.sh which doesn't set a specific env var)
    # or local development. We can use the presence of the reloader as a proxy.
    is_production = not app.debug or os.environ.get('WERKZEUG_RUN_MAIN') == 'true'
    
    # Set the host to '0.0.0.0' to be accessible from outside the container/server
    # In local development, you might prefer '127.0.0.1' or 'localhost'
    run_host = '0.0.0.0'
    
    # Disable debug mode and reloader in a production-like environment
    # The reloader can cause issues with background threads and resource management
    use_reloader = False if is_production else True
    
    print("\n" + "=" * 60)
    print("🚀 Voice Agent Demo Starting!")
    print("=" * 60)
    print(f"\n1. Open this link in your browser to start the demo:")
    print(f"   http://{run_host}:{port}")
    print("\n2. Click 'Start Voice Agent' when the page loads")
    print("\n3. Speak with the agent using your microphone")
    print("\nPress Ctrl+C to stop the server\n")
    print("=" * 60 + "\n")

    # Use app.run for more control over parameters
    socketio.run(app, host=run_host, port=port, debug=False, use_reloader=False)
