package main

import (
	"encoding/json"
	"fmt"
	"log"
	"net"
	"os"
	"os/signal"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/alexbeltran/gobacnet"
	"github.com/alexbeltran/gobacnet/property"
	"github.com/alexbeltran/gobacnet/types"
	mqtt "github.com/eclipse/paho.mqtt.golang"
	"github.com/goburrow/modbus"
	"gopkg.in/yaml.v3"
)

// Configuration structures
type SensorConfig struct {
	ID             string `yaml:"id"`
	Type           string `yaml:"type"`
	Protocol       string `yaml:"protocol"`
	Address        string `yaml:"address"`
	ObjectID       int    `yaml:"object_id,omitempty"`
	Register       int    `yaml:"register,omitempty"`
	Unit           string `yaml:"unit"`
	PollIntervalMs int    `yaml:"poll_interval_ms"`
}

type RoomConfig struct {
	ID      string   `yaml:"id"`
	Name    string   `yaml:"name"`
	Floor   int      `yaml:"floor"`
	Zone    string   `yaml:"zone"`
	Sensors []string `yaml:"sensors"`
}

type SensorsFile struct {
	Sensors []SensorConfig `yaml:"sensors"`
}

type RoomsFile struct {
	Rooms []RoomConfig `yaml:"rooms"`
}

// Sensor reading with metadata
type SensorReading struct {
	SensorID  string    `json:"sensor_id"`
	RoomID    string    `json:"room_id"`
	Type      string    `json:"type"`
	Value     float64   `json:"value"`
	Unit      string    `json:"unit"`
	Timestamp time.Time `json:"timestamp"`
	Status    string    `json:"status"` // "ok", "error", "stale"
}

// Room telemetry aggregated from all sensors
type RoomTelemetry struct {
	RoomID          string  `json:"room_id"`
	Temperature     float64 `json:"temperature"`
	Humidity        float64 `json:"humidity"`
	CO2PPM          float64 `json:"co2_ppm"`
	LightLux        float64 `json:"light_lux"`
	OccupancyCount  int32   `json:"occupancy_count"`
	MotionDetected  bool    `json:"motion_detected"`
	EnergyKWH       float64 `json:"energy_kwh"`
	AirQualityIndex float64 `json:"air_quality_index"`
	Timestamp       string  `json:"timestamp"`
}

// Gateway manages sensor polling and MQTT publishing
type Gateway struct {
	sensors           map[string]*SensorConfig
	rooms             map[string]*RoomConfig
	sensorToRoom      map[string]string
	lastReadings      map[string]*SensorReading
	readingsMutex     sync.RWMutex
	mqttClient        mqtt.Client
	bacnetClient      *gobacnet.Client
	bacnetDevices     map[string]types.Device
	bacnetDeviceMu    sync.RWMutex
	bacnetMu          sync.Mutex
	telemetryInterval time.Duration
	modbusHandler     *modbus.TCPClientHandler
	wg                sync.WaitGroup
	shutdown          chan struct{}
}

func NewGateway(sensorsConfigPath, roomsConfigPath, mqttBroker, bacnetInterface, modbusAddr string) (*Gateway, error) {
	gw := &Gateway{
		sensors:       make(map[string]*SensorConfig),
		rooms:         make(map[string]*RoomConfig),
		sensorToRoom:  make(map[string]string),
		lastReadings:  make(map[string]*SensorReading),
		bacnetDevices: make(map[string]types.Device),
		shutdown:      make(chan struct{}),
	}

	// Load configuration
	if err := gw.loadConfig(sensorsConfigPath, roomsConfigPath); err != nil {
		return nil, err
	}

	gw.configureTelemetryInterval()

	// Setup BACnet client
	if err := gw.setupBACnet(bacnetInterface); err != nil {
		return nil, err
	}

	// Setup Modbus client
	if err := gw.setupModbus(modbusAddr); err != nil {
		return nil, err
	}

	// Connect to MQTT
	if err := gw.connectMQTT(mqttBroker); err != nil {
		return nil, err
	}

	return gw, nil
}

func (gw *Gateway) loadConfig(sensorsPath, roomsPath string) error {
	log.Println("Loading configuration...")

	// Load rooms
	roomsData, err := os.ReadFile(roomsPath)
	if err != nil {
		return fmt.Errorf("failed to read rooms config: %w", err)
	}

	var roomsFile RoomsFile
	if err := yaml.Unmarshal(roomsData, &roomsFile); err != nil {
		return fmt.Errorf("failed to parse rooms config: %w", err)
	}

	for i := range roomsFile.Rooms {
		room := &roomsFile.Rooms[i]
		gw.rooms[room.ID] = room
		for _, sensorID := range room.Sensors {
			gw.sensorToRoom[sensorID] = room.ID
		}
	}

	// Load sensors
	sensorsData, err := os.ReadFile(sensorsPath)
	if err != nil {
		return fmt.Errorf("failed to read sensors config: %w", err)
	}

	var sensorsFile SensorsFile
	if err := yaml.Unmarshal(sensorsData, &sensorsFile); err != nil {
		return fmt.Errorf("failed to parse sensors config: %w", err)
	}

	for i := range sensorsFile.Sensors {
		sensor := &sensorsFile.Sensors[i]
		gw.sensors[sensor.ID] = sensor
	}

	log.Printf("Loaded %d sensors for %d rooms", len(gw.sensors), len(gw.rooms))
	return nil
}

func (gw *Gateway) configureTelemetryInterval() {
	const defaultInterval = time.Second
	var minInterval int
	for _, sensor := range gw.sensors {
		if sensor.PollIntervalMs <= 0 {
			continue
		}
		if minInterval == 0 || sensor.PollIntervalMs < minInterval {
			minInterval = sensor.PollIntervalMs
		}
	}
	if minInterval == 0 {
		gw.telemetryInterval = defaultInterval
	} else {
		gw.telemetryInterval = time.Duration(minInterval) * time.Millisecond
	}
	log.Printf("Telemetry publish interval set to %v", gw.telemetryInterval)
}

func (gw *Gateway) setupBACnet(interfaceName string) error {
	log.Printf("Setting up BACnet client on interface %s", interfaceName)

	client, err := gobacnet.NewClient(interfaceName, 0)
	if err != nil {
		return fmt.Errorf("failed to create BACnet client: %w", err)
	}

	gw.bacnetClient = client
	log.Println("BACnet client ready")
	return nil
}

func (gw *Gateway) setupModbus(address string) error {
	log.Printf("Setting up Modbus client to %s", address)

	// Create Modbus TCP handler with connection pooling
	handler := modbus.NewTCPClientHandler(address)
	handler.Timeout = 2 * time.Second
	handler.IdleTimeout = 60 * time.Second

	if err := handler.Connect(); err != nil {
		return fmt.Errorf("failed to connect Modbus: %w", err)
	}

	gw.modbusHandler = handler
	log.Println("Modbus client ready")
	return nil
}

func (gw *Gateway) connectMQTT(broker string) error {
	opts := mqtt.NewClientOptions()
	opts.AddBroker(broker)
	opts.SetClientID("golang-gateway")
	opts.SetAutoReconnect(true)
	opts.SetConnectRetry(true)

	gw.mqttClient = mqtt.NewClient(opts)
	if token := gw.mqttClient.Connect(); token.Wait() && token.Error() != nil {
		return fmt.Errorf("failed to connect to MQTT: %w", token.Error())
	}

	log.Printf("Connected to MQTT broker: %s", broker)
	return nil
}

func (gw *Gateway) Start() {
	log.Println("Starting gateway...")

	// Start sensor pollers
	for sensorID, sensorConfig := range gw.sensors {
		gw.wg.Add(1)
		go gw.pollSensor(sensorID, sensorConfig)
	}

	// Start room aggregator and publisher
	gw.wg.Add(1)
	go gw.publishRoomData()

	log.Println("Gateway started successfully")
}

func (gw *Gateway) pollSensor(sensorID string, config *SensorConfig) {
	defer gw.wg.Done()

	ticker := time.NewTicker(time.Duration(config.PollIntervalMs) * time.Millisecond)
	defer ticker.Stop()

	roomID := gw.sensorToRoom[sensorID]

	for {
		select {
		case <-gw.shutdown:
			return
		case <-ticker.C:
			var value float64
			var err error

			// Read from protocol
			if config.Protocol == "bacnet" {
				value, err = gw.readBACnet(config)
			} else if config.Protocol == "modbus" {
				value, err = gw.readModbus(config.Register)
			} else {
				log.Printf("[WARN] Unknown protocol for sensor %s: %s", sensorID, config.Protocol)
				continue
			}

			// Create reading
			reading := &SensorReading{
				SensorID:  sensorID,
				RoomID:    roomID,
				Type:      config.Type,
				Value:     value,
				Unit:      config.Unit,
				Timestamp: time.Now(),
				Status:    "ok",
			}

			if err != nil {
				reading.Status = "error"
				log.Printf("[ERROR] Failed to read sensor %s: %v", sensorID, err)
			}

			// Store reading
			gw.readingsMutex.Lock()
			gw.lastReadings[sensorID] = reading
			gw.readingsMutex.Unlock()

			if err == nil {
				log.Printf("[DEBUG] %s: %.2f %s", sensorID, value, config.Unit)
			}
		}
	}
}

func (gw *Gateway) readBACnet(sensor *SensorConfig) (float64, error) {
	if gw.bacnetClient == nil {
		return 0, fmt.Errorf("BACnet client not initialized")
	}

	device, err := gw.getBACnetDevice(sensor.Address)
	if err != nil {
		return 0, err
	}

	rp := types.ReadPropertyData{
		Object: types.Object{
			ID: types.ObjectID{
				Type:     types.AnalogValue,
				Instance: types.ObjectInstance(sensor.ObjectID),
			},
			Properties: []types.Property{
				{
					Type:       property.PresentValue,
					ArrayIndex: gobacnet.ArrayAll,
				},
			},
		},
	}

	gw.bacnetMu.Lock()
	resp, err := gw.bacnetClient.ReadProperty(device, rp)
	gw.bacnetMu.Unlock()
	if err != nil {
		return 0, fmt.Errorf("BACnet read error: %w", err)
	}

	if len(resp.Object.Properties) == 0 {
		return 0, fmt.Errorf("BACnet response contained no properties")
	}

	return parseBACnetNumeric(resp.Object.Properties[0].Data)
}

func (gw *Gateway) getBACnetDevice(address string) (types.Device, error) {
	normalized := normalizeBACnetAddress(address)
	gw.bacnetDeviceMu.RLock()
	dev, found := gw.bacnetDevices[normalized]
	gw.bacnetDeviceMu.RUnlock()
	if found {
		return dev, nil
	}

	udpAddr, err := net.ResolveUDPAddr("udp", normalized)
	if err != nil {
		return types.Device{}, fmt.Errorf("invalid BACnet address %s: %w", normalized, err)
	}
	dev = types.Device{
		Addr: types.UDPToAddress(udpAddr),
	}
	gw.bacnetDeviceMu.Lock()
	gw.bacnetDevices[normalized] = dev
	gw.bacnetDeviceMu.Unlock()
	return dev, nil
}

func normalizeBACnetAddress(address string) string {
	addr := strings.TrimSpace(address)
	if addr == "" {
		return fmt.Sprintf("127.0.0.1:%d", gobacnet.DefaultPort)
	}
	if !strings.Contains(addr, ":") {
		return fmt.Sprintf("%s:%d", addr, gobacnet.DefaultPort)
	}
	return addr
}

func parseBACnetNumeric(value interface{}) (float64, error) {
	switch v := value.(type) {
	case float64:
		return v, nil
	case float32:
		return float64(v), nil
	case int:
		return float64(v), nil
	case int32:
		return float64(v), nil
	case int64:
		return float64(v), nil
	case uint32:
		return float64(v), nil
	case uint64:
		return float64(v), nil
	default:
		return 0, fmt.Errorf("unsupported BACnet value type %T", value)
	}
}

func (gw *Gateway) readModbus(register int) (float64, error) {
	// Create Modbus client
	client := modbus.NewClient(gw.modbusHandler)

	// Read holding register
	results, err := client.ReadHoldingRegisters(uint16(register), 1)
	if err != nil {
		return 0, fmt.Errorf("Modbus read error: %w", err)
	}

	if len(results) < 2 {
		return 0, fmt.Errorf("insufficient data returned")
	}

	// Convert bytes to uint16, then to float (scaled by 100)
	rawValue := uint16(results[0])<<8 | uint16(results[1])
	floatValue := float64(rawValue) / 100.0

	return floatValue, nil
}

func (gw *Gateway) publishRoomData() {
	defer gw.wg.Done()

	interval := gw.telemetryInterval
	if interval <= 0 {
		interval = time.Second
	}
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		select {
		case <-gw.shutdown:
			return
		case <-ticker.C:
			// Aggregate and publish for each room
			for roomID := range gw.rooms {
				telemetry := gw.aggregateRoomData(roomID)
				if telemetry != nil {
					gw.publishTelemetry(roomID, telemetry)
				}
			}
		}
	}
}

func (gw *Gateway) aggregateRoomData(roomID string) *RoomTelemetry {
	gw.readingsMutex.RLock()
	defer gw.readingsMutex.RUnlock()

	room := gw.rooms[roomID]
	telemetry := &RoomTelemetry{
		RoomID:    roomID,
		Timestamp: time.Now().Format(time.RFC3339),
	}

	// Aggregate sensor readings for this room
	for _, sensorID := range room.Sensors {
		reading, exists := gw.lastReadings[sensorID]
		if !exists || reading.Status != "ok" {
			continue
		}

		// Map sensor types to telemetry fields
		switch reading.Type {
		case "temperature":
			telemetry.Temperature = reading.Value
		case "humidity":
			telemetry.Humidity = reading.Value
		case "co2":
			telemetry.CO2PPM = reading.Value
		case "air_quality":
			telemetry.AirQualityIndex = reading.Value
		case "light":
			telemetry.LightLux = reading.Value
		case "energy":
			telemetry.EnergyKWH = reading.Value
		case "motion":
			telemetry.MotionDetected = reading.Value >= 0.5
		case "occupancy":
			telemetry.OccupancyCount = int32(reading.Value)
		}
	}

	return telemetry
}

func (gw *Gateway) publishTelemetry(roomID string, telemetry *RoomTelemetry) {
	topic := fmt.Sprintf("telemetry/%s", roomID)

	payload, err := json.Marshal(telemetry)
	if err != nil {
		log.Printf("[ERROR] Failed to marshal telemetry for room %s: %v", roomID, err)
		return
	}

	token := gw.mqttClient.Publish(topic, 0, false, payload)
	token.Wait()

	if token.Error() != nil {
		log.Printf("[ERROR] Failed to publish to %s: %v", topic, token.Error())
	} else {
		log.Printf("[MQTT] Published to %s", topic)
	}
}

func (gw *Gateway) Stop() {
	log.Println("Shutting down gateway...")
	close(gw.shutdown)
	gw.wg.Wait()

	if gw.mqttClient != nil && gw.mqttClient.IsConnected() {
		gw.mqttClient.Disconnect(250)
	}

	if gw.bacnetClient != nil {
		gw.bacnetClient.Close()
	}

	if gw.modbusHandler != nil {
		gw.modbusHandler.Close()
	}

	log.Println("Gateway stopped")
}

func main() {
	log.Println("Starting Golang Gateway with Real BACnet/Modbus")

	// Configuration
	sensorsConfig := getEnv("SENSORS_CONFIG", "/app/config/sensors.yaml")
	roomsConfig := getEnv("ROOMS_CONFIG", "/app/config/rooms.yaml")
	mqttBroker := getEnv("MQTT_BROKER", "tcp://nanomq:1883")
	bacnetInterface := getEnv("BACNET_INTERFACE", "")
	if bacnetInterface == "" {
		bacnetInterface = getEnv("BACNET_ADDRESS", "eth0")
	}
	modbusAddr := getEnv("MODBUS_ADDRESS", "sensor-simulator:5020")

	// Create gateway
	gateway, err := NewGateway(sensorsConfig, roomsConfig, mqttBroker, bacnetInterface, modbusAddr)
	if err != nil {
		log.Fatalf("Failed to create gateway: %v", err)
	}

	// Start gateway
	gateway.Start()

	// Wait for interrupt
	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, syscall.SIGINT, syscall.SIGTERM)
	<-sigChan

	// Graceful shutdown
	gateway.Stop()
}

func getEnv(key, defaultValue string) string {
	if value := os.Getenv(key); value != "" {
		return value
	}
	return defaultValue
}
