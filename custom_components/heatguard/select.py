from homeassistant.components.select import SelectEntity
from .entity import HeatGuardEntity
OPTIONS = {'HeatMode_s': {'Cooling': 'Холод', 'Heating': 'Тепло', 'Remote': 'Дистанц.'}, 'OnMode_s': {'Day': 'Денний', 'Night': 'Нічний', 'Schedule': 'За розкладом'}}

async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([HeatGuardSelect(entry.runtime_data, key, name) for key, name in [('HeatMode_s', 'Operating mode'), ('OnMode_s', 'Activation mode')]])

class HeatGuardSelect(HeatGuardEntity, SelectEntity):
    @property
    def options(self):
        return list(OPTIONS[self.key])
    @property
    def current_option(self):
        value = self.coordinator.data['settings'][self.key]
        return next(k for k, v in OPTIONS[self.key].items() if v == value)
    async def async_select_option(self, option):
        await self.coordinator.command(self.key, OPTIONS[self.key][option])
