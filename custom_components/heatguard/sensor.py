from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from .entity import HeatGuardEntity
from .api import numeric

# Key, label, unit, device class. Telemetry is instantaneous, not energy counters.
SENSORS = [('Mode', 'Reported mode', None, None), ('Warning', 'Status message', None, None), ('Setpt', 'Active setpoint', '°C', 'temperature'), ('COP', 'COP', None, None), ('InWater', 'Inlet water temperature', '°C', 'temperature'), ('OutTemp', 'Outdoor temperature', '°C', 'temperature'), ('OutWater', 'Outlet water temperature', '°C', 'temperature'), ('OutHTemp', 'OutHTemp', '°C', 'temperature'), ('LiqRef', 'Liquid refrigerant temperature', '°C', 'temperature'), ('DisTemp', 'Discharge temperature', '°C', 'temperature'), ('GasRef', 'Gas refrigerant temperature', '°C', 'temperature'), ('CmpFreq', 'Compressor frequency', 'Hz', 'frequency'), ('Flow', 'Water flow', 'm³/h', 'volume_flow_rate'), ('Curent', 'Current', 'A', 'current'), ('HLoad', 'Thermal load', 'W', 'power'), ('ElPower', 'Electrical power', 'W', 'power')]

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HeatGuardSensor(entry.runtime_data, *spec) for spec in SENSORS])

class HeatGuardSensor(HeatGuardEntity, SensorEntity):
    def __init__(self, coordinator, key, name, unit, device_class):
        super().__init__(coordinator, key, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = SensorDeviceClass(device_class) if device_class else None
        if key in ('HLoad', 'ElPower'):
            self._attr_suggested_unit_of_measurement = 'W'
        if key not in ('Mode', 'Warning'):
            self._attr_state_class = SensorStateClass.MEASUREMENT
    @property
    def native_value(self):
        value = self.coordinator.data['telemetry'][self.key]
        if self.key in ('Mode', 'Warning'):
            return value
        result = numeric(value)
        return result * 1000 if self.key in ('HLoad', 'ElPower') else result
