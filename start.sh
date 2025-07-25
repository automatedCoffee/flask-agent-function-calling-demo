#!/bin/bash

# Ensure no old pulseaudio is running under the current user
pulseaudio -k || true
# Give it a moment to die
sleep 1

# Start PulseAudio as a daemon for the current user
echo "Starting PulseAudio for the current user..."
pulseaudio --start --exit-idle-time=-1

# Wait for pulseaudio to be ready
until pactl info &>/dev/null; do
    echo "Waiting for PulseAudio service to start..."
    sleep 1
done
echo "PulseAudio service started."

# Unload the module if it already exists from a previous run
pactl unload-module module-null-sink 2>/dev/null || true

# Load the virtual audio device (null sink)
# This creates a sink named "dummy" and a source named "dummy.monitor"
echo "Loading virtual audio device..."
pactl load-module module-null-sink sink_name=dummy sink_properties=device.description="Virtual_Dummy_Sink"

# Set the "dummy.monitor" as the default source (microphone)
pactl set-default-source dummy.monitor

# Set the "dummy" sink as the default sink (speaker)
pactl set-default-sink dummy

# Add a small delay to ensure devices are fully registered
sleep 1

# List audio devices for debugging to confirm setup
echo "--- PulseAudio Sinks (Outputs) ---"
pactl list sinks short
echo "--- PulseAudio Sources (Inputs) ---"
pactl list sources short

# Execute the application
echo "--- Starting Application ---"
exec "$@" 