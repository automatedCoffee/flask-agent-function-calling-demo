#!/bin/bash

# Restart Flask Agent Function Calling Demo

echo "🔄 Restarting Flask Agent Function Calling Demo..."

# Stop if running
if [ -f "/tmp/flask-agent.pid" ]; then
    echo "⏹️  Stopping existing instance..."
    ./stop_production.sh
    sleep 2  # Brief pause to ensure clean shutdown
fi

# Start new instance
echo "▶️  Starting new instance..."
./start_production.sh

# Check status
sleep 3
./status_production.sh
