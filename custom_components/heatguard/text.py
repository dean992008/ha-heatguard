from homeassistant.components.text import TextEntity
from .entity import HeatGuardEntity
from .api import numeric

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HeatGuardText(entry.runtime_data, key, name) for key, name in [('HeatSetPoint_s', 'Heating setpoint (°C)'), ('CoolSetPoint_s', 'Cooling setpoint (°C)')]])

class HeatGuardText(HeatGuardEntity, TextEntity):
    _attr_native_min = 1
    _attr_native_max = 32
    _attr_pattern = r'-?\d+([.,]\d)?'
    @property
    def native_value(self):
        return f"{numeric(self.coordinator.data['settings'][self.key]):.1f}"
    async def async_set_value(self, value):
        await self.coordinator.command(self.key, value)
