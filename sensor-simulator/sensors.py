"""
Sensor base classes and protocol implementations for building automation simulation.
"""
import random
import time
import struct
from abc import ABC, abstractmethod
from typing import Dict, Any


class Sensor(ABC):
    """Base class for all sensor types."""
    
    def __init__(self, sensor_id: str, room_id: str):
        self.sensor_id = sensor_id
        self.room_id = room_id
        self.last_value = None
        self.last_update = time.time()
        
    @abstractmethod
    def read(self) -> float:
        """Read current sensor value."""
        pass
    
    def get_value(self) -> float:
        """Get current value with timestamp update."""
        self.last_value = self.read()
        self.last_update = time.time()
        return self.last_value


class TemperatureSensor(Sensor):
    """Temperature sensor (BACnet) - simulates realistic HVAC behavior."""
    
    def __init__(self, sensor_id: str, room_id: str, base_temp: float = 21.0):
        super().__init__(sensor_id, room_id)
        self.base_temp = base_temp
        self.current_temp = base_temp
        self.drift_rate = random.uniform(-0.01, 0.01)
        
    def read(self) -> float:
        """Simulate gradual temperature changes."""
        # Slow drift + small random fluctuation
        self.current_temp += self.drift_rate + random.uniform(-0.1, 0.1)
        
        # Keep within realistic bounds
        self.current_temp = max(18, min(28, self.current_temp))
        
        # Occasionally reset drift direction
        if random.random() < 0.01:
            self.drift_rate = random.uniform(-0.01, 0.01)
            
        return round(self.current_temp, 2)


class HumiditySensor(Sensor):
    """Humidity sensor (BACnet) - correlates with temperature."""
    
    def __init__(self, sensor_id: str, room_id: str, base_humidity: float = 45.0):
        super().__init__(sensor_id, room_id)
        self.base_humidity = base_humidity
        self.current_humidity = base_humidity
        
    def read(self) -> float:
        """Simulate humidity fluctuations."""
        self.current_humidity += random.uniform(-0.5, 0.5)
        self.current_humidity = max(30, min(70, self.current_humidity))
        return round(self.current_humidity, 2)


class CO2Sensor(Sensor):
    """CO2 sensor (BACnet) - varies with occupancy."""
    
    def __init__(self, sensor_id: str, room_id: str, base_co2: float = 450.0):
        super().__init__(sensor_id, room_id)
        self.base_co2 = base_co2
        self.current_co2 = base_co2
        self.occupancy_multiplier = 1.0
        
    def set_occupancy(self, count: int):
        """Adjust CO2 based on occupancy."""
        self.occupancy_multiplier = 1.0 + (count * 0.1)
        
    def read(self) -> float:
        """Simulate CO2 levels."""
        target = self.base_co2 * self.occupancy_multiplier
        self.current_co2 += (target - self.current_co2) * 0.1 + random.uniform(-10, 10)
        self.current_co2 = max(400, min(2000, self.current_co2))
        return round(self.current_co2, 2)


class AirQualitySensor(Sensor):
    """Air quality index sensor (BACnet)."""
    
    def __init__(self, sensor_id: str, room_id: str):
        super().__init__(sensor_id, room_id)
        self.current_aqi = random.uniform(50, 100)
        
    def read(self) -> float:
        """Simulate air quality index."""
        self.current_aqi += random.uniform(-2, 2)
        self.current_aqi = max(0, min(100, self.current_aqi))
        return round(self.current_aqi, 2)


class LightSensor(Sensor):
    """Light level sensor (Modbus) - binary on/off states."""
    
    def __init__(self, sensor_id: str, room_id: str):
        super().__init__(sensor_id, room_id)
        self.is_on = random.choice([True, False])
        self.lux_level = 500 if self.is_on else 0
        
    def read(self) -> float:
        """Simulate light levels."""
        # Occasional on/off transitions
        if random.random() < 0.02:
            self.is_on = not self.is_on
            
        if self.is_on:
            self.lux_level = random.uniform(300, 600)
        else:
            self.lux_level = random.uniform(0, 50)
            
        return round(self.lux_level, 2)


class EnergySensor(Sensor):
    """Energy meter (Modbus) - cumulative consumption."""
    
    def __init__(self, sensor_id: str, room_id: str):
        super().__init__(sensor_id, room_id)
        self.cumulative_kwh = random.uniform(0, 5)
        self.consumption_rate = random.uniform(0.001, 0.005)
        
    def read(self) -> float:
        """Simulate energy consumption."""
        self.cumulative_kwh += self.consumption_rate
        return round(self.cumulative_kwh, 5)


class MotionSensor(Sensor):
    """Motion detector (Modbus) - binary."""
    
    def __init__(self, sensor_id: str, room_id: str):
        super().__init__(sensor_id, room_id)
        self.motion_detected = False
        
    def read(self) -> float:
        """Simulate motion detection."""
        # Random motion events
        if random.random() < 0.1:
            self.motion_detected = not self.motion_detected
        return 1.0 if self.motion_detected else 0.0


class OccupancySensor(Sensor):
    """Occupancy counter (Modbus)."""
    
    def __init__(self, sensor_id: str, room_id: str, max_occupancy: int = 15):
        super().__init__(sensor_id, room_id)
        self.max_occupancy = max_occupancy
        self.current_count = random.randint(0, max_occupancy)
        
    def read(self) -> float:
        """Simulate occupancy count."""
        # Gradual changes in occupancy
        change = random.choice([-1, 0, 0, 0, 1])
        self.current_count = max(0, min(self.max_occupancy, self.current_count + change))
        return float(self.current_count)


class BACnetServer:
    """Lightweight BACnet simulation - simple UDP request/response."""
    
    def __init__(self, sensors: Dict[int, Sensor]):
        """
        Args:
            sensors: Dictionary mapping object_id to Sensor instance
        """
        self.sensors = sensors
        
    def handle_read_request(self, object_id: int) -> bytes:
        """
        Handle read property request for an object.
        Returns: 8-byte response with float value
        """
        if object_id in self.sensors:
            value = self.sensors[object_id].get_value()
            # Simple protocol: 4 bytes object_id + 4 bytes float value
            return struct.pack('!If', object_id, value)
        else:
            # Return error: object_id + NaN
            return struct.pack('!If', object_id, float('nan'))


class ModbusServer:
    """Lightweight Modbus TCP simulation - simple register reads."""
    
    def __init__(self, sensors: Dict[int, Sensor]):
        """
        Args:
            sensors: Dictionary mapping register address to Sensor instance
        """
        self.sensors = sensors
        
    def handle_read_request(self, register: int) -> bytes:
        """
        Handle read holding register request.
        Returns: 6-byte response with register and float value
        """
        if register in self.sensors:
            value = self.sensors[register].get_value()
            # Simple protocol: 2 bytes register + 4 bytes float value
            return struct.pack('!Hf', register, value)
        else:
            # Return error
            return struct.pack('!Hf', register, float('nan'))
