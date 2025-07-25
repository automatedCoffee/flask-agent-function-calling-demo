#!/bin/bash

# --- Stop and Clean Up ---
echo "Stopping any existing PulseAudio instances..."
pulseaudio --kill &>/dev/null
pkill pulseaudio &>/dev/null
sleep 1
rm -rf /var/run/pulse/* /var/lib/pulse/* /tmp/pulseaudio.socket

# --- Configure and Start PulseAudio ---
echo "Configuring and starting PulseAudio in system-wide mode..."
mkdir -p /var/run/pulse /var/lib/pulse
chown -R pulse:pulse /var/run/pulse /var/lib/pulse

# Create a clean system.pa config with TWO INDEPENDENT VIRTUAL DEVICES
# This is the key to eliminating the feedback loop.
cat > /etc/pulse/system.pa << EOL
.fail

# 1. A virtual SINK (speaker) for the agent to play audio to.
load-module module-null-sink sink_name=agent_speaker sink_properties=device.description="Virtual_Agent_Speaker"

# 2. A virtual SOURCE (microphone) that produces a constant stream of silence.
# This source is NOT a monitor of the sink, thus breaking the feedback loop.
load-module module-zero-source source_name=user_mic source_properties=device.description="Virtual_User_Microphone"

# 3. The native protocol socket for clients to connect to.
load-module module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulseaudio.socket

# 4. Set these new devices as the defaults for the system.
set-default-sink agent_speaker
set-default-source user_mic
EOL

# Start the PulseAudio daemon
pulseaudio --system --disallow-exit --exit-idle-time=-1 --daemonize

# --- Wait for PulseAudio to be Ready ---
echo "Waiting for PulseAudio service..."
until pactl info &>/dev/null; do
    echo -n "."
    sleep 1
done
echo -e "\nPulseAudio service is responsive."

# --- Final Checks and Application Start ---
sleep 1
echo "--- PulseAudio Sinks (Outputs) ---"
pactl list sinks short
echo "--- PulseAudio Sources (Inputs) ---"
pactl list sources short

echo "--- Starting Application ---"
exec "$@" 