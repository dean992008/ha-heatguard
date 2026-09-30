import asyncio
import importlib.util
import json
from pathlib import Path
import pytest
import aiohttp
from aiohttp import web

ROOT = Path(__file__).parents[1]
spec = importlib.util.spec_from_file_location('heatguard_api', ROOT / 'custom_components/heatguard/api.py')
api = importlib.util.module_from_spec(spec)
spec.loader.exec_module(api)
HTML = (ROOT / 'tests/fixtures/setpoint_s.cgi.txt').read_text(encoding='utf-8-sig')
TELEMETRY = json.loads((ROOT / 'tests/fixtures/CurentParam_s.cgx.txt').read_text(encoding='utf-8-sig'))

def test_real_form():
    settings = api.parse_settings(HTML)
    assert settings['Mode_s'] == 'Ввімк.'
    assert settings['OnMode_s'] == 'За розкладом'
    assert api.numeric(settings['HeatSetPoint_s']) == 34
    assert settings['set'] == 'Запам’ятати'
    assert api.numeric(TELEMETRY['text']['CmpFreq']) == 0
    assert api.numeric('1.2 м3/год') == 1.2

@pytest.mark.parametrize('value', ['NaN', 'inf', '34.55', '34 °C', '1e3', ''])
def test_reject_invalid_setpoint(value):
    with pytest.raises(api.HeatGuardError):
        api.setpoint(value)

def test_parser_rejects_missing_and_ambiguous():
    with pytest.raises(api.HeatGuardError):
        api.parse_settings(HTML.replace('name="Mode_s"', 'name="other"'))
    with pytest.raises(api.HeatGuardError):
        api.parse_settings(HTML.replace('value="Вимк." >', 'value="Вимк." checked>'))

@pytest.mark.parametrize('url', ['ftp://host', 'http://admin:secret@host', 'http://host/path', 'http://host?x=1'])
def test_invalid_url(url):
    with pytest.raises(ValueError):
        api.normalize_url(url)

def render(settings):
    fields = []
    for key in api.FIELDS:
        kind = 'radio' if key in api.CHOICES else 'text'
        fields.append(f'<input type="{kind}" name="{key}" value="{settings[key]}" checked>')
    return '<form action="setpoint_s.cgi" method="post">' + ''.join(fields) + '<input name="set" value="Запам’ятати"></form>'

@pytest.mark.asyncio
async def test_roundtrip_concurrent_preserve_auth_and_telemetry():
    state = api.parse_settings(HTML)
    posts = []
    async def settings(request):
        assert request.headers['Authorization'] == 'Basic YWRtaW46'
        if request.method == 'POST':
            data = dict(await request.post())
            posts.append(data)
            assert data['set'] == 'Запам’ятати'
            state.update(data)
        return web.Response(text=render(state), content_type='text/html')
    async def telemetry(request):
        return web.json_response(TELEMETRY)
    app = web.Application()
    app.router.add_route('*', '/setpoint_s.cgi', settings)
    app.router.add_get('/CurentParam_s.cgx', telemetry)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    try:
        async with aiohttp.ClientSession() as session:
            client = api.HeatGuardClient(session, f'http://127.0.0.1:{port}', 'admin', '')
            await asyncio.gather(client.write('Mode_s', 'Вимк.'), client.write('HeatSetPoint_s', '35,1'))
            assert posts[0]['CoolSetPoint_s'] == '8.0 °C'
            assert posts[1]['Mode_s'] == 'Вимк.'
            assert state['HeatSetPoint_s'] == '35.1'
            snapshot = await client.read()
            assert snapshot['settings']['OnMode_s'] == 'За розкладом'
    finally:
        await runner.cleanup()

class Response:
    status = 200
    def __init__(self, text='', payload=None):
        self.html, self.payload = text, payload
    async def __aenter__(self):
        return self
    async def __aexit__(self, *args):
        pass
    async def text(self):
        return self.html
    async def json(self, **kwargs):
        return self.payload

class Session:
    def __init__(self, responses):
        self.responses = iter(responses)
    def request(self, *args, **kwargs):
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response

@pytest.mark.asyncio
async def test_verification_failure_no_retry():
    client = api.HeatGuardClient(Session([Response(HTML), Response(), Response(HTML)]), 'host', 'admin', '')
    with pytest.raises(api.HeatGuardError, match='verification'):
        await client.write('Mode_s', 'Вимк.')

@pytest.mark.asyncio
@pytest.mark.parametrize('failure', [asyncio.TimeoutError(), aiohttp.ClientConnectionError()])
async def test_transport_error(failure):
    client = api.HeatGuardClient(Session([failure]), 'host', 'admin', '')
    with pytest.raises(api.HeatGuardError):
        await client.read()

@pytest.mark.asyncio
async def test_auth_and_invalid_json():
    response = Response()
    response.status = 401
    client = api.HeatGuardClient(Session([response]), 'host', 'admin', '')
    with pytest.raises(api.AuthenticationError):
        await client.read()
    client = api.HeatGuardClient(Session([Response(payload={'text': {}})]), 'host', 'admin', '')
    with pytest.raises(api.HeatGuardError, match='Incomplete'):
        await client.read()

@pytest.mark.asyncio
@pytest.mark.parametrize(('key', 'value'), [('Mode_s', 'Вимк.'), ('HeatMode_s', 'Тепло'), ('HeatMode_s', 'Дистанц.'), ('OnMode_s', 'Денний'), ('OnMode_s', 'Нічний'), ('HeatSetPoint_s', '35.0'), ('CoolSetPoint_s', '9.0')])
async def test_each_setting_preserves_others(key, value):
    initial = api.parse_settings(HTML)
    changed = dict(initial, **{key: value})
    class RecordingSession(Session):
        def request(self, method, path, **kwargs):
            if method == 'POST':
                assert kwargs['data'] == changed
            return super().request(method, path, **kwargs)
    client = api.HeatGuardClient(RecordingSession([Response(HTML), Response(), Response(render(changed))]), 'host', 'admin', '')
    assert (await client.write(key, value))[key] == value

@pytest.mark.asyncio
async def test_detect_other_field_changed_after_write():
    changed = dict(api.parse_settings(HTML), Mode_s='Вимк.', HeatMode_s='Тепло')
    client = api.HeatGuardClient(Session([Response(HTML), Response(), Response(render(changed))]), 'host', 'admin', '')
    with pytest.raises(api.HeatGuardError, match='verification'):
        await client.write('Mode_s', 'Вимк.')

@pytest.mark.asyncio
@pytest.mark.parametrize('status', [302, 404, 500])
async def test_http_errors(status):
    response = Response()
    response.status = status
    client = api.HeatGuardClient(Session([response]), 'host', 'admin', '')
    with pytest.raises(api.HeatGuardError, match=f'HTTP {status}'):
        await client.read()
