"""Platform/coordinator smoke tests using real Home Assistant classes."""
from types import SimpleNamespace
import importlib
import os
import pytest

# Protocol tests remain runnable on platforms that cannot install HA.
try:
    from custom_components.heatguard.coordinator import HeatGuardCoordinator
except ImportError as err:
    if os.environ.get('HEATGUARD_REQUIRE_HA'):
        raise
    pytest.skip(f'Home Assistant runtime unavailable: {err}', allow_module_level=True)

from homeassistant.exceptions import HomeAssistantError
from custom_components.heatguard.api import HeatGuardError
from test_api import TELEMETRY, HTML, api

class Coordinator:
    def __init__(self):
        self.entry = SimpleNamespace(entry_id='test')
        self.client = SimpleNamespace(url='http://device')
        self.data = {'telemetry': TELEMETRY['text'], 'settings': api.parse_settings(HTML)}
        self.last_update_success = True
        self.calls = []
    async def command(self, key, value):
        self.calls.append((key, value))

@pytest.mark.parametrize('key', ['HLoad', 'ElPower'])
@pytest.mark.parametrize('value,expected', [('1.25 кВт', 1250), ('0.0 кВт', 0)])
def test_power_converted_to_watts(key, value, expected):
    from custom_components.heatguard.sensor import HeatGuardSensor
    coordinator = Coordinator()
    coordinator.data['telemetry'] = dict(coordinator.data['telemetry'], **{key: value})
    sensor = HeatGuardSensor(coordinator, key, 'Power', 'W', 'power')
    assert sensor.native_value == expected
    assert sensor.native_unit_of_measurement == 'W'
    assert sensor.suggested_unit_of_measurement == 'W'

@pytest.mark.asyncio
async def test_all_platforms_states_and_commands():
    coordinator = Coordinator()
    entry = SimpleNamespace(runtime_data=coordinator)
    entities = []
    for platform in ('sensor', 'binary_sensor', 'switch', 'select', 'text'):
        module = importlib.import_module('custom_components.heatguard.' + platform)
        await module.async_setup_entry(None, entry, entities.extend)
    assert len(entities) == 22
    switch = next(e for e in entities if e.key == 'Mode_s')
    active = next(e for e in entities if e.key == 'compressor_active')
    assert switch.is_on is True
    assert active.is_on is False
    assert next(e for e in entities if e.key == 'Flow').native_unit_of_measurement == 'm³/h'
    await switch.async_turn_off()
    text = next(e for e in entities if e.key == 'HeatSetPoint_s')
    assert text.native_value == '34.0'
    await text.async_set_value('35.0')
    select = next(e for e in entities if e.key == 'HeatMode_s')
    assert select.current_option == 'Cooling'
    await select.async_select_option('Heating')
    assert coordinator.calls == [('Mode_s', 'Вимк.'), ('HeatSetPoint_s', '35.0'), ('HeatMode_s', 'Тепло')]
    coordinator.last_update_success = False
    assert all(not e.available for e in entities)
    coordinator.last_update_success = True
    assert all(e.available for e in entities)

@pytest.mark.asyncio
async def test_command_failure_marks_unavailable():
    async def fail(key, value):
        raise HeatGuardError('verification failed')
    errors = []
    fake = SimpleNamespace(client=SimpleNamespace(write=fail), async_set_update_error=errors.append)
    with pytest.raises(HomeAssistantError):
        await HeatGuardCoordinator.command(fake, 'Mode_s', 'Вимк.')
    assert errors

@pytest.mark.asyncio
async def test_lifecycle_setup_and_unload(monkeypatch):
    from custom_components import heatguard
    calls = []
    class MockCoordinator:
        def __init__(self, hass, entry, client):
            self.client = client
        async def async_config_entry_first_refresh(self):
            calls.append('refresh')
    async def forward(entry, platforms):
        calls.append(tuple(platforms))
    async def unload(entry, platforms):
        calls.append('unload')
        return True
    monkeypatch.setattr(heatguard, 'HeatGuardCoordinator', MockCoordinator)
    monkeypatch.setattr(heatguard, 'async_get_clientsession', lambda hass: object())
    hass = SimpleNamespace(config_entries=SimpleNamespace(async_forward_entry_setups=forward, async_unload_platforms=unload))
    entry = SimpleNamespace(data={'host': 'http://device', 'username': 'admin', 'password': ''})
    assert await heatguard.async_setup_entry(hass, entry)
    assert entry.runtime_data.client.auth.password == ''
    assert calls[0] == 'refresh'
    assert await heatguard.async_unload_entry(hass, entry)
    assert calls[-1] == 'unload'

@pytest.mark.asyncio
async def test_config_flow_validation(monkeypatch):
    from custom_components.heatguard import config_flow
    calls = []
    async def read(client):
        calls.append(client.auth.password)
        return {}
    monkeypatch.setattr(config_flow.HeatGuardClient, 'read', read)
    monkeypatch.setattr(config_flow, 'async_get_clientsession', lambda hass: object())
    fake = SimpleNamespace(hass=object(), _async_current_entries=lambda: [], async_create_entry=lambda **kw: kw, async_show_form=lambda **kw: kw)
    result = await config_flow.HeatGuardConfigFlow._form(fake, 'user', {'host': 'device', 'username': 'admin'})
    assert result['data']['password'] == ''
    assert result['data']['host'] == 'http://device'
    assert calls == ['']
    invalid = await config_flow.HeatGuardConfigFlow._form(fake, 'user', {'host': 'http://host/path', 'username': 'admin'})
    assert invalid['errors']['base'] == 'invalid_host'
