import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Get the Deepgram API key
dg_api_key = os.environ.get("DEEPGRAM_API_KEY")
if not dg_api_key:
    print("❌ ERROR: DEEPGRAM_API_KEY not found in environment variables.")
    print("Please ensure your .env file is present and correct.")
    exit(1)

# The URL that was failing in the logs
url = "https://api.deepgram.com/v1/models"
headers = {"Authorization": f"Token {dg_api_key}"}

print(f"Attempting to connect to: {url}")
print("-" * 50)

try:
    # Make the request with a timeout
    response = requests.get(url, headers=headers, timeout=10)
    
    # Check the status code
    print(f"✅ SUCCESS: Request completed.")
    print(f"Status Code: {response.status_code}")
    
    if response.status_code == 200:
        print("Response seems OK. First 100 characters of response:")
        print(response.text[:100] + "...")
    else:
        print("Received a non-200 status code. Response:")
        print(response.text)

except requests.exceptions.RequestException as e:
    print(f"❌ FAILED: An error occurred during the request.")
    print(f"Error Type: {type(e).__name__}")
    print(f"Error Details: {e}")

print("-" * 50) 