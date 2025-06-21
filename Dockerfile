FROM python:3.12-slim

# Install system dependencies including portaudio, pulseaudio, alsa and curl
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pip \
    curl \
    pulseaudio \
    alsa-utils \
    libasound2-plugins \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Configure virtual audio devices
RUN mkdir -p /etc/alsa && \
    echo 'pcm.!default { type null }' > /etc/asound.conf && \
    echo 'ctl.!default { type null }' >> /etc/asound.conf

# Configure PulseAudio
RUN mkdir -p /var/run/pulse /var/lib/pulse /etc/pulse
RUN adduser --system --home /var/run/pulse pulse
RUN adduser --system --home /var/run/pulse pulse-access
RUN usermod -aG pulse-access root

# Create PulseAudio configuration
RUN echo "default-server = unix:/tmp/pulseaudio.socket" > /etc/pulse/client.conf && \
    echo "autospawn = no" >> /etc/pulse/client.conf && \
    echo "daemon-binary = /bin/true" >> /etc/pulse/client.conf && \
    echo "enable-shm = false" >> /etc/pulse/client.conf

# Configure PulseAudio daemon
RUN echo "load-module module-null-sink sink_name=dummy sink_properties=device.description=dummy_sink" > /etc/pulse/default.pa && \
    echo "load-module module-native-protocol-unix auth-anonymous=1 socket=/tmp/pulseaudio.socket" >> /etc/pulse/default.pa && \
    echo "load-module module-always-sink" >> /etc/pulse/default.pa

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn eventlet

# Create directories for data and ensure proper permissions
RUN mkdir -p /app/quote_data_outputs /app/mock_data_outputs && \
    chmod 777 /app/quote_data_outputs /app/mock_data_outputs

# Expose port 5000
EXPOSE 5000

# Copy start script and make it executable
COPY start.sh /start.sh
RUN chmod +x /start.sh

# Use start.sh as entrypoint
ENTRYPOINT ["/start.sh"]

# Production command using gunicorn
CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "client:app"] 