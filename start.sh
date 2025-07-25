#!/bin/bash

# Stop any existing PulseAudio instances to ensure a clean slate.
pulseaudio --kill &>/dev/null
pkill pulseaudio &>/dev/null
sleep 1

# --- Configure PulseAudio for System-Wide Mode ---
echo "Configuring PulseAudio for system-wide mode..."

# Clean up any leftover files that could cause conflicts.
rm -rf /var/run/pulse/* /var/lib/pulse/* /tmp/pulseaudio.socket

# Create necessary directories and set permissions.
mkdir -p /var/run/pulse /var/lib/pulse
chown -R pulse:pulse /var/run/pulse /var/lib/pulse || { echo "ERROR: Failed to chown pulse directories. Does the 'pulse' user exist? Try 'apt-get install pulseaudio'"; exit 1; }

# Create a minimal system.pa configuration to avoid loading default configs that might fail on a headless server.
cat > /etc/pulse/system.pa << EOL
.fail
load-module module-null-sink sink_name=dummy sink_properties=device.description="Virtual_Dummy_Sink"
load-module module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulseaudio.socket
set-default-sink dummy
set-default-source dummy.monitor
EOL

# --- Start PulseAudio Daemon ---
echo "Starting PulseAudio in system-wide daemon mode..."
pulseaudio --system --disallow-exit --exit-idle-time=-1 --daemonize

# --- Wait for PulseAudio to be Ready ---
echo "Waiting for PulseAudio service to start..."
until pactl info &>/dev/null; do
    echo -n "."
    sleep 1
done
echo "\nPulseAudio service is responsive."

# --- Configure ALSA to use PulseAudio ---
# This tells ALSA-aware applications (like PyAudio) to use our PulseAudio server.
cat > /etc/asound.conf << EOL
pcm.!default {
    type pulse
}
ctl.!default {
    type pulse
}
EOL

# --- Final Checks and Application Start ---
sleep 1
echo "--- PulseAudio Sinks (Outputs) ---"
pactl list sinks short
echo "--- PulseAudio Sources (Inputs) ---"
pactl list sources short

echo "--- Starting Application ---"
exec "$@" 