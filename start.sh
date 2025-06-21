#!/bin/bash

# Create necessary directories and set permissions
mkdir -p /var/run/pulse
chown pulse:pulse /var/run/pulse
chmod 755 /var/run/pulse

# Remove any existing PulseAudio socket
rm -f /tmp/pulseaudio.socket

# Start PulseAudio in system mode with our configuration
pulseaudio --system --disallow-exit --disallow-module-loading --file=/etc/pulse/default.pa --log-level=4 --log-target=stderr --daemonize

# Wait for PulseAudio to start and create socket
for i in {1..5}; do
    if [ -S /tmp/pulseaudio.socket ]; then
        echo "PulseAudio socket found, continuing..."
        break
    fi
    echo "Waiting for PulseAudio socket... (attempt $i)"
    sleep 2
done

# Verify PulseAudio is running
if ! pulseaudio --check; then
    echo "Failed to start PulseAudio"
    pulseaudio --system --kill
    sleep 1
    # Try starting again without daemonize to see the output
    exec pulseaudio --system --disallow-exit --disallow-module-loading --file=/etc/pulse/default.pa --log-level=4 --log-target=stderr
    exit 1
fi

# Configure ALSA to use PulseAudio
export ALSA_CONFIG_PATH=/etc/asound.conf

# List audio devices for debugging
echo "Listing PulseAudio devices:"
pactl list || true
echo "Listing ALSA devices:"
aplay -l || true

# Execute the CMD from Dockerfile (passed as arguments to this script)
exec "$@" 