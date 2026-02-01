# Smart Building Edge Telemetry System

A lightweight, edge-focused real-time telemetry system for smart building sensor data using LF Edge components (NanoMQ, eKuiper), InfluxDB for time-series storage, and Grafana for visualization.

## 🏗️ Architecture

```
Python Sensors (8 rooms)
    ↓ (0.5s = 2Hz per room, 16 msgs/sec total)
NanoMQ (MQTT Broker)
    ↓ telemetry/01-08
eKuiper (Stream Processing)
    ↓ Downsample (5s windows = 0.2Hz)
    ├─→ NanoMQ (ds_telemetry/01-08)
    └─→ InfluxDB (smart_building bucket)
         ↓
    Grafana (Visualization)
         └─ Single dashboard with room selector
```

## 📊 Project Components

### 1. Data Generation
- **8 Unique Room Profiles**: Each room simulates different environmental patterns
- **Metrics**: Temperature, humidity, CO2, light, occupancy, motion, energy, air quality
- **Frequency**: Every 0.5 seconds (2 messages/sec per room = 16 msgs/sec total)

### 2. Message Transport
- **NanoMQ**: Ultra-lightweight MQTT broker from LF Edge
- **Raw Topics**: `telemetry/01` through `telemetry/08` (one per room)
- **Downsampled Topics**: `telemetry/ds/01` through `telemetry/ds/08` (processed data)
- **Protocol**: MQTT on port 1883, WebSocket on port 8083

### 3. Stream Processing
- **eKuiper**: Lightweight edge streaming SQL engine from LF Edge
- **Downsampling**: Aggregates 2Hz raw data into 0.2Hz streams (5-second windows)
- **Aggregations**: AVG for metrics, MAX for events
- **Dual Sinks**: Publishes to both NanoMQ (MQTT) and InfluxDB simultaneously

### 4. Time-Series Storage
- **InfluxDB**: Purpose-built time-series database
- **Bucket**: `smart_building`
- **Retention**: Configurable (default: 30 days)
- **Data Model**: Tags (room metadata) + Fields (sensor measurements)

### 5. Visualization
- **Grafana**: Real-time dashboarding and alerting
- **Dashboard**: Single unified view with room dropdown selector
- **Metrics**: Temperature, humidity, CO2, light, occupancy, motion, energy, air quality
- **Data Source**: InfluxDB with Flux queries

## 🏠 Room Profiles

| Room ID | Name | Characteristics |
|---------|------|-----------------|
| 01 | Server Room | Cool (18-20°C), low humidity, always "occupied", high energy |
| 02 | Conference Room | Swinging temp/humidity, burst occupancy, variable energy |
| 03 | Storage Closet | Always dark, stable temp, no occupancy, minimal energy |
| 04 | Open Office | Moderate temp, consistent occupancy (5-8), moderate energy |
| 05 | Kitchen | High humidity spikes, temp spikes, high energy bursts |
| 06 | Lab/Workshop | Highly variable everything, air quality issues |
| 07 | Break Room | Stable temp, low occupancy, variable lighting |
| 08 | Executive Office | Perfectly controlled, single occupancy, consistent |

## 📋 Data Schema

### Raw Telemetry Message (JSON)
```json
{
  "room_id": "01",
  "timestamp": "2026-01-31T10:30:45.500Z",
  "temperature": 19.2,
  "humidity": 35.5,
  "co2_ppm": 450,
  "light_lux": 0,
  "occupancy_count": 0,
  "motion_detected": false,
  "energy_kwh": 2.3,
  "air_quality_index": 95
}
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- 2GB+ RAM recommended
- 5GB+ disk space

### Setup

1. **Clone and navigate to project**
```bash
git clone <repo-url>
cd smart-building
```

2. **Start the stack**
```bash
docker-compose up -d
```

3. **Verify services**
```bash
docker-compose ps
```

All services should be running:
- NanoMQ: localhost:1883 (MQTT), localhost:8083 (WebSocket)
- eKuiper: http://localhost:9081 (REST API), http://localhost:20498 (Web UI)
- InfluxDB: http://localhost:8086 (Web UI & API)
- Grafana: http://localhost:3000 (Web UI, default: admin/admin)

eKuiper automatically loads from `ekuiper/etc/init.json`:
- 1 stream definition subscribing to `telemetry/#`
- 8 downsampling rules (one per room)
- Rules aggregate 5-second windows and output to `telemetry/ds/01` through `telemetry/ds/08`

## 📊 Monitoring & Validation

### Test MQTT Connection
Using MQTT Explorer or command line:
```bash
# Subscribe to raw telemetry (2Hz per room)
mosquitto_sub -h localhost -p 1883 -t "telemetry/01" -v

# Subscribe to downsampled telemetry (0.2Hz per room)
mosquitto_sub -h localhost -p 1883 -t "telemetry/ds/01" -v

# Subscribe to all downsampled topics
mosquitto_sub -h localhost -p 1883 -t "telemetry/ds/#" -v
```

Or using Docker:
```bash
# Raw data
docker exec -it smart-building-nanomq nanomq_cli sub -t "telemetry/01" -h localhost

# Downsampled data
docker exec -it smart-building-nanomq nanomq_cli sub -t "telemetry/ds/01" -h localhost
```

### Check eKuiper Streams
```bash
# List streams
curl http://localhost:9081/streams

# Check rules and their status
curl http://localhost:9081/rules

# Check specific rule status
curl http://localhost:9081/rules/downsample_room_01/status

# Access eKuiper web management console
open http://localhost:20498
```

### Query EdgeLake
```bash
# Query data via REST API
curl -X GET "http://localhost:32048/query?sql=SELECT * FROM telemetry LIMIT 10"
```

## 🐳 Docker Services

| Service | Port(s) | Description |
|---------|---------|-------------|
| sensor-simulator | - | Python sensor data generator |
| nanomq | 1883, 8083 | Ultra-lightweight MQTT broker from LF Edge |
| ekuiper | 9081, 20498 | Edge stream processing SQL engine from LF Edge |
| edgelake | 32048, 32049 | Distributed data management layer from LF Edge |

## 📁 Project Structure

```
smart-building/
├── docker-compose.yml
├── README.md
├── sensor-simulator/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── sensor_simulator.py
│   └── room_profiles.py
├── ekuiper/
│   ├── etc/
│   │   ├── sources/mqtt.yaml
│   │   ├── sinks/mqtt.yaml
│   │   └── init.json
│   ├── data/
│   └── log/
├── config/
│   └── nanomq.conf
└── data/
    └── .gitkeep
```

## 🎓 Why LF Edge Stack?

This project demonstrates edge computing using Linux Foundation Edge components:

1. **Open Source**: All LF Edge projects (NanoMQ, eKuiper, EdgeLake)
2. **Lightweight**: Optimized for edge deployment and resource-constrained devices
3. **Local Processing**: Stream processing and data management at the edge
4. **Interoperability**: Standards-based MQTT, SQL, and REST APIs
5. **Edge-to-Cloud**: Built-in support for edge-cloud data federation
6. **Resilient**: Operates independently without cloud connectivity

## 🔧 Configuration

Key parameters to experiment with:

- **Sensor frequency**: Adjust `PUBLISH_INTERVAL` in docker-compose.yml
- **Downsampling window**: Modify TUMBLINGWINDOW size in `ekuiper/etc/init.json` rules (currently 5 seconds)
- **Aggregation functions**: Edit SQL queries in `ekuiper/etc/init.json` (AVG, MAX, MIN, etc.)
- **eKuiper rules**: Add custom processing rules via REST API or web UI
- **EdgeLake policies**: Configure data retention and sync policies

## 📈 Data Flow & eKuiper Downsampling

### Raw Telemetry
- **Frequency**: 2 Hz (every 0.5 seconds)
- **Topics**: `telemetry/01` - `telemetry/08`
- **Volume**: 16 messages/second total (8 rooms × 2 Hz)

### Downsampled Telemetry
- **Frequency**: 0.2 Hz (every 5 seconds)
- **Topics**: `telemetry/ds/01` - `telemetry/ds/08`
- **Volume**: 1.6 messages/second total (8 rooms × 0.2 Hz)
- **Reduction**: 90% fewer messages
- **Aggregations**:
  - Temperature, humidity, CO2, light, energy, air quality: AVG
  - Occupancy count, motion detected: MAX (captures any activity)
  - Timestamp: Latest in window

### eKuiper Management

**View and manage rules:**
```bash
# List all rules
curl http://localhost:9081/rules

# Check specific rule status
curl http://localhost:9081/rules/downsample_room_01/status

# Delete a rule
curl -X DELETE http://localhost:9081/rules/downsample_room_01

# View streams
curl http://localhost:9081/streams

# Web UI for visual management
open http://localhost:20498
```

**eKuiper directory structure:**
- `ekuiper/etc/sources/mqtt.yaml`: MQTT source configuration
- `ekuiper/etc/sinks/mqtt.yaml`: MQTT sink configuration
- `ekuiper/etc/init.json`: Stream and rule definitions loaded at startup
- `ekuiper/data/`: Rule and stream state persistence
- `ekuiper/log/`: eKuiper logs

## 📚 Next Steps & Extensions

- [x] Add eKuiper downsampling for data volume reduction
- [ ] Add eKuiper rules for anomaly detection
- [ ] Configure EdgeLake data policies and retention
- [ ] Build dashboard for time-series visualization from EdgeLake
- [ ] Implement alerting based on sensor thresholds
- [ ] Test edge-to-cloud synchronization with EdgeLake
- [ ] Add ML model for predictive maintenance
- [ ] Add additional aggregation windows (1min, 15min, 1hour)

## 🐛 Troubleshooting

**Issue**: Sensor simulator can't connect to NanoMQ
- Check NanoMQ is running: `docker-compose logs nanomq`
- Verify network: `docker network ls`

**Issue**: eKuiper rules not processing data
- Check if rules are running: `curl http://localhost:9081/rules`
- Check rule status: `curl http://localhost:9081/rules/downsample_room_01/status`
- View eKuiper logs: `docker-compose logs ekuiper`
- Verify stream exists: `curl http://localhost:9081/streams`

**Issue**: No downsampled data on telemetry/ds/* topics
- Ensure init_rules.sh was executed
- Check eKuiper logs: `docker-compose logs ekuiper`
- Verify raw data is flowing: `mosquitto_sub -h localhost -t "telemetry.#"`
- Check rule metrics: `curl http://localhost:9081/rules/downsample_room_01/status`

**Issue**: No data in EdgeLake
- Check eKuiper rules: `curl http://localhost:9081/rules`
- Verify data flow: `docker-compose logs ekuiper`
- Check EdgeLake logs: `docker-compose logs edgelake`

**Issue**: High resource usage
- Adjust sensor publish interval (increase from 0.5s)
- Reduce eKuiper window sizes
- Configure EdgeLake data retention policies

## 📝 License

MIT License - Feel free to use for learning purposes

## 🙏 Acknowledgments

Built for learning edge computing, IoT data pipelines, and the Linux Foundation Edge ecosystem.
