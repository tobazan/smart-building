FROM golang:1.21-alpine AS builder

# Install build dependencies
RUN apk add --no-cache git gcc musl-dev

WORKDIR /build

# Copy all source files
COPY . .

# Tidy dependencies and build
RUN go mod tidy && go build -o golang-bridge .

# Final stage
FROM alpine:latest

RUN apk --no-cache add ca-certificates tzdata

WORKDIR /app

# Copy the binary from builder
COPY --from=builder /build/golang-bridge .

# Create data directory
RUN mkdir -p /data/parquet

# Set environment variables with defaults
ENV MQTT_BROKER=nanomq \
    MQTT_PORT=1883 \
    OUTPUT_DIR=/data/parquet \
    OUTPUT_FORMAT=parquet \
    FLUSH_INTERVAL_SEC=60 \
    FILE_ROTATION_SEC=300

CMD ["./golang-bridge"]
