#!/bin/bash

# Check status of Flask Agent Function Calling Demo

PID_FILE="/tmp/flask-agent.pid"
PORT=5000

echo "📊 Flask Agent Function Calling Demo - Status Check"
echo "=================================================="

# Check PID file and process
if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        echo "✅ Application is RUNNING (PID: $PID)"
    else
        echo "❌ Application is NOT running (stale PID file)"
        rm -f "$PID_FILE"
    fi
else
    echo "❌ Application is NOT running (no PID file)"
fi

# Check if port is in use
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1; then
    echo "🌐 Port $PORT is in use"
else
    echo "🌐 Port $PORT is free"
fi

# Check recent logs
echo ""
echo "📝 Recent application logs:"
echo "---------------------------"
if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    # If running, show last few lines of logs (if accessible)
    echo "   Application is running - logs are in real-time"
else
    echo "   Application is not running - no logs to show"
fi

# Show system resource usage
echo ""
echo "🖥️  System Resources:"
echo "--------------------"
if command -v htop >/dev/null 2>&1; then
    echo "   Use 'htop' to monitor system resources"
else
    echo "   CPU: $(uptime | awk -F'load average:' '{print $2}')"
    echo "   Memory: $(free -h | awk 'NR==2{printf "%.1f%% used", $3*100/$2}')"
fi

echo ""
echo "🔧 Management Commands:"
echo "----------------------"
echo "   Start:   ./start_production.sh"
echo "   Stop:    ./stop_production.sh"
echo "   Restart: ./restart_production.sh"
echo "   Status:  ./status_production.sh"
