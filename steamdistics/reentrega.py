import unicodedata
from dataclasses import dataclass
from datetime import datetime

SEVERITIES = ('grave', 'corregir', 'menor', 'observacion')
SEVERITY_DISPLAY = {'grave': 'Grave', 'corregir': 'Corregir', 'menor': 'Menor', 'observacion': 'Observación'}
BODY_LIMIT = 400


@dataclass
class CorrectionIssue:
    number: int
    title: str
    body: str
    severity: str
    state: str
    author: str
    closed_by: str | None = None

    @property
    def severity_display(self):
        return SEVERITY_DISPLAY[self.severity]


def _normalize(label):
    return unicodedata.normalize('NFKD', label).encode('ascii', 'ignore').decode().lower().strip()


def severity_of(raw_issue):
    found = {_normalize(label.get('name', '')) for label in raw_issue.get('labels', [])}
    return next((s for s in SEVERITIES if s in found), None)


def _parse_time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')) if value else None


def select_correction_issues(raw_issues, teachers, created_before=None, closed_after=None):
    selected = []
    for raw in raw_issues:
        severity = severity_of(raw)
        author = (raw.get('user') or {}).get('login', '')
        if not severity or (teachers and author.lower() not in teachers):
            continue
        created = _parse_time(raw.get('created_at'))
        closed = _parse_time(raw.get('closed_at'))
        if created_before and created and created > created_before:
            continue
        if closed_after and closed and closed < closed_after:
            continue
        body = ' '.join((raw.get('body') or '').split())
        selected.append(CorrectionIssue(
            number=raw['number'],
            title=raw.get('title', ''),
            body=body[:BODY_LIMIT] + ('...' if len(body) > BODY_LIMIT else ''),
            severity=severity,
            state=raw.get('state', 'open'),
            author=author,
        ))
    return sorted(selected, key=lambda i: (SEVERITIES.index(i.severity), i.number))


def format_issues_for_prompt(issues):
    lines = []
    for issue in issues:
        line = f"#{issue.number} [{issue.severity_display}] ({'abierto' if issue.state == 'open' else 'cerrado'}): {issue.title}"
        if issue.body:
            line += f" — {issue.body}"
        lines.append(line)
    return '\n'.join(lines)
