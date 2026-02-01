# Smart Building Edge Telemetry System

A lightweight, edge-focused real-time telemetry system for smart building sensor data using industry-standard open-source components.

## 🏗️ Architecture

```
Sensor Simulator (8 rooms @ 2Hz)
    ↓
NanoMQ (MQTT Broker)
    ├─→ Raw topics: telemetry/01-08
    ↓
eKuiper (Stream Processing)
    └─→ Downsampled topics: ds_telemetry/01-08 (0.2Hz, 5s windows)
         ↓
    Telegraf (Data Bridge)
         └─→ InfluxDB (Time-Series Database)
              ↓
         Grafana (Visualization)
```

## 📊 Project Components

### 1. Sensor Simulator (Python)
- **8 Unique Room Profiles**: Server room, conference room, storage, office, kitchen, lab, break room, executive office
- **Metrics**: Temperature, humidity, CO2, light, occupancy, motion, energy, air quality
- **Publishing Rate**: 0.5s intervals (2 messages/sec per room = 16 msgs/sec total)
- **Topics**: `telemetry/01` through `telemetry/08`

### 2. NanoMQ (MQTT Broker)
- **Type**: Ultra-lightweight MQTT broker from LF Edge
- **Protocol**: MQTT 3.1.1 on port 1883, WebSocket on port 8083
- **Role**: Message transport layer for sensor data

### 3. eKuiper (Stream Processing)
- **Type**: Lightweight edge streaming SQL engine from LF Edge  
- **Function**: Real-time downsampling and aggregation
- **Input**: Raw 2Hz streams from `telemetry/#`
- **Processing**: 5-second hopping windows (10s window, 5s hop)
- **Aggregations**: AVG for continuous metrics, MAX for discrete events
- **Output**: Downsampled 0.2Hz streams to `ds_telemetry/#`
- **Data Reduction**: 90% (16 msgs/sec → 1.6 msgs/sec)

### 4. Telegraf (Data Bridge)
- **Type**: Plugin-driven data collection agent
- **Function**: MQTT consumer → InfluxDB writer
- **Input**: Subscribes to `ds_telemetry/#` topics
- **Output**: Writes to InfluxDB v2 with proper tags and fields
- **Benefits**: Production-ready, no custom code needed

### 5. InfluxDB (Time-Series Database)
- **Version**: InfluxDB 2.7
- **Organization**: `smart-building`
- **Bucket**: `sensor_data` (30-day retention)
- **Data Model**: 
  - Measurement: `sensor_telemetry`
  - Tags: `room_id`
  - Fields: `temperature`, `humidity`, `co2_ppm`, `light_lux`, `occupancy_count`, `motion_detected`, `energy_kwh`, `air_quality_index`
  - Timestamp: from sensor data

### 6. Grafana (Visualization)
- **Dashboards**: Single unified dashboard with room selector
- **Visualizations**:
  - 6 time-series line charts (temperature, humidity, CO2, light, energy, air quality)
  - 1 gauge panel (current occupancy)
  - 1 state timeline (motion detection)
- **Data Source**: InfluxDB with Flux queries
- **Auto-refresh**: Every 5 seconds

## 🏠 Room Profiles

| Room ID | Name | Characteristics |
|---------|------|-----------------|
| 01 | Server Room | Cool (18-20°C), low humidity, always "occupied", high energy |
| 02 | Conference Room | Variable temp/humidity, burst occupancy, variable energy |
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
  "timestamp": "2026-02-01T10:30:45.500Z",
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

### Downsampled Message (Aggregated over 5 seconds)
```json
{
  "room_id": "01",
  "timestamp": "2026-02-01T10:30:50.000Z",
  "temperature": 19.18,
  "humidity": 35.42,
  "co2_ppm": 448.5,
  "light_lux": 0,
  "occupancy_count": 0,
  "motion_detected": 0,
  "energy_kwh": 2.31,
  "air_quality_index": 94.8
}
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- 2GB+ RAM recommended
- 5GB+ disk space

### Startup

1. **Start all services**
```bash
docker-compose up -d
```

2. **Verify services are running**
```bash
docker-compose ps
```

All services should show as "Up":
- smart-building-nanomq
- smart-building-sensor-simulator
- smart-building-ekuiper
- smart-building-telegraf
- smart-building-influxdb
- smart-building-grafana

3. **Access the dashboard**
- Grafana: http://localhost:3000 (admin/admin)
- InfluxDB UI: http://localhost:8086 (admin/admin123456)
- eKuiper UI: http://localhost:20498

### Verification

**Check MQTT topics:**
```bash
# Install mosquitto-clients if needed
sudo apt-get install mosquitto-clients

# Subscribe to raw telemetry
mosquitto_sub -h localhost -t "telemetry/#" -v

# Subscribe to downsampled telemetry
mosquitto_sub -h localhost -t "ds_telemetry/#" -v
```

**Check InfluxDB data:**
```bash
# View Telegraf logs
docker logs smart-building-telegraf --tail 50

# Query InfluxDB via CLI
docker exec -it smart-building-influxdb influx query \
  'from(bucket:"sensor_data") |> range(start: -5m) |> limit(n:10)'
```

**Check Grafana dashboard:**
1. Navigate to http://localhost:3000
2. Login with admin/admin
3. Go to Dashboards → Smart Building - Room Telemetry
4. Select a room from the dropdown
5. Observe real-time data visualization

## 📁 Project Structure

```
smart-building/
├── config/
│   ├── nanomq.conf          # NanoMQ broker configuration
│   └── telegraf.conf        # Telegraf MQTT→InfluxDB bridge config
├── ekuiper/
│   └── etc/
│       ├── init.json        # eKuiper streams and rules auto-loaded at startup
│       └── mqtt_source.yaml # MQTT source configuration
├── grafana/
│   └── provisioning/
│       ├── dashboards/
│       │   ├── dashboard.yaml              # Dashboard provisioning config
│       │   └── smart-building-dashboard.json # Pre-built dashboard
│       └── datasources/
│           └── influxdb.yaml               # InfluxDB datasource config
├── influxdb/
│   └── init/                # InfluxDB initialization scripts (optional)
├── sensor-simulator/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── sensor_simulator.py  # Main simulator
│   └── room_profiles.py     # Room profile definitions
├── docker-compose.yml       # Service orchestration
└── README.md
```

## 🔧 Configuration

### Adjusting Publish Rate
Edit `docker-compose.yml`:
```yaml
environment:
  - PUBLISH_INTERVAL=0.5  # Change to 1.0 for 1 msg/sec, 0.1 for 10 msg/sec
```

### Adjusting Downsampling Window
Edit `ekuiper/etc/init.json` - change `HOPPINGWINDOW(ss, 10, 5)`:
- First parameter (10): Window size in seconds
- Second parameter (5): Hop interval in seconds

### Changing Data Retention
Edit `docker-compose.yml`:
```yaml
environment:
  - DOCKER_INFLUXDB_INIT_RETENTION=30d  # Change to 7d, 90d, etc.
```

## 🛑 Shutdown

```bash
# Stop all services
docker-compose down

# Stop and remove volumes (deletes all data)
docker-compose down -v
```

## 📊 Performance Metrics

- **Raw message rate**: 16 messages/second (8 rooms × 2 Hz)
- **Downsampled rate**: 1.6 messages/second (8 rooms × 0.2 Hz)  
- **Data reduction**: 90%
- **Memory footprint**: ~500MB total (all services)
- **CPU usage**: <5% on modern systems

## 🎯 Use Cases

- **Building automation**: Monitor HVAC, lighting, energy consumption
- **Occupancy analytics**: Track space utilization patterns
- **Air quality monitoring**: CO2 and general air quality tracking
- **Energy optimization**: Identify energy waste and optimization opportunities
- **Anomaly detection**: Detect unusual patterns in sensor data
- **Edge computing demonstration**: Showcase edge processing before cloud upload

## 🔍 Troubleshooting

**No data in Grafana:**
1. Check InfluxDB has data: http://localhost:8086 → Data Explorer
2. Check Telegraf logs: `docker logs smart-building-telegraf`
3. Verify MQTT messages: `mosquitto_sub -h localhost -t "ds_telemetry/#"`

**Services not starting:**
1. Check logs: `docker-compose logs [service-name]`
2. Verify ports are available: `netstat -tulpn | grep -E "1883|8086|3000"`
3. Check Docker resources: Ensure sufficient memory/CPU

**eKuiper rules not loading:**
1. Check syntax: `docker logs smart-building-ekuiper | grep -i error`
2. Verify MQTT connection: `docker logs smart-building-ekuiper | grep -i mqtt`

## 📚 Technology Stack

| Component | Technology | Purpose |
|-----------|-----------|---------|
| MQTT Broker | NanoMQ (LF Edge) | Lightweight message transport |
| Stream Processing | eKuiper (LF Edge) | Real-time data aggregation |
| Data Bridge | Telegraf | MQTT to InfluxDB pipeline |
| Time-Series DB | InfluxDB 2.7 | Persistent storage |
| Visualization | Grafana | Dashboards and analytics |
| Sensors | Python | Data generation |

## 📝 License

This is a demonstration project for educational purposes.

## 🤝 Contributing

This is a reference implementation. Feel free to fork and adapt for your needs.
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
