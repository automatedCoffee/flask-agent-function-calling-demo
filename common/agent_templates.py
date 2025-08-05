from common.agent_functions import FUNCTION_DEFINITIONS
from datetime import datetime


# Template for the prompt that will be formatted with current date
PROMPT_TEMPLATE = """You are an AI assistant for creating service quotes. Your only goal is to collect the necessary information and use your tools to create a quote. 

IMPORTANT: When using the tools, if you receive an error response (success: false), you MUST inform the user about the specific error and ask them to provide corrected information. Do NOT proceed with mock or made-up data.

Process:
1. Greet the user and ask for the customer's company name
2. Use get_customer tool to find their CustomerOid
   - If customer not found: Tell the user the exact company name was not found and ask them to provide the correct company name
   - If found: Confirm the customer name and proceed
3. Ask for the job location and use get_location tool
   - If location not found: Tell the user the location was not found and ask for a different address or location description
   - If found: Confirm the location and proceed
4. Gather remaining details: service date, contact person, job description, job name
5. Use post_quote tool to create the quote
6. Provide the Internal Request Number to the user

Never make up or assume customer or location data. Always use the actual results from your tools. The current date is {current_date}."""

VOICE = "aura-2-cora-en"

# this gets updated by the agent template
FIRST_MESSAGE = "Hello, I can help you create a service quote. What is the customer's company name?"

# audio settings
USER_AUDIO_SAMPLE_RATE = 24000
USER_AUDIO_SECS_PER_CHUNK = 1.0 / 50.0  # 20ms
USER_AUDIO_SAMPLES_PER_CHUNK = round(USER_AUDIO_SAMPLE_RATE * USER_AUDIO_SECS_PER_CHUNK)
USER_AUDIO_BYTES_PER_SEC = 2 * USER_AUDIO_SAMPLE_RATE

AGENT_AUDIO_SAMPLE_RATE = 24000
AGENT_AUDIO_BYTES_PER_SEC = 2 * AGENT_AUDIO_SAMPLE_RATE

VOICE_AGENT_URL = "wss://agent.deepgram.com/v1/agent/converse"

AUDIO_SETTINGS = {
    "input": {
        "encoding": "linear16",
        "sample_rate": USER_AUDIO_SAMPLE_RATE,
    },
    "output": {
        "encoding": "linear16",
        "sample_rate": AGENT_AUDIO_SAMPLE_RATE,
        "container": "wav"
    },
}

LISTEN_SETTINGS = {
    "provider": {
        "type": "deepgram",
        "model": "nova-3",
    }
}

THINK_SETTINGS = {
    "provider": {
        "type": "open_ai",
        "model": "gpt-4o-mini",
        "temperature": 0.7,
    },
    "prompt": PROMPT_TEMPLATE,
    "functions": FUNCTION_DEFINITIONS,
}

SPEAK_SETTINGS = {
    "provider": {
        "type": "deepgram",
        "model": VOICE,
    },
    "voice": {
        "name": "aura-2-thalia-en"
    },
    "output": {
        "encoding": "pcm_s16le"
    }
}

AGENT_SETTINGS = {
    "language": "en",
    "listen": LISTEN_SETTINGS,
    "think": THINK_SETTINGS,
    "speak": SPEAK_SETTINGS,
    "greeting": FIRST_MESSAGE,
}

SETTINGS = {
    "type": "Settings",
    "experimental": False,
    "audio": {
        "input": {
            "encoding": "linear16",
            "sample_rate": USER_AUDIO_SAMPLE_RATE
        },
        "output": {
            "encoding": "linear16",
            "sample_rate": AGENT_AUDIO_SAMPLE_RATE,
            "container": "none"
        }
    },
    "agent": {
        "language": "en",
        "listen": {
            "provider": {
                "type": "deepgram",
                "model": "nova-3"
            }
        },
        "think": {
            "provider": {
                "type": "open_ai",
                "model": "gpt-4o-mini",
                "temperature": 0.7
            },
            "prompt": PROMPT_TEMPLATE,
            "functions": FUNCTION_DEFINITIONS
        },
        "speak": {
            "provider": {
                "type": "deepgram",
                "model": VOICE
            }
        },
        "greeting": FIRST_MESSAGE
    }
}


class AgentTemplates:
    PROMPT_TEMPLATE = PROMPT_TEMPLATE

    def __init__(self, industry="tech_support", voiceName="", voiceModel="aura-2-thalia-en"):
        self.industry = industry
        self.voiceModel = voiceModel
        self.voiceName = voiceName if voiceName else self.get_voice_name_from_model(voiceModel)
        
        self.prompt = self.PROMPT_TEMPLATE.format(
            current_date=datetime.now().strftime("%A, %B %d, %Y")
        )

        self.voice_agent_url = VOICE_AGENT_URL
        self.settings = SETTINGS
        self.user_audio_sample_rate = USER_AUDIO_SAMPLE_RATE
        self.user_audio_secs_per_chunk = USER_AUDIO_SECS_PER_CHUNK
        self.user_audio_samples_per_chunk = USER_AUDIO_SAMPLES_PER_CHUNK
        self.agent_audio_sample_rate = AGENT_AUDIO_SAMPLE_RATE
        self.agent_audio_bytes_per_sec = AGENT_AUDIO_BYTES_PER_SEC

        # Set up the settings with the configured voice model and prompt
        self.settings["agent"]["speak"]["provider"]["model"] = self.voiceModel
        self.settings["agent"]["think"]["prompt"] = self.prompt
        self.settings["agent"]["greeting"] = FIRST_MESSAGE

    @staticmethod
    def get_available_industries():
        """Returns a list of available industries and their display names."""
        return {
            "tech_support": "Tech Support",
            "customer_service": "Customer Service",
            "sales": "Sales",
            "healthcare": "Healthcare",
            "education": "Education",
            "finance": "Finance",
            "retail": "Retail",
            "hospitality": "Hospitality"
        }

    @staticmethod
    def get_voice_name_from_model(model):
        """Extracts a human-readable voice name from the model string."""
        parts = model.split('-')
        if len(parts) >= 3:
            return parts[2].capitalize()
        return model
