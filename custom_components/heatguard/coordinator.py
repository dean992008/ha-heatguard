import logging
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.exceptions import ConfigEntryAuthFailed, HomeAssistantError
from .api import HeatGuardError, AuthenticationError

class HeatGuardCoordinator(DataUpdateCoordinator):
    def __init__(self, hass, entry, client):
        super().__init__(hass, logging.getLogger(__name__), name='HeatGuard', update_interval=timedelta(seconds=15))
        self.client = client
        self.entry = entry

    async def _async_update_data(self):
        try:
            return await self.client.read()
        except AuthenticationError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except HeatGuardError as err:
            raise UpdateFailed(str(err)) from err

    async def command(self, key, value):
        try:
            await self.client.write(key, value)
        except HeatGuardError as err:
            self.async_set_update_error(UpdateFailed(str(err)))
            raise HomeAssistantError(str(err)) from err
        await self.async_refresh()
        if not self.last_update_success:
            raise HomeAssistantError('Command sent, but refreshed state is unavailable')
