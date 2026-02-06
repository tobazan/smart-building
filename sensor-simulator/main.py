"""
Real BACnet and Modbus server implementation with bacpypes3 and pymodbus.
"""
import asyncio
import logging
from argparse import Namespace
from pathlib import Path
from typing import Dict

import yaml

from bacpypes3.app import Application
from bacpypes3.local.analog import AnalogValueObject
from bacpypes3.primitivedata import Real

from pymodbus.server import StartAsyncTcpServer
from pymodbus.datastore import ModbusSlaveContext, ModbusServerContext
from pymodbus.datastore import ModbusSequentialDataBlock

from sensors import (
    TemperatureSensor, HumiditySensor, CO2Sensor, AirQualitySensor,
    LightSensor, EnergySensor, MotionSensor, OccupancySensor
)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class BACnetSimulator:
    """BACnet/IP server with real protocol implementation."""
    
    def __init__(self, sensors_map: Dict[int, object]):
        """
        Args:
            sensors_map: Dictionary mapping object_id to Sensor instance
        """
        self.sensors_map = sensors_map
        self.bacnet_objects = {}
        self.app = None
        
    async def setup(self):
        """Initialize BACnet application and objects."""
        # Build a minimal argparse namespace expected by bacpypes3
        args = Namespace(
            name="SensorSimulator",
            instance=47808,
            network=None,
            address="0.0.0.0:47808",
            vendoridentifier=999,
            foreign=None,
            ttl=30,
            bbmd=None,
        )

        self.app = Application.from_args(args)
        
        # Create BACnet objects for each sensor
        for object_id, sensor in self.sensors_map.items():
            # Create Analog Value object
            avo = AnalogValueObject(
                objectIdentifier=('analogValue', object_id),
                objectName=f'sensor_{object_id}',
                presentValue=Real(sensor.get_value()),
                statusFlags=[0, 0, 0, 0],
                eventState='normal',
                outOfService=False,
                units='noUnits'
            )
            
            # Add to application
            self.app.add_object(avo)
            self.bacnet_objects[object_id] = (avo, sensor)
            
        logger.info(f"BACnet server initialized with {len(self.bacnet_objects)} objects on port 47808")
        
    async def update_loop(self):
        """Continuously update sensor values."""
        while True:
            try:
                for object_id, (avo, sensor) in self.bacnet_objects.items():
                    new_value = sensor.get_value()
                    avo.presentValue = Real(new_value)
                    
                await asyncio.sleep(0.1)  # Update 10 times per second
            except Exception as e:
                logger.error(f"BACnet update error: {e}")
                await asyncio.sleep(1)


class ModbusSimulator:
    """Modbus TCP server with real protocol implementation."""
    
    def __init__(self, sensors_map: Dict[int, object], port: int = 5020):
        """
        Args:
            sensors_map: Dictionary mapping register address to Sensor instance
            port: Modbus TCP port
        """
        self.sensors_map = sensors_map
        self.port = port
        self.datastore = None
        
    async def setup(self):
        """Initialize Modbus datastore."""
        # Create datastore with 1000 holding registers
        # Initialize all to 0
        block = ModbusSequentialDataBlock(0, [0] * 1000)
        store = ModbusSlaveContext(
            di=ModbusSequentialDataBlock(0, [0] * 1000),
            co=ModbusSequentialDataBlock(0, [0] * 1000),
            hr=block,  # Holding registers for our sensors
            ir=ModbusSequentialDataBlock(0, [0] * 1000)
        )
        self.datastore = ModbusServerContext(slaves=store, single=True)
        
        logger.info(f"Modbus TCP server initialized with {len(self.sensors_map)} registers on port {self.port}")
        
    async def update_loop(self):
        """Continuously update register values from sensors."""
        while True:
            try:
                for register, sensor in self.sensors_map.items():
                    value = sensor.get_value()
                    # Convert float to int (scaled by 100 for precision)
                    scaled_value = int(value * 100)
                    # Write to holding register (function code 3)
                    self.datastore[0].setValues(3, register, [scaled_value])
                    
                await asyncio.sleep(0.1)  # Update 10 times per second
            except Exception as e:
                logger.error(f"Modbus update error: {e}")
                await asyncio.sleep(1)
                
    async def run_server(self):
        """Start Modbus TCP server."""
        await self.setup()
        
        # Start update loop in background
        asyncio.create_task(self.update_loop())
        
        # Start Modbus server
        await StartAsyncTcpServer(
            context=self.datastore,
            address=("0.0.0.0", self.port)
        )


class SimulatorCoordinator:
    """Coordinates BACnet and Modbus servers."""
    
    def __init__(self, sensors_config_path: str, rooms_config_path: str):
        self.sensors = {}
        self.rooms = {}
        self.bacnet_sensors = {}  # object_id -> Sensor
        self.modbus_sensors = {}  # register -> Sensor
        
        self._load_config(sensors_config_path, rooms_config_path)
        
        self.bacnet_sim = BACnetSimulator(self.bacnet_sensors)
        self.modbus_sim = ModbusSimulator(self.modbus_sensors)
        
    def _load_config(self, sensors_path: str, rooms_path: str):
        """Load sensors and rooms configuration."""
        logger.info("Loading configuration...")
        
        # Load rooms
        with open(rooms_path, 'r') as f:
            rooms_data = yaml.safe_load(f)
            self.rooms = {room['id']: room for room in rooms_data['rooms']}
            
        # Map sensors to rooms
        sensor_to_room = {}
        for room in self.rooms.values():
            for sensor_id in room['sensors']:
                sensor_to_room[sensor_id] = room['id']
                
        # Load sensors
        with open(sensors_path, 'r') as f:
            sensors_data = yaml.safe_load(f)
            
        for sensor_config in sensors_data['sensors']:
            sensor_id = sensor_config['id']
            sensor_type = sensor_config['type']
            protocol = sensor_config['protocol']
            room_id = sensor_to_room.get(sensor_id, '00')
            
            # Create sensor instance
            sensor = self._create_sensor(sensor_type, sensor_id, room_id)
            self.sensors[sensor_id] = sensor
            
            # Map to protocol
            if protocol == 'bacnet':
                object_id = sensor_config['object_id']
                self.bacnet_sensors[object_id] = sensor
            elif protocol == 'modbus':
                register = sensor_config['register']
                self.modbus_sensors[register] = sensor
                
        logger.info(f"Loaded {len(self.sensors)} sensors: "
                   f"{len(self.bacnet_sensors)} BACnet, {len(self.modbus_sensors)} Modbus")
        
    def _create_sensor(self, sensor_type: str, sensor_id: str, room_id: str):
        """Factory method to create sensor instances."""
        if sensor_type == 'temperature':
            return TemperatureSensor(sensor_id, room_id)
        elif sensor_type == 'humidity':
            return HumiditySensor(sensor_id, room_id)
        elif sensor_type == 'co2':
            return CO2Sensor(sensor_id, room_id)
        elif sensor_type == 'air_quality':
            return AirQualitySensor(sensor_id, room_id)
        elif sensor_type == 'light':
            return LightSensor(sensor_id, room_id)
        elif sensor_type == 'energy':
            return EnergySensor(sensor_id, room_id)
        elif sensor_type == 'motion':
            return MotionSensor(sensor_id, room_id)
        elif sensor_type == 'occupancy':
            return OccupancySensor(sensor_id, room_id)
        else:
            raise ValueError(f"Unknown sensor type: {sensor_type}")
            
    async def run(self):
        """Start all servers."""
        logger.info("Starting simulator...")
        
        # Setup BACnet
        await self.bacnet_sim.setup()
        
        # Start tasks
        bacnet_task = asyncio.create_task(self.bacnet_sim.update_loop())
        modbus_task = asyncio.create_task(self.modbus_sim.run_server())
        
        logger.info("Simulator running...")
        
        # Wait for tasks
        await asyncio.gather(bacnet_task, modbus_task)


async def main():
    """Entry point."""
    config_dir = Path('/app/config')
    sensors_config = config_dir / 'sensors.yaml'
    rooms_config = config_dir / 'rooms.yaml'
    
    coordinator = SimulatorCoordinator(str(sensors_config), str(rooms_config))
    await coordinator.run()


if __name__ == '__main__':
    asyncio.run(main())
