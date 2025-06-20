#!/bin/bash

# Start PulseAudio in system mode
pulseaudio --system --disallow-exit --disallow-module-loading --daemonize

# Wait for PulseAudio to start
sleep 2

# Load null sink module
pacmd load-module module-null-sink sink_name=dummy sink_properties=device.description=dummy_sink

# Start the Flask application
python client.py 