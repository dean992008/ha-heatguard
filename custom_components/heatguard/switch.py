from homeassistant.components.switch import SwitchEntity
from .entity import HeatGuardEntity

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HeatGuardSwitch(entry.runtime_data, 'Mode_s', 'Operation permitted')])

class HeatGuardSwitch(HeatGuardEntity, SwitchEntity):
    @property
    def is_on(self):
        return self.coordinator.data['settings'][self.key] == 'Ввімк.'
    async def async_turn_on(self, **kwargs):
        await self.coordinator.command(self.key, 'Ввімк.')
    async def async_turn_off(self, **kwargs):
        await self.coordinator.command(self.key, 'Вимк.')
