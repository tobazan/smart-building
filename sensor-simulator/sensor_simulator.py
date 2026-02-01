"""
Smart Building Sensor Simulator
Generates telemetry data for 8 different rooms and publishes to MQTT broker.
Publishes every 0.5 seconds (2 messages/sec per room = 16 msgs/sec total).
"""
import os
import time
import json
import logging
import signal
import sys
from typing import List
import paho.mqtt.client as mqtt
from room_profiles import get_all_room_profiles, RoomProfile

# Configuration
MQTT_BROKER = os.getenv('MQTT_BROKER', 'nanomq')
MQTT_PORT = int(os.getenv('MQTT_PORT', 1883))
MQTT_TOPIC_PREFIX = os.getenv('MQTT_TOPIC_PREFIX', 'telemetry')
PUBLISH_INTERVAL = float(os.getenv('PUBLISH_INTERVAL', 0.5))  # seconds

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global flag for graceful shutdown
shutdown_flag = False


def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    global shutdown_flag
    logger.info("Shutdown signal received. Stopping sensor simulation...")
    shutdown_flag = True


class SensorSimulator:
    """Main sensor simulator class"""
    
    def __init__(self, broker: str, port: int, topic_prefix: str):
        self.broker = broker
        self.port = port
        self.topic_prefix = topic_prefix
        self.client = None
        self.rooms: List[RoomProfile] = []
        self.connected = False
        self.message_count = 0
        
    def on_connect(self, client, userdata, flags, rc):
        """MQTT connection callback"""
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
        else:
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
            self.connected = False
    
    def on_disconnect(self, client, userdata, rc):
        """MQTT disconnection callback"""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker. Return code: {rc}")
        else:
            logger.info("Disconnected from MQTT broker")
    
    def on_publish(self, client, userdata, mid):
        """MQTT publish callback"""
        # Optional: track published messages
        pass
    
    def connect_mqtt(self):
        """Establish connection to MQTT broker"""
        try:
            self.client = mqtt.Client(client_id="sensor-simulator", clean_session=True)
            self.client.on_connect = self.on_connect
            self.client.on_disconnect = self.on_disconnect
            self.client.on_publish = self.on_publish
            
            logger.info(f"Connecting to MQTT broker at {self.broker}:{self.port}...")
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 10
            start_time = time.time()
            while not self.connected and (time.time() - start_time) < timeout:
                time.sleep(0.1)
            
            if not self.connected:
                raise ConnectionError("Failed to connect to MQTT broker within timeout")
            
            return True
            
        except Exception as e:
            logger.error(f"Error connecting to MQTT broker: {e}")
            return False
    
    def disconnect_mqtt(self):
        """Disconnect from MQTT broker"""
        if self.client:
            self.client.loop_stop()
            self.client.disconnect()
            logger.info("Disconnected from MQTT broker")
    
    def initialize_rooms(self):
        """Initialize all room profiles"""
        self.rooms = get_all_room_profiles()
        logger.info(f"Initialized {len(self.rooms)} room profiles:")
        for room in self.rooms:
            logger.info(f"  - {room.room_id}: {room.name} ({room.room_type})")
    
    def publish_telemetry(self, room: RoomProfile):
        """Generate and publish telemetry data for a room"""
        try:
            # Get telemetry data from room profile
            telemetry = room.get_telemetry()
            
            # Convert to JSON
            payload = json.dumps(telemetry)
            
            # Publish to MQTT topic
            topic = f"{self.topic_prefix}/{room.room_id}"
            result = self.client.publish(topic, payload, qos=1)
            
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.message_count += 1
                if self.message_count % 100 == 0:  # Log every 100 messages
                    logger.info(f"Published {self.message_count} messages. Latest: {room.room_id}")
            else:
                logger.warning(f"Failed to publish to {topic}. Return code: {result.rc}")
                
        except Exception as e:
            logger.error(f"Error publishing telemetry for {room.room_id}: {e}")
    
    def run(self):
        """Main simulation loop"""
        logger.info("Starting sensor simulation...")
        logger.info(f"Publishing interval: {PUBLISH_INTERVAL} seconds")
        logger.info(f"Expected rate: {len(self.rooms) / PUBLISH_INTERVAL:.1f} messages/second")
        
        start_time = time.time()
        
        try:
            while not shutdown_flag:
                iteration_start = time.time()
                
                # Publish telemetry for all rooms
                for room in self.rooms:
                    if shutdown_flag:
                        break
                    self.publish_telemetry(room)
                
                # Calculate sleep time to maintain interval
                elapsed = time.time() - iteration_start
                sleep_time = max(0, PUBLISH_INTERVAL - elapsed)
                
                if sleep_time > 0:
                    time.sleep(sleep_time)
                else:
                    logger.warning(f"Iteration took {elapsed:.3f}s, longer than interval {PUBLISH_INTERVAL}s")
                
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
        except Exception as e:
            logger.error(f"Error in simulation loop: {e}", exc_info=True)
        finally:
            # Print statistics
            total_time = time.time() - start_time
            if total_time > 0:
                avg_rate = self.message_count / total_time
                logger.info(f"Simulation statistics:")
                logger.info(f"  Total messages: {self.message_count}")
                logger.info(f"  Total time: {total_time:.2f} seconds")
                logger.info(f"  Average rate: {avg_rate:.2f} messages/second")


def main():
    """Main entry point"""
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    logger.info("="*60)
    logger.info("Smart Building Sensor Simulator")
    logger.info("="*60)
    
    # Create simulator instance
    simulator = SensorSimulator(
        broker=MQTT_BROKER,
        port=MQTT_PORT,
        topic_prefix=MQTT_TOPIC_PREFIX
    )
    
    # Initialize room profiles
    simulator.initialize_rooms()
    
    # Connect to MQTT broker
    if not simulator.connect_mqtt():
        logger.error("Failed to connect to MQTT broker. Exiting.")
        sys.exit(1)
    
    # Run simulation
    try:
        simulator.run()
    finally:
        # Cleanup
        simulator.disconnect_mqtt()
        logger.info("Sensor simulator stopped")


if __name__ == "__main__":
    main()
