#!/bin/bash
set -e

# Wait for InfluxDB to be ready
echo "Waiting for InfluxDB to be ready..."
until influx ping --host http://localhost:8086 > /dev/null 2>&1; do
  sleep 1
done

echo "InfluxDB is ready!"

# Configuration
INFLUX_HOST="http://localhost:8086"
INFLUX_TOKEN="${DOCKER_INFLUXDB_INIT_ADMIN_TOKEN}"
INFLUX_ORG="${DOCKER_INFLUXDB_INIT_ORG}"

# List of buckets to create
BUCKETS=("sensor_data" "monitoring_ekuiper" "monitoring_nanomq")

# Function to check if bucket exists
bucket_exists() {
  local bucket_name=$1
  influx bucket list \
    --host "${INFLUX_HOST}" \
    --token "${INFLUX_TOKEN}" \
    --org "${INFLUX_ORG}" \
    --name "${bucket_name}" \
    --hide-headers | grep -q "${bucket_name}"
}

# Create buckets if they don't exist
for bucket in "${BUCKETS[@]}"; do
  if bucket_exists "${bucket}"; then
    echo "Bucket '${bucket}' already exists, skipping..."
  else
    echo "Creating bucket '${bucket}'..."
    influx bucket create \
      --host "${INFLUX_HOST}" \
      --token "${INFLUX_TOKEN}" \
      --org "${INFLUX_ORG}" \
      --name "${bucket}" \
      --retention 7d
    echo "Bucket '${bucket}' created successfully!"
  fi
done

echo "Bucket initialization complete!"