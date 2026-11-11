import re
from dataclasses import dataclass, field
from datetime import datetime
from steamdistics import context, gemini
from steamdistics.config import MAILMAP_FILE
from steamdistics.github import GitHubError
from steamdistics.gitlog import read_commits, read_merges
from steamdistics.identity import group_members
from steamdistics.metrics import compute_member_metrics, activity_shares
from steamdistics.reentrega import select_correction_issues, format_issues_for_prompt
from steamdistics.report import ReportData, render


@dataclass
class AnalysisInput:
    repo_dir: object
    repo: str
    team: str
    tag_range: object
    course: object
    config: object
    now: datetime
    github: object = None
    owner: str | None = None
    name: str | None = None
    api_key: str | None = None
    issues_created_before: datetime | None = None
    notices: list = field(default_factory=list)


@dataclass(frozen=True)
class AnalysisOutput:
    markdown: str
    ai_complete: bool


def team_slug(team):
    return re.sub(r'[^a-z0-9_-]+', '-', team.lower()).strip('-')


def _logins(inp):
    if not inp.github:
        return {}
    try:
        return inp.github.commit_logins(inp.owner, inp.name, inp.tag_range.tag_sha, inp.tag_range.previous_sha)
    except GitHubError:
        inp.notices.append("No se pudieron vincular los commits con logins de GitHub; "
                           "las identidades se agruparon solo por email y nombre.")
        return {}


def _roster(inp):
    configured = inp.course.members_by_team.get(inp.team)
    if configured:
        return list(configured)
    if not inp.github:
        return None
    if inp.course.roster_from_teams:
        members = inp.github.team_members(inp.owner, team_slug(inp.team))
        if members is not None:
            return members
    inp.notices.append("Roster del equipo no disponible: no se pueden detectar integrantes sin commits.")
    return None


def _issues(inp):
    if not (inp.github and inp.tag_range.previous):
        return None
    try:
        raw = inp.github.issues(inp.owner, inp.name)
        selected = select_correction_issues(
            raw, inp.course.teachers,
            created_before=inp.issues_created_before,
            closed_after=inp.tag_range.previous_date,
        )
        for issue in selected:
            if issue.state == 'closed':
                issue.closed_by = inp.github.issue_closer(inp.owner, inp.name, issue.number)
    except GitHubError:
        inp.notices.append("No se pudieron leer los issues del repo: se omite el análisis de reentrega.")
        return None
    if selected and not inp.course.teachers:
        inp.notices.append("La lista de docentes está vacía: se tomaron issues con severidad de cualquier autor.")
    return selected or None


def _metrics_for_prompt(aliases, metrics, shares, config):
    lines = []
    for alias, m, share in zip(aliases, metrics, shares):
        layers = ', '.join(f"{layer}={m.layer_share(layer)}%" for layer in config.layers)
        late = ', '.join(f"últimas {h} h={m.late_share.get(h, 0)}%" for h in config.late_windows_hours)
        lines.append(
            f"- {alias}: {m.commits} commits ({m.paired_commits} en pareja), +{m.added}/−{m.deleted} líneas, "
            f"{share}% de la actividad del equipo, {m.active_days} días activos, {late}, "
            f"{m.merges} merges, {m.reverts} reverts. Capas: {layers}"
        )
    return '\n'.join(lines)


def _run_ai(inp, members, metrics, shares, issues):
    aliases = context.assign_aliases(members)
    scrub = context.build_scrubber(members, aliases)
    sections, truncated = [], set()
    for member, alias in zip(members, aliases):
        diff, was_truncated = context.member_diff(member, inp.config.diff_chars_per_member)
        if was_truncated:
            truncated.add(member.name)
        sections.append(f"## {alias}\n\n{diff or '(sin commits propios en el período)'}")
    prompt = gemini.build_prompt(
        team=scrub(inp.team),
        period=inp.tag_range.label,
        metrics_text=_metrics_for_prompt(aliases, metrics, shares, inp.config),
        data_text=scrub('\n\n'.join(sections)),
        issues_text=scrub(format_issues_for_prompt(issues)) if issues else None,
    )
    return aliases, gemini.analyze(prompt, inp.api_key, inp.config), truncated


def run_analysis(inp):
    rev_range = inp.tag_range.rev_range
    commits = read_commits(inp.repo_dir, rev_range, inp.config, mailmap_file=MAILMAP_FILE)
    merges = read_merges(inp.repo_dir, rev_range, mailmap_file=MAILMAP_FILE)
    members = group_members(commits, merges, _logins(inp), _roster(inp))
    metrics = [compute_member_metrics(m, inp.tag_range.tag_date, inp.config) for m in members]
    shares_by_index = activity_shares(dict(enumerate(metrics)))
    shares = [shares_by_index[i] for i in range(len(metrics))]
    issues = _issues(inp)

    ai_requested = bool(inp.api_key) and any(m.has_activity for m in members)
    aliases, ai, truncated = context.assign_aliases(members), None, set()
    if ai_requested:
        aliases, ai, truncated = _run_ai(inp, members, metrics, shares, issues)

    data = ReportData(
        repo=inp.repo, team=inp.team, tag_range=inp.tag_range, generated_at=inp.now,
        layers=inp.config.layers, members=members, aliases=aliases, metrics=metrics, shares=shares,
        windows_hours=inp.config.late_windows_hours, ai=ai, ai_requested=ai_requested,
        issues=issues, truncated_members=truncated, notices=inp.notices,
        prompt_version=gemini.PROMPT_VERSION,
    )
    ai_complete = (not ai_requested) or ai.ok
    return AnalysisOutput(render(data), ai_complete)
