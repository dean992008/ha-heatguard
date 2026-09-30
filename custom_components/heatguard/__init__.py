from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import HeatGuardClient
from .const import PLATFORMS
from .coordinator import HeatGuardCoordinator

async def async_setup_entry(hass, entry):
    client = HeatGuardClient(async_get_clientsession(hass), entry.data['host'], entry.data['username'], entry.data.get('password', ''))
    coordinator = HeatGuardCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True

async def async_unload_entry(hass, entry):
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
