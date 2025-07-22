#!/bin/bash

# Kill any existing PulseAudio processes to ensure a clean start
pulseaudio --kill || true

# Clean up any existing PulseAudio files that might cause conflicts
rm -rf /var/run/pulse/* /var/lib/pulse/* /tmp/pulseaudio.socket

# Create necessary directories and set permissions for PulseAudio system mode
mkdir -p /var/run/pulse /var/lib/pulse
chown -R pulse:pulse /var/run/pulse /var/lib/pulse
chmod -R 755 /var/run/pulse /var/lib/pulse

# Create PulseAudio client configuration to point to the correct socket
cat > /etc/pulse/client.conf << EOL
default-server = unix:/tmp/pulseaudio.socket
autospawn = no
EOL

# Create a clean system.pa configuration for our virtual audio device
cat > /etc/pulse/system.pa << EOL
.fail

# Load a virtual sink (output device) and a corresponding source (input device)
load-module module-null-sink sink_name=dummy sink_properties=device.description="Virtual_Dummy_Sink"
load-module module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulseaudio.socket

# Set the default devices
set-default-sink dummy
set-default-source dummy.monitor
EOL

# Start PulseAudio in system mode. It will automatically load /etc/pulse/system.pa.
pulseaudio --system --disallow-exit --exit-idle-time=-1 --daemonize=no --log-target=stderr -v &

# Wait for the PulseAudio socket to be created before proceeding
for i in {1..10}; do
    if [ -S /tmp/pulseaudio.socket ]; then
        echo "PulseAudio socket found, continuing..."
        break
    fi
    echo "Waiting for PulseAudio socket... (attempt $i)"
    sleep 1
done

if ! [ -S /tmp/pulseaudio.socket ]; then
    echo "PulseAudio socket not found after 10 seconds. Exiting."
    exit 1
fi

# Configure ALSA to use our PulseAudio server by default
# This is crucial for PyAudio to find and use the virtual devices
cat > /etc/asound.conf << EOL
pcm.!default {
    type pulse
}
ctl.!default {
    type pulse
}
EOL

# Add a small delay to ensure devices are registered
sleep 2

# List audio devices for debugging to confirm setup
echo "--- PulseAudio Sinks (Outputs) ---"
pactl list sinks short
echo "--- PulseAudio Sources (Inputs) ---"
pactl list sources short
echo "--- ALSA Devices ---"
aplay -l

# Execute the CMD from Dockerfile (passed as arguments to this script)
echo "--- Starting Application ---"
exec "$@" 