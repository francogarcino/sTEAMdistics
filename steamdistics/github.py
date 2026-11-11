import json
import re
import urllib.error
import urllib.parse
import urllib.request

API_URL = 'https://api.github.com'
MAX_PAGES = 10
REMOTE = re.compile(r'(?:git@github\.com:|https://github\.com/)([^/]+)/(.+?)(?:\.git)?/?$')


class GitHubError(RuntimeError):
    pass


def parse_remote(url):
    match = REMOTE.match(url.strip())
    if not match:
        raise GitHubError(f"No se pudo interpretar el remoto de GitHub: {url}")
    return match.group(1), match.group(2)


class GitHubClient:
    def __init__(self, token, api_url=API_URL, opener=urllib.request.urlopen):
        self.token = token
        self.api_url = api_url
        self.opener = opener

    def get(self, path, **params):
        query = f"?{urllib.parse.urlencode(params)}" if params else ''
        request = urllib.request.Request(f"{self.api_url}{path}{query}", headers={
            'Accept': 'application/vnd.github+json',
            'X-GitHub-Api-Version': '2022-11-28',
            'User-Agent': 'sTEAMdistics',
            **({'Authorization': f'Bearer {self.token}'} if self.token else {}),
        })
        try:
            with self.opener(request, timeout=30) as response:
                return json.loads(response.read())
        except urllib.error.HTTPError as error:
            error.close()
            raise GitHubError(f"GitHub respondió {error.code} en {path}") from error
        except urllib.error.URLError as error:
            raise GitHubError(f"No se pudo conectar con GitHub ({path})") from error

    def paginate(self, path, key=None, **params):
        items = []
        for page in range(1, MAX_PAGES + 1):
            data = self.get(path, per_page=100, page=page, **params)
            batch = data[key] if key else data
            items.extend(batch)
            if len(batch) < 100:
                break
        return items

    def commit_logins(self, owner, repo, head_sha, base_sha=None):
        if base_sha:
            commits = self.paginate(f"/repos/{owner}/{repo}/compare/{base_sha}...{head_sha}", key='commits')
        else:
            commits = self.paginate(f"/repos/{owner}/{repo}/commits", sha=head_sha)
        return {c['sha']: c['author']['login'] for c in commits if c.get('author')}

    def issues(self, owner, repo):
        return [i for i in self.paginate(f"/repos/{owner}/{repo}/issues", state='all')
                if 'pull_request' not in i]

    def issue_closer(self, owner, repo, number):
        closed_by = self.get(f"/repos/{owner}/{repo}/issues/{number}").get('closed_by')
        return closed_by['login'] if closed_by else None

    def team_members(self, org, team_slug):
        try:
            return [m['login'] for m in self.paginate(f"/orgs/{org}/teams/{team_slug}/members")]
        except GitHubError:
            return None
