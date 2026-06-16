import json
import re
import urllib.request
import urllib.error
from utils.git import run


def _parse_github_remote(url):
    url = url.strip()
    ssh   = re.match(r'git@github\.com:([^/]+)/(.+?)(?:\.git)?$', url)
    https = re.match(r'https://github\.com/([^/]+)/(.+?)(?:\.git)?$', url)
    m = ssh or https
    if not m:
        raise ValueError(f"No se pudo parsear la URL de GitHub: {url}")
    return m.group(1), m.group(2)


def fetch_open_issues(token=None):
    remote_url = run(["git", "remote", "get-url", "origin"])
    owner, repo = _parse_github_remote(remote_url)

    url = f"https://api.github.com/repos/{owner}/{repo}/issues?state=open&per_page=100"
    headers = {'Accept': 'application/vnd.github+json', 'User-Agent': 'sTEAMdistics'}
    if token:
        headers['Authorization'] = f'Bearer {token}'

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())
            return [i for i in data if 'pull_request' not in i]
    except urllib.error.HTTPError as e:
        if e.code in (401, 403, 404):
            raise RuntimeError(
                f"No se pudo acceder a los issues ({e.code}). "
                "Para repos privados configurá: git config sTEAMdistics.gh-token \"TU_TOKEN\""
            )
        raise RuntimeError(f"Error al obtener issues de GitHub: {e}")


def format_issues(issues):
    if not issues:
        return "No hay issues abiertos."
    lines = []
    for issue in issues:
        body = (issue.get('body') or '').strip().replace('\n', ' ')
        if len(body) > 200:
            body = body[:200] + '...'
        line = f"#{issue['number']}: {issue['title']}"
        if body:
            line += f" — {body}"
        lines.append(line)
    return "\n".join(lines)
