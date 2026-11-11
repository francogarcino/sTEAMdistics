import json
from pathlib import Path

NEW = 'nuevo'
MOVED = 'movido'
ALREADY_DONE = 'repetido'
RETRY_AI = 'completar_ia'


def state_file(reports_dir, repo):
    return Path(reports_dir) / 'state' / f"{repo.replace('/', '__')}.json"


def load(reports_dir, repo):
    path = state_file(reports_dir, repo)
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}


def classify(state, tag, sha):
    previous = state.get(tag)
    if previous is None:
        return NEW
    if previous['sha'] != sha:
        return MOVED
    return ALREADY_DONE if previous.get('ia_completa') else RETRY_AI


def record(reports_dir, repo, tag, sha, report_path, analyzed_at, ai_complete):
    state = load(reports_dir, repo)
    state[tag] = {
        'sha': sha,
        'reporte': str(report_path),
        'analizado': analyzed_at.isoformat(timespec='seconds'),
        'ia_completa': ai_complete,
    }
    path = state_file(reports_dir, repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
