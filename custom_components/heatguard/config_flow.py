import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .api import HeatGuardClient, HeatGuardError, AuthenticationError, normalize_url
from .const import DOMAIN

class HeatGuardConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        return await self._form('user', user_input)

    async def async_step_reconfigure(self, user_input=None):
        return await self._form('reconfigure', user_input)

    async def async_step_reauth(self, entry_data):
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(self, user_input=None):
        return await self._form('reauth_confirm', user_input)

    async def _form(self, step, user_input):
        errors = {}
        entry = self._get_reconfigure_entry() if step == 'reconfigure' else self._get_reauth_entry() if step == 'reauth_confirm' else None
        defaults = entry.data if entry else {'host': '', 'username': 'admin'}
        if user_input is not None:
            data = dict(user_input)
            data.setdefault('password', '')
            try:
                data['host'] = normalize_url(data['host'])
                client = HeatGuardClient(async_get_clientsession(self.hass), **{'url': data['host'], 'username': data['username'], 'password': data['password']})
                await client.read()
            except AuthenticationError:
                errors['base'] = 'invalid_auth'
            except ValueError:
                errors['base'] = 'invalid_host'
            except HeatGuardError:
                errors['base'] = 'cannot_connect'
            else:
                for existing in self._async_current_entries():
                    if existing.data['host'] == data['host'] and (entry is None or existing.entry_id != entry.entry_id):
                        return self.async_abort(reason='already_configured')
                if entry:
                    return self.async_update_reload_and_abort(entry, data_updates=data)
                return self.async_create_entry(title='HeatGuard ' + data['host'], data=data)
        schema = vol.Schema({vol.Required('host', default=defaults['host']): str, vol.Required('username', default=defaults['username']): str, vol.Optional('password', default=''): str})
        return self.async_show_form(step_id=step, data_schema=schema, errors=errors)
