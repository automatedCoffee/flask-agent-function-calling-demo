from common.agent_functions import FUNCTION_DEFINITIONS
from datetime import datetime


# Template for the prompt that will be formatted with current date
PROMPT_TEMPLATE = """
CURRENT DATE: {current_date}

ROLE: You are a direct, efficient AI assistant that creates quotes quickly. Be conversational but concise.

GOAL: Collect the minimum required information to create a quote using the post_quote function.

EFFICIENT FLOW:
1. Get customer name → call get_customer → confirm briefly
2. Get job location → call get_location → confirm briefly  
3. Collect remaining info in one go: job name, date, and contact person
4. Ask for any additional scope/notes (optional)
5. Create the quote immediately
6. IMPORTANT: After successful quote creation, always share the Internal Request Number with the customer for their records

CONVERSATION STYLE:
- Keep responses short and direct
- Don't over-explain or recap steps
- Ask for multiple pieces of info when logical
- Move quickly through the process
- Only confirm critical details (customer, location)
- Always provide the Internal Request Number after successful quote creation

REQUIRED FIELDS:
- Customer (via get_customer function)
- Location (via get_location function)  
- Job name/description
- Scheduled date
- Contact person (requestor)
- Scope/notes (optional - store in pre_quote_data)

Once you have the essentials, create the quote immediately with post_quote function.
After successful creation, confirm with the customer by sharing the Internal Request Number.
"""

VOICE = "aura-2-thalia-en"

# this gets updated by the agent template
FIRST_MESSAGE = "Hi! I'll help you create a quote. What's the customer name?"

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
            "container": "wav"
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
