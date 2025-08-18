# Voice Agent Function Calling Python Demo

This is a demo application showcasing a voice agent that can take service quotes and interact with a backend system using function calling. It is built with Flask, Socket.IO, and the Deepgram Voice Agent API.

## Refactored for Stability and Performance

This version of the application has been significantly refactored to address issues with choppy audio, input timeouts, and overall stability. The key improvements include:

-   **Modular Frontend Architecture:** The frontend JavaScript has been reorganized into a clean, modular structure with clear separation of concerns:
    -   `app.js`: Manages the main application state and WebSocket communication.
    -   `audio.js`: Handles all Web Audio API interactions, including microphone input and precisely scheduled audio playback for smooth, uninterrupted output.
    -   `ui.js`: Manages all DOM updates and user interface logic.
-   **Robust Backend Logic:** The Python backend has been enhanced for greater resilience and reliability:
    -   **Graceful Shutdown:** The server now handles shutdown signals gracefully, ensuring that all background threads and connections are properly terminated.
    -   **Stable WebSocket Connections:** The connection to the Deepgram API is now more robust, with improved error handling and connection management to prevent unexpected disconnects.
    -   **Reliable Agent Lifecycle:** The voice agent's lifecycle is carefully managed to prevent race conditions and ensure clean startup and shutdown procedures.

These changes result in a much smoother and more reliable user experience, eliminating the audio artifacts and hangs that were present in the previous version.

## Features

-   **Real-time Voice Interaction:** Speak with the agent in real-time to provide details for a service quote.
-   **Function Calling:** The agent can call backend functions to look up customer information and create quotes in a simulated ERP system (Backendless).
-   **Dynamic UI:** The UI provides real-time status updates, conversation history, and debug logs.
-   **Modular Codebase:** The code is organized into logical modules for easier maintenance and extension.

## Getting Started

### Prerequisites

-   Python 3.8+
-   `pip` for Python package management
-   An active Deepgram API key with credits
-   (Optional) A free Backendless account to store customer and quote data

### Installation

1.  **Clone the repository:**

    ```bash
    git clone https://github.com/your-username/flask-agent-function-calling-demo.git
    cd flask-agent-function-calling-demo
    ```

2.  **Create and activate a virtual environment:**

    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows, use `venv\Scripts\activate`
    ```

3.  **Install the required Python packages:**

    ```bash
    pip install -r requirements.txt
    ```

4.  **Set up your environment variables:**

    -   Copy the `sample.env` file to a new file named `.env`:
        ```bash
        cp sample.env .env
        ```
    -   Open the `.env` file and add your Deepgram API key:
        ```env
        DEEPGRAM_API_KEY="YOUR_DEEPGRAM_API_KEY"
        ```
    -   (Optional) If you are using Backendless, add your App ID and API Key to the `.env` file. You can find these in your Backendless dashboard.
        ```env
        BACKENDLESS_API_URL="YOUR_BACKENDLESS_API_URL"
        BACKENDLESS_APP_ID="YOUR_BACKENDLESS_APP_ID"
        BACKENDLESS_API_KEY="YOUR_BACKENDLESS_API_KEY"
        ```
        If you do not provide these, the application will fall back to using mock data for customer and location lookups.

### Running the Application

1.  **Start the Flask server:**

    ```bash
    python client.py
    ```

2.  **Open your web browser** and navigate to `http://localhost:5000`.

3.  **Allow microphone access** when prompted by the browser.

4.  **Click the "Start Voice Agent" button** to begin the conversation.

5.  **Hold down the "Hold to Speak" button** to talk to the agent. Release the button when you are finished speaking.

## How It Works

1.  **Client-Side (Browser):**
    -   `index.html`: The main page structure.
    -   `app.js`: Initializes the application, handles Socket.IO communication, and manages the overall state.
    -   `audio.js`: Uses the Web Audio API to capture microphone input and play back the agent's audio responses.
    -   `ui.js`: Updates the user interface with conversation history, status messages, and logs.
    -   `audio-processor.js`: An `AudioWorkletProcessor` that runs in a separate thread to process and downsample audio from the microphone before sending it to the server.

2.  **Server-Side (Flask):**
    -   `client.py`: The main Flask application. It handles HTTP requests, manages the Socket.IO server, and runs the `VoiceAgent`.
    -   `VoiceAgent`: A class that encapsulates the logic for interacting with the Deepgram Voice Agent API via WebSockets. It sends user audio to Deepgram and receives agent responses and audio back.
    -   `common/agent_functions.py`: Defines the functions that the voice agent can call (e.g., `get_customer`, `post_quote`).
    -   `common/business_logic.py`: Contains the logic for interacting with the Backendless API or mock data.
    -   `common/agent_templates.py`: Configures the agent's personality, voice, and function definitions.

## Project Structure

```
├── common/
│   ├── agent_functions.py    # Function definitions and routing
│   ├── business_logic.py     # Core function implementations
│   ├── config.py             # Configuration settings
│   ├── log_formatter.py      # Logger setup
├── client.py             # WebSocket client and message handling
```

## Mock Data System

The implementation uses a mock data system for demonstration:
- Generates realistic customer, order, and appointment data
- Saves data to timestamped JSON files in `mock_data_outputs/`
- Configurable through `config.py`

### Artificial Delays
The implementation demonstrates how to handle real-world latency:
- Configurable database operation delays in `config.py`
- Helps simulate production environment timing

## Setup Instructions

0. Make sure you have portaudio installed.

In macOS:
```bash
brew install portaudio:
```

In Ubuntu:
```bash
sudo apt-get install portaudio19-dev
```

`pipenv` can be used to manage virtual env. and packages in one easy to use tool. Instead of running pip commands, you just use [pipenv](https://pypi.org/project/pipenv/).

1. Install pipenv if not already installed.

```bash
pip install pipenv
```

2. Switch to the pipenv virtual environment:

```bash
pipenv shell
```

3. Install the project dependencies:

In the root directory of the project, run the following command to install the dependencies:

```bash
pipenv install -r requirements.txt
```

4. Set your Deepgram API key. Either programatically:
```bash
export DEEPGRAM_API_KEY=<your-key-here>
```
   - or in a file named `.env` within your root directory which has this entry:
```
DEEPGRAM_API_KEY=<your-key-here>
```

## Application Usage

1. Run the client:
   ```bash
   python client.py
   ```

> The application will be available at http://localhost:5000

2. Use headphones to prevent audio feedback (the agent hearing itself).

## Example Interactions

The voice agent handles natural conversations like:

```
User: "I need to check my order status"
Agent: "Let me look that up for you..."
[Agent executes customer lookup]
Agent: "I can see you have two recent orders. Your most recent
       order from last week is currently being shipped..."
```

## Configuration

Key settings in `config.py`:
- `ARTIFICIAL_DELAY`: Configurable delays for database operations
- `MOCK_DATA_SIZE`: Control size of generated test data


## Issue Reporting

If you have found a bug or if you have a feature request, please report them at this repository issues section. Please do not report security vulnerabilities on the public GitHub issue tracker. The [Security Policy](./SECURITY.md) details the procedure for contacting Deepgram.

## Author

[Deepgram](https://deepgram.com)

## License

This project is licensed under the MIT license. See the [LICENSE](./LICENSE) file for more info.
