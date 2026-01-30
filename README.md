# Smart Building Telemetry Streaming Analytics

A real-time streaming analytics pipeline for smart building sensor data using MQTT, Redpanda (Kafka), and Apache Spark Streaming with Delta Lake.

## 🏗️ Architecture

```
Python Sensors (8 rooms) → MQTT Broker → MQTT-Kafka Bridge → Redpanda
    (0.5s intervals)                                            ↓
                                                         Spark Streaming
                                                         (10s windows, 5s slide)
                                                                ↓
                                                    ┌───────────┴───────────┐
                                                    ↓                       ↓
                                            Delta Lake (MinIO)    Redpanda Downsampled Topics
                                            Time-travel enabled    (telemetry.room_X.downsampled)
```

## 📊 Project Components

### 1. Data Generation
- **8 Unique Room Profiles**: Each room simulates different environmental patterns
- **Metrics**: Temperature, humidity, CO2, light, occupancy, motion, energy, air quality
- **Frequency**: Every 0.5 seconds (2 messages/sec per room = 16 msgs/sec total)

### 2. Message Transport
- **MQTT Broker**: Mosquitto for IoT device simulation
- **Redpanda**: Kafka-compatible streaming platform
- **Topics**: 
  - `telemetry.room_1` through `telemetry.room_8` (raw data)
  - `telemetry.room_1.downsampled` through `telemetry.room_8.downsampled` (aggregated)
- **Retention**: 3 days

### 3. Stream Processing
- **Spark Streaming**: Structured Streaming with sliding windows
- **Window Strategy**: 10-second windows sliding every 5 seconds
- **Operations**: Aggregations (avg, min, max, sum) with room metadata enrichment
- **Dual Sink**: Delta Lake + Redpanda

### 4. Storage & Analytics
- **Delta Lake**: ACID transactions, time-travel, schema evolution
- **MinIO**: S3-compatible object storage
- **SQLite**: Room metadata dimension table

## 🏠 Room Profiles

| Room ID | Name | Characteristics |
|---------|------|-----------------|
| room_1 | Server Room | Cool (18-20°C), low humidity, always "occupied", high energy |
| room_2 | Conference Room | Swinging temp/humidity, burst occupancy, variable energy |
| room_3 | Storage Closet | Always dark, stable temp, no occupancy, minimal energy |
| room_4 | Open Office | Moderate temp, consistent occupancy (5-8), moderate energy |
| room_5 | Kitchen | High humidity spikes, temp spikes, high energy bursts |
| room_6 | Lab/Workshop | Highly variable everything, air quality issues |
| room_7 | Break Room | Stable temp, low occupancy, variable lighting |
| room_8 | Executive Office | Perfectly controlled, single occupancy, consistent |

## 📋 Data Schema

### Raw Telemetry Message (JSON)
```json
{
  "room_id": "room_1",
  "timestamp": "2026-01-30T10:30:45.500Z",
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

### Aggregated Data (Delta Lake)
```
window_start, window_end, room_id, room_name, floor, room_type,
avg_temperature, min_temperature, max_temperature,
avg_humidity, min_humidity, max_humidity,
avg_co2, max_co2,
avg_light,
max_occupancy,
motion_events,
avg_energy,
avg_air_quality, min_air_quality
```

## 🚀 Quick Start

### Prerequisites
- Docker & Docker Compose
- 8GB+ RAM recommended
- 10GB+ disk space

### Setup

1. **Clone and navigate to project**
```bash
git clone <repo-url>
cd smart-building-streaming
```

2. **Start the stack**
```bash
docker-compose up -d
```

3. **Verify services**
```bash
docker-compose ps
```

All services should be healthy:
- Redpanda: http://localhost:8080 (Console)
- Spark Master: http://localhost:8081
- MinIO: http://localhost:9001 (admin/password)

4. **Initialize room metadata**
```bash
docker-compose exec sensor-simulator python init_metadata.py
```

5. **Start sensor simulation**
```bash
docker-compose exec sensor-simulator python sensor_simulator.py
```

6. **Start MQTT-Kafka bridge**
```bash
docker-compose exec mqtt-bridge python bridge.py
```

7. **Submit Spark streaming job**
```bash
docker-compose exec spark-master spark-submit \
  --master spark://spark-master:7077 \
  --packages io.delta:delta-core_2.12:2.4.0,org.apache.spark:spark-sql-kafka-0-10_2.12:3.5.0 \
  /app/streaming_app.py
```

## 📊 Monitoring & Validation

### Check Redpanda Topics
```bash
docker-compose exec redpanda rpk topic list
docker-compose exec redpanda rpk topic consume telemetry.room_1 --num 5
```

### Query Delta Lake
```python
from pyspark.sql import SparkSession

spark = SparkSession.builder \
    .config("spark.sql.extensions", "io.delta.sql.DeltaSparkSessionExtension") \
    .config("spark.sql.catalog.spark_catalog", "org.apache.spark.sql.delta.catalog.DeltaCatalog") \
    .getOrCreate()

df = spark.read.format("delta").load("s3a://datalake/telemetry_5s_agg")
df.show()

# Time travel
df_historical = spark.read.format("delta").option("versionAsOf", 0).load("s3a://datalake/telemetry_5s_agg")
```

### View Downsampled Topics
```bash
docker-compose exec redpanda rpk topic consume telemetry.room_1.downsampled
```

## 🧪 Testing Reprocessing

Stop the Spark job and replay data from 1 hour ago:

```bash
# Stop current job
docker-compose exec spark-master <kill process>

# Restart with earlier offset
# Modify streaming_app.py startingOffsets parameter
# Or use Kafka consumer groups to reset offset
```

## 🐳 Docker Services

| Service | Port(s) | Description |
|---------|---------|-------------|
| mosquitto | 1883 | MQTT broker |
| redpanda | 9092, 8081, 8082 | Kafka-compatible broker |
| redpanda-console | 8080 | Web UI for Redpanda |
| spark-master | 7077, 8081 | Spark cluster manager |
| spark-worker | 8082 | Spark executor |
| minio | 9000, 9001 | S3-compatible storage |
| sensor-simulator | - | Python sensor data generator |
| mqtt-bridge | - | MQTT to Kafka bridge |

## 📁 Project Structure

```
smart-building-streaming/
├── docker-compose.yml
├── README.md
├── sensor-simulator/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── sensor_simulator.py
│   ├── room_profiles.py
│   └── init_metadata.py
├── mqtt-bridge/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── bridge.py
├── spark-app/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── streaming_app.py
├── data/
│   └── metadata.db (SQLite)
└── config/
    ├── mosquitto.conf
    └── spark-defaults.conf
```

## 🎓 Learning Objectives

This project demonstrates:

1. **Streaming Data Ingestion**: MQTT → Kafka pattern for IoT
2. **Structured Streaming**: Spark's modern streaming API
3. **Windowing Operations**: Sliding windows for time-series aggregation
4. **Stream-Static Joins**: Enriching streams with dimension data
5. **Dual Sinks**: Writing to both data lake and streaming topics
6. **Delta Lake Features**: ACID, time-travel, schema evolution
7. **Reprocessing**: Replaying historical data from Kafka
8. **Backpressure Handling**: Spark's adaptive query execution

## 🔧 Configuration Tuning

Key parameters to experiment with:

- **Sensor frequency**: Adjust `PUBLISH_INTERVAL` in sensor_simulator.py
- **Window size**: Modify `.window()` in streaming_app.py
- **Parallelism**: Change Spark worker count and executor cores
- **Checkpointing**: Configure checkpoint interval for fault tolerance
- **Watermarking**: Add `.withWatermark()` for late data handling

## 📚 Next Steps & Extensions

- [ ] Add Grafana dashboards for real-time visualization
- [ ] Implement anomaly detection (e.g., temperature spikes)
- [ ] Add stateful operations (e.g., session windows per occupancy)
- [ ] Experiment with different aggregation windows (1min, 5min)
- [ ] Add data quality checks and alerting
- [ ] Implement exactly-once semantics testing
- [ ] Add schema evolution scenarios
- [ ] Test failure recovery and checkpoint restoration

## 🐛 Troubleshooting

**Issue**: Spark can't connect to Redpanda
- Check Redpanda is healthy: `docker-compose logs redpanda`
- Verify network: `docker network ls`

**Issue**: MinIO connection refused
- Ensure MinIO credentials match in Spark config
- Check bucket exists: `docker-compose exec minio mc ls local/`

**Issue**: No data in Delta Lake
- Check Spark job logs: `docker-compose logs spark-master`
- Verify watermark isn't too aggressive
- Check checkpoint location is writable

## 📝 License

MIT License - Feel free to use for learning purposes

## 🙏 Acknowledgments

Built for learning Apache Spark Structured Streaming, Delta Lake, and real-time data pipelines.
