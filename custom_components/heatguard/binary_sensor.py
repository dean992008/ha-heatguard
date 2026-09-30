from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
from .entity import HeatGuardEntity
from .api import numeric

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HeatGuardActive(entry.runtime_data, 'compressor_active', 'Compressor active')])

class HeatGuardActive(HeatGuardEntity, BinarySensorEntity):
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    @property
    def is_on(self):
        return numeric(self.coordinator.data['telemetry']['CmpFreq']) > 0
