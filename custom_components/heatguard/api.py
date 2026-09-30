"""Local HeatGuard WEB V2.10 protocol; no Home Assistant dependencies."""
import asyncio
import math
import re
from html.parser import HTMLParser
from urllib.parse import urlsplit

import aiohttp

FIELDS = ('Mode_s', 'HeatMode_s', 'OnMode_s', 'HeatSetPoint_s', 'CoolSetPoint_s')
CHOICES = {'Mode_s': ('Вимк.', 'Ввімк.'), 'HeatMode_s': ('Холод', 'Тепло', 'Дистанц.'), 'OnMode_s': ('Денний', 'Нічний', 'За розкладом')}
TEMPERATURES = FIELDS[3:]

class HeatGuardError(Exception):
    """Communication or protocol failure."""

class AuthenticationError(HeatGuardError):
    """Credentials rejected."""

def normalize_url(value):
    value = value.strip().rstrip('/')
    if '://' not in value:
        value = 'http://' + value
    url = urlsplit(value)
    if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
        raise ValueError('Use a plain HTTP(S) server address without credentials or path')
    _ = url.port
    return value

def numeric(value):
    match = re.fullmatch(r'\s*([-+]?\d+(?:[.,]\d+)?)\s*(?:°C|Hz|м3/год|м³/год|m³/h|A|кВт|kW)?\s*', str(value))
    if not match:
        raise HeatGuardError('Invalid numeric value')
    result = float(match[1].replace(',', '.'))
    if not math.isfinite(result):
        raise HeatGuardError('Non-finite value')
    return result

def setpoint(value):
    if not re.fullmatch(r'-?\d+(?:[.,]\d)?', str(value).strip()):
        raise HeatGuardError('Setpoint requires a number with at most one decimal place')
    return f'{numeric(value):.1f}'

class FormParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.values = {}
        self.active = False
        self.valid_form = False
    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'form':
            self.active = attrs.get('action', '').lstrip('./') == 'setpoint_s.cgi' and attrs.get('method', '').lower() == 'post'
            self.valid_form |= self.active
        if tag != 'input' or not self.active:
            return
        name = attrs.get('name')
        if name not in (*FIELDS, 'set'):
            return
        if attrs.get('type', '').lower() == 'radio' and 'checked' not in attrs:
            return
        if name in self.values:
            raise HeatGuardError('Ambiguous settings form')
        self.values[name] = attrs.get('value', '')
    def handle_endtag(self, tag):
        if tag == 'form':
            self.active = False

def parse_settings(html):
    parser = FormParser()
    parser.feed(html)
    values = parser.values
    if not parser.valid_form or any(key not in values for key in (*FIELDS, 'set')):
        raise HeatGuardError('Incomplete settings form')
    for key, choices in CHOICES.items():
        if values[key] not in choices:
            raise HeatGuardError('Unsupported mode')
    for key in TEMPERATURES:
        numeric(values[key])
    return values

class HeatGuardClient:
    def __init__(self, session, url, username, password):
        self.session = session
        self.url = normalize_url(url)
        self.auth = aiohttp.BasicAuth(username, password)
        self.lock = asyncio.Lock()

    async def request(self, method, path, data=None):
        try:
            async with self.session.request(method, self.url + '/' + path, auth=self.auth, data=data, timeout=aiohttp.ClientTimeout(total=10), allow_redirects=False) as response:
                if response.status in (401, 403):
                    raise AuthenticationError('Credentials rejected')
                if response.status != 200:
                    raise HeatGuardError(f'HTTP {response.status}')
                if path.endswith('.cgx'):
                    return await response.json(content_type=None)
                return await response.text()
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError, UnicodeError) as err:
            raise HeatGuardError('Invalid response or connection failure') from err

    async def settings(self):
        return parse_settings(await self.request('GET', 'setpoint_s.cgi'))

    async def read(self):
        async with self.lock:
            payload = await self.request('GET', 'CurentParam_s.cgx')
            if not isinstance(payload, dict) or not isinstance(payload.get('text'), dict):
                raise HeatGuardError('Invalid telemetry')
            values = payload['text']
            expected = ('Mode', 'Warning', 'Setpt', 'COP', 'InWater', 'OutTemp', 'OutWater', 'OutHTemp', 'LiqRef', 'DisTemp', 'GasRef', 'CmpFreq', 'Flow', 'Curent', 'HLoad', 'ElPower')
            if any(key not in values or not isinstance(values[key], str) for key in expected):
                raise HeatGuardError('Incomplete telemetry')
            for key in expected[2:]:
                numeric(values[key])
            return {'telemetry': values, 'settings': await self.settings()}

    async def write(self, key, value):
        if key not in FIELDS:
            raise HeatGuardError('Unknown setting')
        if key in CHOICES and value not in CHOICES[key]:
            raise HeatGuardError('Unsupported mode')
        if key in TEMPERATURES:
            value = setpoint(value)
        async with self.lock:
            current = await self.settings()
            payload = dict(current)
            # Mimic JS focus sanitization only for the edited temperature.
            payload[key] = value
            await self.request('POST', 'setpoint_s.cgi', payload)
            actual = await self.settings()
            for field in FIELDS:
                equal = numeric(actual[field]) == numeric(payload[field]) if field in TEMPERATURES else actual[field] == payload[field]
                if not equal:
                    raise HeatGuardError('Settings verification failed; refresh before retrying')
            return actual
