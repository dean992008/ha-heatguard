from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.entity import DeviceInfo
from .const import DOMAIN

class HeatGuardEntity(CoordinatorEntity):
    _attr_has_entity_name = True
    def __init__(self, coordinator, key, name):
        super().__init__(coordinator)
        self.key = key
        self._attr_name = name
        self._attr_unique_id = f'{coordinator.entry.entry_id}_{key}'
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, coordinator.entry.entry_id)}, name='HeatGuard', manufacturer='Mitsubishi Heavy / HeatGuard', model='140SX (owner supplied)', configuration_url=coordinator.client.url)
