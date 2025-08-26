#!/bin/bash

# Stop production Flask Agent Function Calling Demo

PID_FILE="/tmp/flask-agent.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    echo "🛑 Stopping Flask Agent (PID: $PID)..."

    # Try graceful shutdown first
    kill -TERM "$PID" 2>/dev/null

    # Wait for up to 10 seconds for graceful shutdown
    for i in {1..10}; do
        if ! kill -0 "$PID" 2>/dev/null; then
            echo "✅ Application stopped gracefully"
            rm -f "$PID_FILE"
            exit 0
        fi
        echo "⏳ Waiting for graceful shutdown... ($i/10)"
        sleep 1
    done

    # Force kill if still running
    echo "⚠️  Force stopping application..."
    kill -KILL "$PID" 2>/dev/null
    rm -f "$PID_FILE"
    echo "✅ Application force stopped"
else
    echo "❌ No PID file found. Application may not be running."
    echo "   Check with: ps aux | grep gunicorn"
fi
