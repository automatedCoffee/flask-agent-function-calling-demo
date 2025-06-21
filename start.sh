#!/bin/bash

# Kill any existing PulseAudio processes
pulseaudio --kill || true

# Clean up any existing PulseAudio files
rm -rf /var/run/pulse/* /var/lib/pulse/* /tmp/pulseaudio.socket

# Create necessary directories and set permissions
mkdir -p /var/run/pulse /var/lib/pulse
chown -R pulse:pulse /var/run/pulse /var/lib/pulse
chmod -R 755 /var/run/pulse /var/lib/pulse

# Create PulseAudio client configuration
cat > /etc/pulse/client.conf << EOL
default-server = unix:/tmp/pulseaudio.socket
autospawn = no
daemon-binary = /bin/true
enable-shm = false
EOL

# Create PulseAudio daemon configuration
cat > /etc/pulse/daemon.conf << EOL
daemonize = no
system-instance = yes
exit-idle-time = -1
high-priority = no
nice-level = -11
realtime-scheduling = no
realtime-priority = 5
allow-module-loading = yes
allow-exit = no
use-pid-file = no
EOL

# Create PulseAudio system configuration
cat > /etc/pulse/system.pa << EOL
.fail
load-module module-null-sink sink_name=dummy sink_properties=device.description=dummy_sink
load-module module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulseaudio.socket
EOL

# Start PulseAudio in the foreground (non-daemonized)
pulseaudio --system -vvv --log-level=4 --log-target=stderr --file=/etc/pulse/system.pa &

# Wait for PulseAudio socket
for i in {1..10}; do
    if [ -S /tmp/pulseaudio.socket ]; then
        echo "PulseAudio socket found, continuing..."
        break
    fi
    echo "Waiting for PulseAudio socket... (attempt $i)"
    sleep 2
done

# Configure ALSA
mkdir -p /etc/alsa
cat > /etc/asound.conf << EOL
pcm.!default {
    type pulse
    fallback "null"
    device null
}

ctl.!default {
    type pulse
    fallback "null"
}
EOL

# List audio devices for debugging
echo "Listing PulseAudio devices:"
pactl list || true
echo "Listing ALSA devices:"
aplay -l || true

# Execute the CMD from Dockerfile (passed as arguments to this script)
exec "$@" 