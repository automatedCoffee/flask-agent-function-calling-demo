#!/bin/bash

# Start PulseAudio in system mode with our configuration
pulseaudio --system --disallow-exit --disallow-module-loading --file=/etc/pulse/default.pa --daemonize

# Wait for PulseAudio to start and create socket
sleep 2

# Verify PulseAudio is running
if ! pulseaudio --check; then
    echo "Failed to start PulseAudio"
    exit 1
fi

# Configure ALSA to use PulseAudio
export ALSA_CONFIG_PATH=/etc/asound.conf

# Execute the CMD from Dockerfile (passed as arguments to this script)
exec "$@" 