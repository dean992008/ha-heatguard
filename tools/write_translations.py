"""Generate config flow translations from the same schema."""
import json
from pathlib import Path

root = Path(__file__).parents[1] / 'custom_components/heatguard'
for language in ('en', 'ru'):
    ru = language == 'ru'
    fields = {'host': 'Адрес сервера' if ru else 'Server address', 'username': 'Имя пользователя' if ru else 'Username', 'password': 'Пароль (может быть пустым)' if ru else 'Password (may be empty)'}
    content = {'title': 'HeatGuard', 'config': {'step': {step: {'title': 'HeatGuard', 'description': 'Локальное подключение. Пустое поле означает пустой пароль.' if ru else 'Local connection. An empty password field means an empty password.', 'data': fields} for step in ('user', 'reconfigure', 'reauth_confirm')}, 'error': {'invalid_auth': 'Неверные учётные данные' if ru else 'Invalid credentials', 'cannot_connect': 'Нет связи или ответ контроллера некорректен' if ru else 'Cannot connect or invalid controller response', 'invalid_host': 'Укажите HTTP(S) адрес без пути и учётных данных' if ru else 'Enter an HTTP(S) address without path or credentials'}, 'abort': {'already_configured': 'Устройство уже настроено' if ru else 'Device already configured', 'reconfigure_successful': 'Настройки обновлены' if ru else 'Configuration updated', 'reauth_successful': 'Учётные данные обновлены' if ru else 'Authentication updated'}}}
    target = root / 'translations' / f'{language}.json'
    target.parent.mkdir(exist_ok=True)
    target.write_text(json.dumps(content, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    if language == 'en':
        (root / 'strings.json').write_text(target.read_text(encoding='utf-8'), encoding='utf-8')
