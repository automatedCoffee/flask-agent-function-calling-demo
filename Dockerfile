FROM python:3.12-slim

# Install system dependencies including portaudio, pulseaudio and curl (for healthcheck)
RUN apt-get update && apt-get install -y \
    portaudio19-dev \
    python3-pip \
    curl \
    pulseaudio \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Configure PulseAudio for virtual audio
RUN mkdir -p /var/run/pulse /var/lib/pulse
RUN adduser --system --home /var/run/pulse pulse
RUN adduser --system --home /var/run/pulse pulse-access
RUN usermod -aG pulse-access root

# Create PulseAudio configuration
RUN echo "default-server = unix:/tmp/pulseaudio.socket" > /etc/pulse/client.conf
RUN echo "autospawn = no" >> /etc/pulse/client.conf
RUN echo "daemon-binary = /bin/true" >> /etc/pulse/client.conf
RUN echo "enable-shm = false" >> /etc/pulse/client.conf

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt gunicorn eventlet

# Don't copy project files here - they will be mounted via docker-compose volume

# Create directory for quote data
RUN mkdir -p /app/quote_data_outputs && chmod 777 /app/quote_data_outputs

# Expose port 5000
EXPOSE 5000

# Start PulseAudio and the Flask application
COPY start.sh /start.sh
RUN chmod +x /start.sh

CMD ["/start.sh"]

# Development command using Flask's debug server
CMD ["python", "client.py"]

# Production command using gunicorn (commented out for reference)
# CMD ["gunicorn", "--worker-class", "eventlet", "-w", "1", "--bind", "0.0.0.0:5000", "client:app"] 