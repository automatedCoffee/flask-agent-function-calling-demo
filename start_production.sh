#!/bin/bash

# Production startup script for Flask Agent Function Calling Demo
# This script validates the environment before starting the server

set -e  # Exit on any error

echo "🚀 Starting Flask Agent Function Calling Demo (Production Mode)"
echo "============================================================"

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ No .env file found!"
    echo "   Please create a .env file based on sample.env:"
    echo "   cp sample.env .env"
    echo "   Then edit .env with your actual API keys"
    exit 1
fi

# Check if virtual environment is activated
if [ -z "$VIRTUAL_ENV" ]; then
    echo "❌ Virtual environment not activated!"
    echo "   Please activate your virtual environment:"
    echo "   source venv/bin/activate  # Linux/Mac"
    echo "   venv\\Scripts\\activate     # Windows"
    exit 1
fi

# Run environment validation
echo "🔍 Validating environment configuration..."
if ! python check_env.py; then
    echo "❌ Environment validation failed!"
    echo "   Please fix the issues above and try again"
    exit 1
fi

echo ""
echo "✅ Environment validation passed!"
echo ""

# Check if we should use gunicorn or flask run
if command -v gunicorn &> /dev/null; then
    echo "🐍 Starting with Gunicorn (recommended for production)..."
    echo "   Workers: 1 (single worker for WebSocket compatibility)"
    echo "   Worker Class: GeventWebSocketWorker"
    echo ""

    # Start with gunicorn
    exec gunicorn \
        --worker-class geventwebsocket.gunicorn.workers.GeventWebSocketWorker \
        -w 1 \
        -b 0.0.0.0:5000 \
        --access-logfile - \
        --error-logfile - \
        --log-level info \
        client:app

else
    echo "🐍 Gunicorn not found, falling back to Flask development server..."
    echo "   WARNING: Not recommended for production!"
    echo "   Install gunicorn: pip install gunicorn[gevent]"
    echo ""

    # Fallback to flask run
    export FLASK_APP=client.py
    exec flask run --host=0.0.0.0 --port=5000
fi
