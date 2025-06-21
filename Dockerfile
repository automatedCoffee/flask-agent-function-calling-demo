FROM python:3.12-slim

# Install system dependencies including portaudio, pulseaudio, alsa and curl
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pip \
    curl \
    pulseaudio \
    alsa-utils \
    libasound2-plugins \
    libasound2 \
    libpulse0 \
    pulseaudio-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Create necessary directories
RUN mkdir -p /var/run/pulse /var/lib/pulse /etc/pulse /etc/alsa

# Configure system user for PulseAudio
RUN adduser --system --home /var/run/pulse --group pulse && \
    adduser --system --home /var/run/pulse --group pulse-access && \
    usermod -aG pulse-access root

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