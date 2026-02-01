FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set environment variables with defaults
ENV MQTT_BROKER=mosquitto \
    MQTT_PORT=1883 \
    MQTT_TOPIC_PREFIX=telemetry \
    PUBLISH_INTERVAL=0.5 \
    PYTHONUNBUFFERED=1

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import paho.mqtt.client as mqtt; import sys; sys.exit(0)"

# Default command (can be overridden in docker-compose)
CMD ["python", "sensor_simulator.py"]
