#!/usr/bin/env python3
"""
Environment validation script for Flask Agent Function Calling Demo
Run this to check if your environment is properly configured.
"""

import os
import sys
from dotenv import load_dotenv

def check_environment():
    """Check if all required environment variables are set"""
    print("🔍 Checking environment configuration...\n")

    # Load environment variables from .env file
    load_dotenv()

    # Check Deepgram API Key
    dg_key = os.environ.get("DEEPGRAM_API_KEY")
    if not dg_key:
        print("❌ DEEPGRAM_API_KEY is not set!")
        print("   Please set your Deepgram API key:")
        print("   1. Get your API key from https://console.deepgram.com/")
        print("   2. Set it in your environment: export DEEPGRAM_API_KEY='your_key_here'")
        print("   3. Or add it to a .env file in the project root")
        return False
    else:
        print(f"✅ DEEPGRAM_API_KEY is set (starts with: {dg_key[:8]}...)")

    # Validate API key format
    if len(dg_key.strip()) < 10:
        print("❌ DEEPGRAM_API_KEY appears to be invalid (too short)")
        return False

    # Check Backendless configuration
    backendless_app_id = os.environ.get("BACKENDLESS_APP_ID")
    backendless_api_key = os.environ.get("BACKENDLESS_API_KEY")

    if not backendless_app_id or not backendless_api_key:
        print("⚠️  Backendless configuration is missing or incomplete")
        print("   This may affect customer lookup functionality")
        print("   Set BACKENDLESS_APP_ID and BACKENDLESS_API_KEY if needed")
    else:
        print("✅ Backendless configuration is set")

    # Check if sessions directory exists
    if os.path.exists("sessions"):
        session_count = len([f for f in os.listdir("sessions") if os.path.isdir(os.path.join("sessions", f))])
        print(f"📁 Sessions directory exists with {session_count} sessions")
    else:
        print("📁 Sessions directory will be created automatically")

    print("\n🎉 Environment check complete!")
    return True

if __name__ == "__main__":
    success = check_environment()
    sys.exit(0 if success else 1)
