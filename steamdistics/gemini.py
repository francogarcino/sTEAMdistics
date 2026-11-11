import json
import secrets
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from string import Template
from steamdistics.config import PROMPTS_DIR

PROMPT_VERSION = '2026.11-1'
API_URL = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
VERDICTS = ['genuina', 'superficial', 'sin_evidencia']

_TEXT = {'type': 'STRING'}
RESPONSE_SCHEMA = {
    'type': 'OBJECT',
    'properties': {
        'integrantes': {
            'type': 'ARRAY',
            'items': {
                'type': 'OBJECT',
                'properties': {'alias': _TEXT, 'capas': _TEXT, 'integridad': _TEXT, 'gitflow': _TEXT},
                'required': ['alias', 'capas', 'integridad', 'gitflow'],
            },
        },
        'issues': {
            'type': 'ARRAY',
            'items': {
                'type': 'OBJECT',
                'properties': {
                    'numero': {'type': 'INTEGER'},
                    'veredicto': {'type': 'STRING', 'enum': VERDICTS},
                    'integrantes': {'type': 'ARRAY', 'items': _TEXT},
                    'comentario': _TEXT,
                },
                'required': ['numero', 'veredicto', 'integrantes', 'comentario'],
            },
        },
        'observaciones_equipo': _TEXT,
    },
    'required': ['integrantes', 'issues', 'observaciones_equipo'],
}


@dataclass(frozen=True)
class AiResult:
    data: dict | None
    model: str | None
    error: str | None

    @property
    def ok(self):
        return self.data is not None


class _DailyQuotaExhausted(Exception):
    pass


class _BadResponse(Exception):
    pass


def build_prompt(team, period, metrics_text, data_text, issues_text=None, nonce=None):
    nonce = nonce or secrets.token_hex(8)
    reentrega = ''
    if issues_text:
        reentrega = Template((PROMPTS_DIR / 'reentrega.md').read_text(encoding='utf-8')).substitute(
            issues=issues_text,
        )
    return Template((PROMPTS_DIR / 'equipo.md').read_text(encoding='utf-8')).substitute(
        nonce=nonce, reentrega=reentrega, equipo=team, rango=period,
        metricas=metrics_text, datos=data_text.replace(nonce, '[nonce]'),
    )


def _request(model, prompt, api_key, config, opener):
    payload = {
        'contents': [{'role': 'user', 'parts': [{'text': prompt}]}],
        'generationConfig': {
            'temperature': config.temperature,
            'maxOutputTokens': config.max_output_tokens,
            'responseMimeType': 'application/json',
            'responseSchema': RESPONSE_SCHEMA,
        },
    }
    request = urllib.request.Request(
        API_URL.format(model=model),
        data=json.dumps(payload).encode(),
        headers={'Content-Type': 'application/json', 'x-goog-api-key': api_key},
        method='POST',
    )
    with opener(request, timeout=config.timeout_seconds) as response:
        return json.loads(response.read())


def _extract(response):
    candidates = response.get('candidates') or []
    if not candidates:
        raise _BadResponse('respuesta sin candidatos')
    candidate = candidates[0]
    if candidate.get('finishReason') == 'MAX_TOKENS':
        raise _BadResponse('respuesta truncada por maxOutputTokens')
    parts = candidate.get('content', {}).get('parts', [])
    text = ''.join(p.get('text', '') for p in parts if not p.get('thought'))
    try:
        return json.loads(text)
    except json.JSONDecodeError as error:
        raise _BadResponse('respuesta que no es JSON válido') from error


def _is_daily_quota(error):
    try:
        body = error.read().decode('utf-8', 'replace')
    except Exception:
        return False
    return 'PerDay' in body


def _call_model(model, prompt, api_key, config, opener, sleep):
    wait = config.initial_wait_seconds
    for attempt in range(config.retries + 1):
        try:
            return _extract(_request(model, prompt, api_key, config, opener))
        except urllib.error.HTTPError as error:
            daily_quota = error.code == 429 and _is_daily_quota(error)
            error.close()
            if daily_quota:
                raise _DailyQuotaExhausted() from error
            if error.code not in RETRYABLE_STATUS or attempt == config.retries:
                raise
        except (urllib.error.URLError, TimeoutError):
            if attempt == config.retries:
                raise
        sleep(wait)
        wait *= 2


def analyze(prompt, api_key, config, opener=urllib.request.urlopen, sleep=time.sleep):
    errors = []
    for model in config.gemini_models:
        try:
            return AiResult(_call_model(model, prompt, api_key, config, opener, sleep), model, None)
        except _DailyQuotaExhausted:
            errors.append(f"{model}: cuota diaria agotada")
        except urllib.error.HTTPError as error:
            errors.append(f"{model}: HTTP {error.code}")
        except _BadResponse as error:
            errors.append(f"{model}: {error}")
        except (urllib.error.URLError, TimeoutError) as error:
            errors.append(f"{model}: error de red ({type(error).__name__})")
    return AiResult(None, None, '; '.join(errors) or 'sin modelos configurados')
