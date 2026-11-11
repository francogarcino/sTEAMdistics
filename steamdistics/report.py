import re
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ReportData:
    repo: str
    team: str
    tag_range: object
    generated_at: datetime
    layers: tuple
    members: list
    aliases: list
    metrics: list
    shares: list
    windows_hours: tuple
    ai: object = None
    ai_requested: bool = False
    issues: list | None = None
    truncated_members: set = field(default_factory=set)
    notices: list = field(default_factory=list)
    prompt_version: str = ''


def make_bar(percentage, width=10):
    filled = max(0, min(width, round(percentage * width / 100)))
    return '▓' * filled + '░' * (width - filled)


def make_anchor(text):
    return re.sub(r'[^\w\s-]', '', text.lower()).strip().replace(' ', '-')


def cell(text):
    return ' '.join(str(text).split()).replace('|', '\\|')


def _display_name(member):
    return f"{member.name} (@{member.login})" if member.login and member.login != member.name else member.name


def unalias(text, data):
    names = dict(zip(data.aliases, (m.name for m in data.members)))
    if not names:
        return text
    pattern = re.compile(r'\b(?:' + '|'.join(re.escape(a) for a in sorted(names, key=len, reverse=True)) + r')\b')
    return pattern.sub(lambda m: names[m.group(0)], text)


def _ai_by_alias(data):
    if not (data.ai and data.ai.ok):
        return {}
    return {entry.get('alias'): entry for entry in data.ai.data.get('integrantes', [])}


def _header(data):
    tr = data.tag_range
    return [
        f"# Reporte de participación: {data.team}",
        "",
        f"**Repo:** `{data.repo}` · **Tag:** `{tr.tag}` (`{tr.tag_sha[:8]}`) · "
        f"**Rango:** {tr.label} · **Generado:** {data.generated_at:%Y-%m-%d %H:%M} UTC",
        "",
        "> **CONFIDENCIAL** — uso exclusivo docente. Las métricas son determinísticas; "
        "el análisis de IA es una primera pasada y no reemplaza la corrección.",
        "",
    ]


def _notices(data):
    notices = list(data.notices)
    if data.ai_requested and data.ai and not data.ai.ok:
        notices.append(f"Análisis IA no disponible: {data.ai.error}.")
    if data.truncated_members:
        names = ', '.join(sorted(data.truncated_members))
        notices.append(f"Los diffs enviados a la IA se recortaron por presupuesto para: {names}.")
    inactive = [m.name for m in data.members if not m.has_activity]
    if inactive:
        notices.append(f"Sin actividad en el período: {', '.join(inactive)}.")
    if not notices:
        return []
    return ["## Avisos", ""] + [f"- ⚠️ {n}" for n in notices] + [""]


def _summary_table(data):
    late_headers = ' | '.join(f"Últimas {h} h" for h in data.windows_hours)
    lines = [
        "## Resumen del equipo", "",
        f"| Integrante | Commits | En pareja | + / − | Actividad | Días activos | {late_headers} | Merges | Reverts |",
        "|---|---|---|---|---|---|" + "---|" * len(data.windows_hours) + "---|---|",
    ]
    for member, metrics, share in zip(data.members, data.metrics, data.shares):
        late = ' | '.join(f"{metrics.late_share.get(h, 0)}%" for h in data.windows_hours)
        name = f"[{cell(_display_name(member))}](#{make_anchor(member.name)})"
        if not member.has_activity:
            name += " ⚠️"
        lines.append(
            f"| {name} | {metrics.commits} | {metrics.paired_commits} | +{metrics.added} / −{metrics.deleted} | "
            f"{share}% {make_bar(share)} | {metrics.active_days} | {late} | {metrics.merges} | {metrics.reverts} |"
        )
    lines += ["", "*Los commits en pareja (`Co-authored-by`) suman a ambos integrantes.*", ""]
    return lines


def _layers_table(data):
    lines = [
        "## Distribución por capa", "",
        "| Integrante | " + " | ".join(data.layers) + " |",
        "|---|" + "---|" * len(data.layers),
    ]
    for member, metrics in zip(data.members, data.metrics):
        values = " | ".join(f"{metrics.layer_share(layer)}%" for layer in data.layers)
        lines.append(f"| {cell(member.name)} | {values} |")
    return lines + [""]


def _team_observations(data):
    if not (data.ai and data.ai.ok):
        return []
    text = unalias(data.ai.data.get('observaciones_equipo', '').strip(), data)
    return ["## Observaciones de IA sobre el equipo", "", text, ""] if text else []


def _reentrega(data):
    if not data.issues:
        return []
    verdicts = {}
    if data.ai and data.ai.ok:
        verdicts = {v.get('numero'): v for v in data.ai.data.get('issues', [])}
    names = dict(zip(data.aliases, (m.name for m in data.members)))
    lines = [
        "## Reentrega", "",
        "| Issue | Severidad | Estado | Cerrado por | Veredicto IA | Quién | Comentario |",
        "|---|---|---|---|---|---|---|",
    ]
    for issue in data.issues:
        verdict = verdicts.get(issue.number, {})
        who = ', '.join(names.get(a, a) for a in verdict.get('integrantes', []))
        lines.append(
            f"| #{issue.number} {cell(issue.title)} | {issue.severity_display} | "
            f"{'abierto' if issue.state == 'open' else 'cerrado'} | {cell(issue.closed_by or '—')} | "
            f"{verdict.get('veredicto', '—')} | {cell(who or '—')} | {cell(unalias(verdict.get('comentario', '—'), data))} |"
        )
    return lines + [""]


def _member_section(member, metrics, ai_entry, data):
    lines = [f"### {member.name}", ""]
    if member.login:
        lines.append(f"GitHub: @{member.login}")
    if member.emails:
        lines.append(f"Emails: {', '.join(sorted(member.emails))}")
    lines.append("")
    if ai_entry:
        for label, key in (("Capas", 'capas'), ("Integridad", 'integridad'), ("Gitflow", 'gitflow')):
            lines += [f"**{label}:** {unalias(ai_entry.get(key, '').strip(), data)}", ""]
    if not member.has_activity:
        return lines + ["Sin actividad en el período.", ""]
    lines += ["**Capas:**", ""]
    for layer in data.layers:
        added, deleted = metrics.layers.get(layer, (0, 0))
        share = metrics.layer_share(layer)
        lines.append(f"- `{layer}`: {share}% {make_bar(share)} (+{added} / −{deleted})")
    lines += ["", f"**Actividad por día:** " + ', '.join(
        f"{day} ({count})" for day, count in metrics.commits_by_day.items()), ""]
    lines += ["<details><summary>Commits</summary>", ""]
    for commit in member.authored:
        pair = " (en pareja)" if commit.co_authors else ""
        lines.append(f"- `{commit.sha[:8]}` {commit.date:%Y-%m-%d %H:%M} — {cell(commit.subject)} "
                     f"(+{commit.added} / −{commit.deleted}){pair}")
    for commit in member.co_authored:
        lines.append(f"- `{commit.sha[:8]}` {commit.date:%Y-%m-%d %H:%M} — {cell(commit.subject)} "
                     f"(coautor, +{commit.added} / −{commit.deleted})")
    return lines + ["", "</details>", ""]


def _footer(data):
    model = data.ai.model if data.ai and data.ai.ok else '—'
    return ["---", f"*Modelo: {model} · Prompt: {data.prompt_version} · "
                   f"Commit del tag: `{data.tag_range.tag_sha}`*", ""]


def render(data):
    ai = _ai_by_alias(data)
    lines = _header(data) + _notices(data) + _summary_table(data) + _layers_table(data)
    lines += _team_observations(data) + _reentrega(data) + ["## Detalle por integrante", ""]
    for member, alias, metrics in zip(data.members, data.aliases, data.metrics):
        lines += _member_section(member, metrics, ai.get(alias), data)
    return '\n'.join(lines + _footer(data))
