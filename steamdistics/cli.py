"""Uso local: se corre dentro del repo de un equipo y deja el reporte en el directorio actual."""
import argparse
import os
from datetime import datetime, timezone
from pathlib import Path
from steamdistics.config import load_analysis_config, load_course_config
from steamdistics.github import GitHubClient, GitHubError, parse_remote
from steamdistics.gitrepo import GitError, build_range, git, tags_by_creation
from steamdistics.pipeline import AnalysisInput, run_analysis


def _git_config(key):
    try:
        return git('.', 'config', '--get', key).strip()
    except GitError:
        return ''


def _ask_index(label, max_index):
    while True:
        raw = input(f"{label} [0-{max_index}]: ").strip()
        if raw.isdigit() and 0 <= int(raw) <= max_index:
            return int(raw)
        print(f"  Ingresá un número entre 0 y {max_index}.")


def pick_range_interactively(tags):
    options = ['(inicio del repo)'] + tags + ['HEAD']
    print("Puntos disponibles:")
    for index, option in enumerate(options):
        print(f"  [{index}] {option}")
    start = _ask_index("Desde", len(options) - 2)
    end = _ask_index("Hasta", len(options) - 1)
    if end <= start or end == 0:
        raise SystemExit("Error: 'Hasta' debe ser posterior a 'Desde'.")
    return options[end], (options[start] if start > 0 else None)


def resolve_endpoints(args, tags):
    if not tags:
        raise SystemExit("Error: no hay tags en este repositorio.")
    if args.tag_to_head:
        return 'HEAD', tags[-1]
    if args.tag_to_tag:
        return tags[-1], tags[-2] if len(tags) > 1 else None
    return pick_range_interactively(tags)


def _github_context():
    token = os.environ.get('STEAMDISTICS_GH_TOKEN') or _git_config('sTEAMdistics.gh-token')
    try:
        owner, name = parse_remote(git('.', 'remote', 'get-url', 'origin'))
    except (GitError, GitHubError):
        return None, None, None
    return GitHubClient(token or None), owner, name


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Reporte de participación de un repo de equipo (uso local).',
        epilog='Sin modo: lista los tags y permite elegir el rango.',
    )
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('-H', '--tag-to-head', action='store_true', help='Último tag → HEAD.')
    modes.add_argument('-T', '--tag-to-tag', action='store_true',
                       help='Penúltimo tag → último tag (lo mismo que hace el CI).')
    parser.add_argument('--ai', action='store_true', help='Activa el análisis con Gemini.')
    parser.add_argument('--sin-github', action='store_true',
                        help='No consulta la API de GitHub (sin logins, roster ni issues).')
    args = parser.parse_args(argv)

    api_key = None
    if args.ai:
        api_key = os.environ.get('STEAMDISTICS_AI_KEY') or _git_config('sTEAMdistics.ai-key')
        if not api_key:
            raise SystemExit(
                "Error: --ai requiere una API Key de Gemini.\n"
                "Configurala con: git config --global sTEAMdistics.ai-key \"TU_CLAVE\"\n"
                "o con la variable de entorno STEAMDISTICS_AI_KEY."
            )

    repo_dir = Path(git('.', 'rev-parse', '--show-toplevel').strip())
    end, start = resolve_endpoints(args, tags_by_creation(repo_dir))
    tag_range = build_range(repo_dir, end, start)
    github, owner, name = (None, None, None) if args.sin_github else _github_context()
    course = load_course_config()
    repo_name = name or repo_dir.name
    team = course.team_for_repo(repo_name) or repo_name

    print(f"Analizando {tag_range.label}...")
    now = datetime.now(timezone.utc)
    output = run_analysis(AnalysisInput(
        repo_dir=repo_dir, repo=f"{owner}/{name}" if owner else repo_name, team=team,
        tag_range=tag_range, course=course, config=load_analysis_config(), now=now,
        github=github, owner=owner, name=name, api_key=api_key,
        issues_created_before=tag_range.tag_date,
    ))
    filename = f"{repo_name}-stats-{now:%Y-%m-%d}.md"
    Path(filename).write_text(output.markdown, encoding='utf-8')
    print(f"[OK] Reporte generado: {filename}")
