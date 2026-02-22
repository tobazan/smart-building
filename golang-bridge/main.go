package main

import (
	"encoding/json"
	"fmt"
	"log"
	"os"
	"os/signal"
	"path/filepath"
	"sync"
	"syscall"
	"time"

	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/xitongsys/parquet-go-source/local"
	"github.com/xitongsys/parquet-go/parquet"
	"github.com/xitongsys/parquet-go/source"
	"github.com/xitongsys/parquet-go/writer"
)

// SensorTelemetry represents the downsampled sensor data structure
type SensorTelemetry struct {
	RoomID          string  `json:"room_id" parquet:"name=room_id, type=BYTE_ARRAY, convertedtype=UTF8"`
	Temperature     float64 `json:"temperature" parquet:"name=temperature, type=DOUBLE"`
	Humidity        float64 `json:"humidity" parquet:"name=humidity, type=DOUBLE"`
	CO2PPM          float64 `json:"co2_ppm" parquet:"name=co2_ppm, type=DOUBLE"`
	LightLux        float64 `json:"light_lux" parquet:"name=light_lux, type=DOUBLE"`
	OccupancyCount  int32   `json:"occupancy_count" parquet:"name=occupancy_count, type=INT32"`
	MotionDetected  bool    `json:"motion_detected" parquet:"name=motion_detected, type=BOOLEAN"`
	EnergyKWH       float64 `json:"energy_kwh" parquet:"name=energy_kwh, type=DOUBLE"`
	AirQualityIndex float64 `json:"air_quality_index" parquet:"name=air_quality_index, type=DOUBLE"`
	TimestampStr    string  `json:"timestamp"`                              // RFC3339 string from JSON
	Timestamp       int64   `json:"-" parquet:"name=timestamp, type=INT64"` // Unix nano for Parquet
}

// Config holds application configuration
type Config struct {
	MQTTBroker       string
	MQTTPort         string
	MQTTClientID     string
	MQTTTopicPattern string
	OutputDir        string
	OutputFormat     string
	FlushInterval    time.Duration
	FileRotation     time.Duration
}

// ParquetWriter manages writing data to parquet files
type ParquetWriter struct {
	mu           sync.Mutex
	currentFile  string
	writer       *writer.ParquetWriter
	fileWriter   source.ParquetFile
	recordCount  int64
	lastRotation time.Time
	config       *Config
}

func loadConfig() *Config {
	mqttBroker := getEnv("MQTT_BROKER", "nanomq")
	mqttPort := getEnv("MQTT_PORT", "1883")
	outputDir := getEnv("OUTPUT_DIR", "/data/parquet")
	outputFormat := getEnv("OUTPUT_FORMAT", "parquet")
	flushIntervalSec := getEnvAsInt("FLUSH_INTERVAL_SEC", 60)
	fileRotationSec := getEnvAsInt("FILE_ROTATION_SEC", 300)

	return &Config{
		MQTTBroker:       mqttBroker,
		MQTTPort:         mqttPort,
		MQTTClientID:     "golang-bridge-" + fmt.Sprint(time.Now().Unix()),
		MQTTTopicPattern: "ds_telemetry/#",
		OutputDir:        outputDir,
		OutputFormat:     outputFormat,
		FlushInterval:    time.Duration(flushIntervalSec) * time.Second,
		FileRotation:     time.Duration(fileRotationSec) * time.Second,
	}
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}

func getEnvAsInt(key string, defaultValue int) int {
	valueStr := os.Getenv(key)
	if valueStr == "" {
		return defaultValue
	}
	var value int
	_, err := fmt.Sscanf(valueStr, "%d", &value)
	if err != nil {
		return defaultValue
	}
	return value
}

// NewParquetWriter creates a new parquet writer
func NewParquetWriter(config *Config) *ParquetWriter {
	return &ParquetWriter{
		config:       config,
		lastRotation: time.Now(),
	}
}

// rotateFile closes the current file and creates a new one
func (pw *ParquetWriter) rotateFile() error {
	pw.mu.Lock()
	defer pw.mu.Unlock()

	log.Println("[DEBUG] rotateFile called")

	// Close existing writer
	if pw.writer != nil {
		log.Printf("Closing current parquet file: %s (records: %d)", pw.currentFile, pw.recordCount)
		if err := pw.writer.WriteStop(); err != nil {
			log.Printf("[ERROR] WriteStop failed: %v", err)
		}
		if err := pw.fileWriter.Close(); err != nil {
			log.Printf("[ERROR] Close failed: %v", err)
		}
		pw.writer = nil
		pw.fileWriter = nil
	}

	// Create new file with timestamp
	timestamp := time.Now().Format("20060102_150405")
	filename := fmt.Sprintf("sensor_telemetry_%s.parquet", timestamp)
	filepath := filepath.Join(pw.config.OutputDir, filename)

	log.Printf("[DEBUG] Creating new parquet file: %s", filepath)

	// Ensure output directory exists
	if err := os.MkdirAll(pw.config.OutputDir, 0755); err != nil {
		return fmt.Errorf("failed to create output directory: %w", err)
	}

	// Create new parquet file
	fw, err := local.NewLocalFileWriter(filepath)
	if err != nil {
		return fmt.Errorf("failed to create parquet file: %w", err)
	}
	log.Println("[DEBUG] LocalFileWriter created successfully")

	// Create parquet writer with compression
	pw.fileWriter = fw
	pw.writer, err = writer.NewParquetWriter(fw, new(SensorTelemetry), 4)
	if err != nil {
		fw.Close()
		return fmt.Errorf("failed to create parquet writer: %w", err)
	}
	log.Println("[DEBUG] ParquetWriter created successfully")

	pw.writer.CompressionType = parquet.CompressionCodec_SNAPPY
	pw.currentFile = filepath
	pw.recordCount = 0
	pw.lastRotation = time.Now()

	log.Printf("Created new parquet file: %s", filepath)
	return nil
}

// Write adds a record to the parquet file
func (pw *ParquetWriter) Write(record *SensorTelemetry) error {
	pw.mu.Lock()
	defer pw.mu.Unlock()

	log.Printf("[DEBUG] Write called, writer is nil: %v", pw.writer == nil)

	// Initialize writer if needed
	if pw.writer == nil {
		pw.mu.Unlock()
		log.Println("[DEBUG] Initializing new parquet file...")
		if err := pw.rotateFile(); err != nil {
			log.Printf("[ERROR] Failed to rotate file: %v", err)
			return err
		}
		pw.mu.Lock()
	}

	log.Printf("[DEBUG] About to write record to parquet: room=%s", record.RoomID)

	// Write record
	if err := pw.writer.Write(record); err != nil {
		return fmt.Errorf("failed to write record: %w", err)
	}

	pw.recordCount++
	log.Printf("[DEBUG] Record written successfully, total records: %d", pw.recordCount)
	return nil
}

// Flush flushes the writer buffer
func (pw *ParquetWriter) Flush() error {
	pw.mu.Lock()
	defer pw.mu.Unlock()

	if pw.writer != nil {
		// Parquet writer doesn't have explicit flush, but WriteStop commits data
		// We'll just log the current status
		log.Printf("Current file: %s, Records written: %d", pw.currentFile, pw.recordCount)
	}
	return nil
}

// CheckRotation checks if file rotation is needed
func (pw *ParquetWriter) CheckRotation() error {
	if time.Since(pw.lastRotation) >= pw.config.FileRotation {
		log.Println("File rotation interval reached, rotating file...")
		return pw.rotateFile()
	}
	return nil
}

// Close closes the parquet writer
func (pw *ParquetWriter) Close() error {
	pw.mu.Lock()
	defer pw.mu.Unlock()

	if pw.writer != nil {
		log.Printf("Final close: %s (records: %d)", pw.currentFile, pw.recordCount)
		pw.writer.WriteStop()
		pw.fileWriter.Close()
	}
	return nil
}

// MQTTHandler handles MQTT connections and messages
type MQTTHandler struct {
	config        *Config
	client        mqtt.Client
	parquetWriter *ParquetWriter
	wg            sync.WaitGroup
	errorCount    int64
	successCount  int64
}

func NewMQTTHandler(config *Config) *MQTTHandler {
	return &MQTTHandler{
		config:        config,
		parquetWriter: NewParquetWriter(config),
	}
}

var messagePubHandler mqtt.MessageHandler = func(client mqtt.Client, msg mqtt.Message) {
	log.Printf("Received message on topic: %s", msg.Topic())
}

var connectHandler mqtt.OnConnectHandler = func(client mqtt.Client) {
	log.Println("Connected to MQTT broker")
}

var connectLostHandler mqtt.ConnectionLostHandler = func(client mqtt.Client, err error) {
	log.Printf("Connection lost: %v", err)
}

func (h *MQTTHandler) messageHandler(client mqtt.Client, msg mqtt.Message) {
	log.Printf("[DEBUG] Received message on topic: %s, payload length: %d", msg.Topic(), len(msg.Payload()))
	log.Printf("[DEBUG] Payload: %s", string(msg.Payload()))

	var telemetry SensorTelemetry

	if err := json.Unmarshal(msg.Payload(), &telemetry); err != nil {
		log.Printf("[ERROR] Failed to unmarshal JSON from %s: %v", msg.Topic(), err)
		h.errorCount++
		return
	}

	// Parse RFC3339 timestamp string to Unix nanoseconds
	t, err := time.Parse(time.RFC3339, telemetry.TimestampStr)
	if err != nil {
		log.Printf("[ERROR] Failed to parse timestamp '%s' from %s: %v", telemetry.TimestampStr, msg.Topic(), err)
		h.errorCount++
		return
	}
	telemetry.Timestamp = t.UnixNano()

	log.Printf("[DEBUG] Unmarshaled telemetry: room_id=%s, temp=%.2f, timestamp=%d",
		telemetry.RoomID, telemetry.Temperature, telemetry.Timestamp)

	// Write to parquet
	if err := h.parquetWriter.Write(&telemetry); err != nil {
		log.Printf("[ERROR] Failed to write to parquet: %v", err)
		h.errorCount++
		return
	}

	h.successCount++
	if h.successCount%100 == 0 {
		log.Printf("[STATS] Success: %d, Errors: %d, Success rate: %.2f%%",
			h.successCount, h.errorCount,
			float64(h.successCount)*100/float64(h.successCount+h.errorCount))
	}
	log.Printf("[SUCCESS] Written record for room %s at %d", telemetry.RoomID, telemetry.Timestamp)
}

func (h *MQTTHandler) Connect() error {
	broker := fmt.Sprintf("tcp://%s:%s", h.config.MQTTBroker, h.config.MQTTPort)

	opts := mqtt.NewClientOptions()
	opts.AddBroker(broker)
	opts.SetClientID(h.config.MQTTClientID)
	opts.SetDefaultPublishHandler(messagePubHandler)
	opts.OnConnect = connectHandler
	opts.OnConnectionLost = connectLostHandler
	opts.SetAutoReconnect(true)
	opts.SetCleanSession(true)

	h.client = mqtt.NewClient(opts)

	log.Printf("Connecting to MQTT broker at %s...", broker)
	if token := h.client.Connect(); token.Wait() && token.Error() != nil {
		return fmt.Errorf("failed to connect to MQTT broker: %w", token.Error())
	}

	log.Printf("Subscribing to topic: %s", h.config.MQTTTopicPattern)
	if token := h.client.Subscribe(h.config.MQTTTopicPattern, 1, h.messageHandler); token.Wait() && token.Error() != nil {
		return fmt.Errorf("failed to subscribe to topic: %w", token.Error())
	}

	log.Println("Successfully subscribed to downsampled topics")
	return nil
}

func (h *MQTTHandler) StartPeriodicTasks() {
	// Periodic flush
	h.wg.Add(1)
	go func() {
		defer h.wg.Done()
		ticker := time.NewTicker(h.config.FlushInterval)
		defer ticker.Stop()

		for range ticker.C {
			if err := h.parquetWriter.Flush(); err != nil {
				log.Printf("Error flushing writer: %v", err)
			}
			if err := h.parquetWriter.CheckRotation(); err != nil {
				log.Printf("Error checking rotation: %v", err)
			}
		}
	}()
}

func (h *MQTTHandler) Close() {
	log.Println("Closing MQTT handler...")

	if h.client != nil && h.client.IsConnected() {
		h.client.Disconnect(250)
	}

	if h.parquetWriter != nil {
		h.parquetWriter.Close()
	}

	h.wg.Wait()
	log.Println("MQTT handler closed")
}

func main() {
	log.Println("Starting Parquet Golang Bridge...")

	config := loadConfig()
	log.Printf("Configuration: Broker=%s:%s, OutputDir=%s, Format=%s",
		config.MQTTBroker, config.MQTTPort, config.OutputDir, config.OutputFormat)

	handler := NewMQTTHandler(config)

	if err := handler.Connect(); err != nil {
		log.Fatalf("Failed to connect: %v", err)
	}

	// Start periodic tasks
	handler.StartPeriodicTasks()

	// Wait for interrupt signal
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	log.Println("Parquet Golang Bridge is running. Press Ctrl+C to exit.")
	<-sigChan

	log.Println("Shutdown signal received...")
	handler.Close()
	log.Println("Shutdown complete")
}
