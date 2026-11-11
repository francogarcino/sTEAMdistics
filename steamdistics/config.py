import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT_DIR / 'config'
PROMPTS_DIR = Path(__file__).resolve().parent / 'prompts'
MAILMAP_FILE = CONFIG_DIR / 'mailmap'

DEFAULT_LAYER = 'otros'


@dataclass(frozen=True)
class LayerRule:
    layer: str
    segments: frozenset
    suffixes: tuple


@dataclass(frozen=True)
class AnalysisConfig:
    layers: tuple
    rules: tuple
    generated_pattern: re.Pattern
    diff_chars_per_member: int
    late_windows_hours: tuple
    gemini_models: tuple
    temperature: float
    max_output_tokens: int
    retries: int
    initial_wait_seconds: float
    timeout_seconds: float


@dataclass(frozen=True)
class CourseConfig:
    year: int
    name: str
    repo_pattern: re.Pattern
    teachers: frozenset
    roster_from_teams: bool
    members_by_team: dict

    def team_for_repo(self, repo_name):
        match = self.repo_pattern.match(repo_name)
        if not match:
            return None
        return match.groupdict().get('equipo') or repo_name


def _read_toml(path):
    return tomllib.loads(Path(path).read_text(encoding='utf-8'))


def load_analysis_config(path=CONFIG_DIR / 'analisis.toml'):
    data = _read_toml(path)
    layers = tuple(data['capas']['orden'])
    if DEFAULT_LAYER not in layers:
        raise ValueError(f"La capa '{DEFAULT_LAYER}' tiene que estar en capas.orden")
    rules = []
    for raw in data['capas'].get('reglas', []):
        if raw['capa'] not in layers:
            raise ValueError(f"La regla usa la capa '{raw['capa']}', que no está en capas.orden")
        rules.append(LayerRule(
            layer=raw['capa'],
            segments=frozenset(s.lower() for s in raw.get('segmentos', [])),
            suffixes=tuple(s.lower() for s in raw.get('sufijos', [])),
        ))
    gemini = data['gemini']
    limits = data['limites']
    return AnalysisConfig(
        layers=layers,
        rules=tuple(rules),
        generated_pattern=re.compile(data['generados']['patron'], re.IGNORECASE),
        diff_chars_per_member=int(limits['diff_chars_por_integrante']),
        late_windows_hours=tuple(int(h) for h in limits['ventanas_horas']),
        gemini_models=tuple(gemini['modelos']),
        temperature=float(gemini['temperatura']),
        max_output_tokens=int(gemini['max_output_tokens']),
        retries=int(gemini['reintentos']),
        initial_wait_seconds=float(gemini['espera_inicial_seg']),
        timeout_seconds=float(gemini['timeout_seg']),
    )


def load_course_config(path=CONFIG_DIR / 'cursada.toml'):
    data = _read_toml(path)
    teams = data['equipos']
    return CourseConfig(
        year=int(data['cursada']['anio']),
        name=str(data['cursada']['nombre']),
        repo_pattern=re.compile(teams['patron_repo']),
        teachers=frozenset(login.lower() for login in teams.get('docentes', [])),
        roster_from_teams=bool(teams.get('roster_desde_teams', False)),
        members_by_team={
            team: tuple(logins) for team, logins in teams.get('integrantes', {}).items()
        },
    )
