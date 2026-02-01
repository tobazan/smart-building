"""
Room profiles for smart building sensor simulation.
Each room has unique characteristics that affect sensor readings.
"""
import random
import math
from datetime import datetime


class RoomProfile:
    """Base class for room sensor profiles"""
    
    def __init__(self, room_id, name, floor, room_type):
        self.room_id = room_id
        self.name = name
        self.floor = floor
        self.room_type = room_type
        self.time_offset = 0  # For time-based patterns
    
    def get_telemetry(self):
        """Generate telemetry data for this room. Override in subclasses."""
        raise NotImplementedError
    
    def _add_noise(self, value, noise_percent=2):
        """Add random noise to a value"""
        noise = value * (noise_percent / 100) * (random.random() - 0.5) * 2
        return value + noise
    
    def _time_based_pattern(self, base_value, amplitude, period_minutes=60):
        """Generate a sinusoidal pattern based on time"""
        self.time_offset += 0.5  # Increment by publish interval
        phase = (self.time_offset / (period_minutes * 60)) * 2 * math.pi
        return base_value + amplitude * math.sin(phase)


class ServerRoom(RoomProfile):
    """Room 1: Server Room - Cool, low humidity, always occupied, high energy"""
    
    def __init__(self):
        super().__init__("01", "Server Room", 1, "server")
    
    def get_telemetry(self):
        temp = self._add_noise(19.0, noise_percent=1)  # Very stable 18-20°C
        humidity = self._add_noise(35.0, noise_percent=3)  # Low humidity 32-38%
        co2 = self._add_noise(450, noise_percent=5)  # Low CO2
        light = 0  # Always dark
        occupancy = 0  # No humans, but "occupied" by servers
        motion = False
        energy = self._add_noise(2.3, noise_percent=8)  # High consistent energy
        air_quality = random.randint(90, 100)  # Excellent air quality
        
        return {
            "room_id": self.room_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "temperature": round(temp, 2),
            "humidity": round(humidity, 2),
            "co2_ppm": int(co2),
            "light_lux": light,
            "occupancy_count": occupancy,
            "motion_detected": motion,
            "energy_kwh": round(energy, 3),
            "air_quality_index": air_quality
        }


class ConferenceRoom(RoomProfile):
    """Room 2: Conference Room - Variable conditions with burst patterns"""
    
    def __init__(self):
        super().__init__("02", "Conference Room", 2, "conference")
        self.meeting_active = False
        self.meeting_timer = 0
    
    def get_telemetry(self):
        # Simulate meeting cycles (15 min meetings every hour)
        self.meeting_timer += 0.5
        if self.meeting_timer > 3600:  # Reset every hour
            self.meeting_timer = 0
        
        # Meeting from minute 0-15 each hour
        self.meeting_active = (self.meeting_timer % 3600) < 900
        
        if self.meeting_active:
            temp = self._add_noise(23.5, noise_percent=5)
            humidity = self._add_noise(55.0, noise_percent=8)
            co2 = self._add_noise(1200, noise_percent=15)
            light = random.randint(400, 600)
            occupancy = random.randint(6, 12)
            motion = True
            energy = self._add_noise(1.5, noise_percent=20)
        else:
            temp = self._add_noise(21.0, noise_percent=3)
            humidity = self._add_noise(45.0, noise_percent=5)
            co2 = self._add_noise(500, noise_percent=10)
            light = random.randint(0, 100)
            occupancy = 0
            motion = random.random() < 0.1
            energy = self._add_noise(0.3, noise_percent=15)
        
        air_quality = max(50, 100 - int(co2 / 20))
        
        return {
            "room_id": self.room_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "temperature": round(temp, 2),
            "humidity": round(humidity, 2),
            "co2_ppm": int(co2),
            "light_lux": light,
            "occupancy_count": occupancy,
            "motion_detected": motion,
            "energy_kwh": round(energy, 3),
            "air_quality_index": air_quality
        }


class StorageCloset(RoomProfile):
    """Room 3: Storage Closet - Stable, dark, no activity"""
    
    def __init__(self):
        super().__init__("03", "Storage Closet", 1, "storage")
    
    def get_telemetry(self):
        temp = self._add_noise(20.5, noise_percent=1)
        humidity = self._add_noise(50.0, noise_percent=2)
        co2 = self._add_noise(400, noise_percent=3)
        light = 0  # Always dark
        occupancy = 0
        motion = False
        energy = self._add_noise(0.05, noise_percent=10)  # Minimal
        air_quality = random.randint(85, 95)
        
        return {
            "room_id": self.room_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "temperature": round(temp, 2),
            "humidity": round(humidity, 2),
            "co2_ppm": int(co2),
            "light_lux": light,
            "occupancy_count": occupancy,
            "motion_detected": motion,
            "energy_kwh": round(energy, 3),
            "air_quality_index": air_quality
        }


class OpenOffice(RoomProfile):
    """Room 4: Open Office - Consistent occupancy during work hours"""
    
    def __init__(self):
        super().__init__("04", "Open Office", 2, "office")
    
    def get_telemetry(self):
        # Simulate work hours (9-17) with time-based patterns
        hour = datetime.utcnow().hour
        is_work_hours = 9 <= hour <= 17
        
        if is_work_hours:
            temp = self._time_based_pattern(22.0, 1.5, period_minutes=120)
            humidity = self._add_noise(48.0, noise_percent=5)
            co2 = self._add_noise(800, noise_percent=12)
            light = random.randint(350, 500)
            occupancy = random.randint(5, 8)
            motion = True
            energy = self._add_noise(1.2, noise_percent=10)
        else:
            temp = self._add_noise(20.0, noise_percent=2)
            humidity = self._add_noise(45.0, noise_percent=3)
            co2 = self._add_noise(450, noise_percent=8)
            light = random.randint(0, 50)
            occupancy = 0
            motion = random.random() < 0.05
            energy = self._add_noise(0.4, noise_percent=10)
        
        air_quality = max(60, 100 - int(co2 / 15))
        
        return {
            "room_id": self.room_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "temperature": round(temp, 2),
            "humidity": round(humidity, 2),
            "co2_ppm": int(co2),
            "light_lux": light,
            "occupancy_count": occupancy,
            "motion_detected": motion,
            "energy_kwh": round(energy, 3),
            "air_quality_index": air_quality
        }


class Kitchen(RoomProfile):
    """Room 5: Kitchen - High humidity/temp spikes, energy bursts"""
    
    def __init__(self):
        super().__init__("05", "Kitchen", 1, "kitchen")
        self.cooking_active = False
        self.cooking_timer = 0
    
    def get_telemetry(self):
        # Random cooking events
        if random.random() < 0.02:  # 2% chance to start cooking
            self.cooking_active = True
            self.cooking_timer = random.randint(300, 900)  # 5-15 minutes
        
        if self.cooking_active:
            self.cooking_timer -= 0.5
            if self.cooking_timer <= 0:
                self.cooking_active = False
        
        if self.cooking_active:
            temp = self._add_noise(28.0, noise_percent=10)
            humidity = self._add_noise(70.0, noise_percent=12)
            co2 = self._add_noise(1000, noise_percent=20)
            light = random.randint(300, 500)
            occupancy = random.randint(1, 3)
            motion = True
            energy = self._add_noise(3.5, noise_percent=25)
        else:
            temp = self._add_noise(21.0, noise_percent=3)
            humidity = self._add_noise(50.0, noise_percent=5)
            co2 = self._add_noise(550, noise_percent=10)
            light = random.randint(100, 300)
            occupancy = random.randint(0, 1)
            motion = random.random() < 0.3
            energy = self._add_noise(0.6, noise_percent=15)
        
        air_quality = max(40, 100 - int(co2 / 18))
        
        return {
            "room_id": self.room_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "temperature": round(temp, 2),
            "humidity": round(humidity, 2),
            "co2_ppm": int(co2),
            "light_lux": light,
            "occupancy_count": occupancy,
            "motion_detected": motion,
            "energy_kwh": round(energy, 3),
            "air_quality_index": air_quality
        }


class LabWorkshop(RoomProfile):
    """Room 6: Lab/Workshop - Highly variable with air quality issues"""
    
    def __init__(self):
        super().__init__("06", "Lab Workshop", 1, "lab")
    
    def get_telemetry(self):
        # Very erratic patterns
        temp = self._add_noise(22.0, noise_percent=15)
        humidity = self._add_noise(45.0, noise_percent=20)
        co2 = self._add_noise(900, noise_percent=30)
        light = random.randint(200, 700)
        occupancy = random.randint(0, 4)
        motion = random.random() < 0.6
        energy = self._add_noise(1.8, noise_percent=40)
        
        # Sometimes poor air quality
        if random.random() < 0.1:
            air_quality = random.randint(30, 50)
        else:
            air_quality = random.randint(55, 75)
        
        return {
            "room_id": self.room_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "temperature": round(temp, 2),
            "humidity": round(humidity, 2),
            "co2_ppm": int(co2),
            "light_lux": light,
            "occupancy_count": occupancy,
            "motion_detected": motion,
            "energy_kwh": round(energy, 3),
            "air_quality_index": air_quality
        }


class BreakRoom(RoomProfile):
    """Room 7: Break Room - Stable temp, low occupancy, variable lighting"""
    
    def __init__(self):
        super().__init__("07", "Break Room", 2, "breakroom")
    
    def get_telemetry(self):
        # Sporadic use throughout the day
        in_use = random.random() < 0.25  # 25% of the time
        
        temp = self._add_noise(21.5, noise_percent=2)
        humidity = self._add_noise(47.0, noise_percent=4)
        co2 = self._add_noise(600 if in_use else 450, noise_percent=10)
        light = random.randint(250, 400) if in_use else random.randint(0, 100)
        occupancy = random.randint(1, 3) if in_use else 0
        motion = in_use
        energy = self._add_noise(0.8 if in_use else 0.3, noise_percent=15)
        air_quality = random.randint(75, 90)
        
        return {
            "room_id": self.room_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "temperature": round(temp, 2),
            "humidity": round(humidity, 2),
            "co2_ppm": int(co2),
            "light_lux": light,
            "occupancy_count": occupancy,
            "motion_detected": motion,
            "energy_kwh": round(energy, 3),
            "air_quality_index": air_quality
        }


class ExecutiveOffice(RoomProfile):
    """Room 8: Executive Office - Perfectly controlled environment"""
    
    def __init__(self):
        super().__init__("08", "Executive Office", 3, "executive")
    
    def get_telemetry(self):
        # Very stable, single occupancy during work hours
        hour = datetime.utcnow().hour
        is_work_hours = 9 <= hour <= 17
        
        temp = self._add_noise(21.0, noise_percent=1)  # Tight control
        humidity = self._add_noise(45.0, noise_percent=2)
        co2 = self._add_noise(650 if is_work_hours else 420, noise_percent=5)
        light = random.randint(400, 450) if is_work_hours else 0
        occupancy = 1 if is_work_hours else 0
        motion = is_work_hours
        energy = self._add_noise(0.7 if is_work_hours else 0.2, noise_percent=8)
        air_quality = random.randint(85, 98)
        
        return {
            "room_id": self.room_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "temperature": round(temp, 2),
            "humidity": round(humidity, 2),
            "co2_ppm": int(co2),
            "light_lux": light,
            "occupancy_count": occupancy,
            "motion_detected": motion,
            "energy_kwh": round(energy, 3),
            "air_quality_index": air_quality
        }


# Factory function to get all room profiles
def get_all_room_profiles():
    """Returns a list of all 8 room profile instances"""
    return [
        ServerRoom(),
        ConferenceRoom(),
        StorageCloset(),
        OpenOffice(),
        Kitchen(),
        LabWorkshop(),
        BreakRoom(),
        ExecutiveOffice()
    ]
