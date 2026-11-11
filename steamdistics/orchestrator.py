"""Punto de entrada del CI: analiza el último tag de un repo de equipo.

Los logs de Actions pueden ser leídos por quien tenga el token de dispatch, así que
este módulo solo imprime mensajes neutros. El detalle de cualquier error se guarda
en la rama `reportes`.
"""
import argparse
import base64
import os
import re
import subprocess
import sys
import tempfile
import traceback
from datetime import datetime, timezone
from pathlib import Path
from steamdistics import state
from steamdistics.config import load_analysis_config, load_course_config
from steamdistics.github import GitHubClient
from steamdistics.gitrepo import latest_tag_range, tags_by_creation
from steamdistics.pipeline import AnalysisInput, run_analysis

REPO_RE = re.compile(r'^[A-Za-z0-9-]{1,39}/[A-Za-z0-9._-]{1,100}$')
TAG_RE = re.compile(r'^(?![-./])(?!.*\.\.)[A-Za-z0-9._/+-]{1,100}$')


class Ignored(Exception):
    pass


def validate_inputs(repo, tag, expected_owner, course):
    if not REPO_RE.match(repo or ''):
        raise Ignored("repo con formato inválido")
    if not TAG_RE.match(tag or ''):
        raise Ignored("tag con formato inválido")
    owner, name = repo.split('/')
    if expected_owner and owner.lower() != expected_owner.lower():
        raise Ignored("el repo no pertenece a la organización")
    team = course.team_for_repo(name)
    if not team:
        raise Ignored("el repo no es de un equipo")
    return owner, name, team


def clone_bare(repo, token, dest):
    credentials = base64.b64encode(f"x-access-token:{token}".encode()).decode()
    env = {
        **os.environ,
        'GIT_TERMINAL_PROMPT': '0',
        'GIT_CONFIG_COUNT': '1',
        'GIT_CONFIG_KEY_0': 'http.https://github.com/.extraheader',
        'GIT_CONFIG_VALUE_0': f'AUTHORIZATION: basic {credentials}',
    }
    result = subprocess.run(
        ['git', '-c', 'core.hooksPath=/dev/null', 'clone', '--bare', '--quiet',
         f'https://github.com/{repo}.git', str(dest)],
        env=env, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"git clone falló ({result.returncode}): {result.stderr.strip()}")


def report_path(reports_dir, course, team, tag):
    return Path(reports_dir) / str(course.year) / course.name / team / f"{tag.replace('/', '_')}.md"


def analyze_latest_tag(repo, tag, reports_dir, token, api_key, expected_owner, now, workdir):
    course = load_course_config()
    config = load_analysis_config()
    owner, name, team = validate_inputs(repo, tag, expected_owner, course)

    clone_dir = Path(workdir) / 'repo.git'
    clone_bare(repo, token, clone_dir)
    if tag not in tags_by_creation(clone_dir):
        raise Ignored("el tag no existe en el repo")
    tag_range = latest_tag_range(clone_dir, tag)
    if tag_range is None:
        raise Ignored("el tag no es el último del repo")

    notices = []
    repo_state = state.load(reports_dir, repo)
    previous = repo_state.get(tag)
    status = state.classify(repo_state, tag, tag_range.tag_sha)
    if status == state.ALREADY_DONE:
        raise Ignored("el tag ya fue analizado")
    if status == state.MOVED:
        notices.append(f"Tag movido: antes apuntaba a `{previous['sha'][:8]}` y ahora a "
                       f"`{tag_range.tag_sha[:8]}`. Este reporte reemplaza al anterior.")

    output = run_analysis(AnalysisInput(
        repo_dir=clone_dir, repo=repo, team=team, tag_range=tag_range, course=course,
        config=config, now=now, github=GitHubClient(token), owner=owner, name=name,
        api_key=api_key, notices=notices,
    ))
    destination = report_path(reports_dir, course, team, tag)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(output.markdown, encoding='utf-8')
    state.record(reports_dir, repo, tag, tag_range.tag_sha,
                 destination.relative_to(reports_dir), now, output.ai_complete)
    return output.ai_complete


def write_error_log(reports_dir, repo, now):
    safe_repo = re.sub(r'[^A-Za-z0-9._-]', '_', repo or 'desconocido')
    path = Path(reports_dir) / 'errores' / safe_repo / f"{now:%Y%m%dT%H%M%S}.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(traceback.format_exc(), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description='Analiza el último tag de un repo de equipo (CI).')
    parser.add_argument('--repo', required=True)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--reportes', required=True, help='Worktree de la rama reportes.')
    args = parser.parse_args(argv)

    now = datetime.now(timezone.utc)
    token = os.environ.get('GH_TOKEN', '')
    api_key = os.environ.get('GEMINI_API_KEY', '')
    if not token or not api_key:
        print("ERROR: faltan credenciales en el entorno.")
        return 1
    try:
        with tempfile.TemporaryDirectory() as workdir:
            ai_complete = analyze_latest_tag(
                args.repo, args.tag, args.reportes, token, api_key,
                os.environ.get('GITHUB_REPOSITORY_OWNER'), now, workdir,
            )
    except Ignored as reason:
        print(f"Sin análisis: {reason}.")
        return 0
    except Exception:
        write_error_log(args.reportes, args.repo, now)
        print("ERROR: el análisis falló. El detalle quedó en la rama reportes.")
        return 1
    print("OK: reporte generado." if ai_complete else "OK: reporte generado sin análisis IA.")
    return 0


if __name__ == '__main__':
    sys.exit(main())
