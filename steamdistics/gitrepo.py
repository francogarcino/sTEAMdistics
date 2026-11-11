import subprocess
from dataclasses import dataclass
from datetime import datetime

TAG_PREFIX = 'refs/tags/'


class GitError(RuntimeError):
    pass


def git(repo_dir, *args, mailmap_file=None, env=None):
    cmd = ['git', '-C', str(repo_dir), '-c', 'core.quotePath=false', '-c', 'core.hooksPath=/dev/null']
    if mailmap_file:
        cmd += ['-c', f'mailmap.file={mailmap_file}']
    cmd += list(args)
    result = subprocess.run(
        cmd, capture_output=True, text=True, encoding='utf-8', errors='replace', env=env,
    )
    if result.returncode != 0:
        raise GitError(f"git {args[0]} falló ({result.returncode}): {result.stderr.strip()}")
    return result.stdout


@dataclass(frozen=True)
class TagRange:
    tag: str
    tag_sha: str
    tag_date: datetime
    previous: str | None
    previous_sha: str | None
    previous_date: datetime | None

    @property
    def rev_range(self):
        return f"{self.previous_sha}..{self.tag_sha}" if self.previous_sha else self.tag_sha

    @property
    def label(self):
        return f"{self.previous or 'inicio del repo'} → {self.tag}"


def tags_by_creation(repo_dir):
    output = git(repo_dir, 'for-each-ref', '--sort=creatordate', '--format=%(refname)', TAG_PREFIX)
    return [line[len(TAG_PREFIX):] for line in output.splitlines() if line.startswith(TAG_PREFIX)]


def _qualify(ref):
    return ref if ref == 'HEAD' else TAG_PREFIX + ref


def resolve_commit(repo_dir, ref):
    return git(repo_dir, 'rev-parse', '--verify', '--quiet', f'{_qualify(ref)}^{{commit}}').strip()


def commit_date(repo_dir, sha):
    return datetime.fromisoformat(git(repo_dir, 'log', '-1', '--format=%cI', sha).strip())


def build_range(repo_dir, end, start=None):
    end_sha = resolve_commit(repo_dir, end)
    start_sha = resolve_commit(repo_dir, start) if start else None
    return TagRange(
        tag=end,
        tag_sha=end_sha,
        tag_date=commit_date(repo_dir, end_sha),
        previous=start,
        previous_sha=start_sha,
        previous_date=commit_date(repo_dir, start_sha) if start_sha else None,
    )


def latest_tag_range(repo_dir, tag):
    tags = tags_by_creation(repo_dir)
    if not tags or tags[-1] != tag:
        return None
    return build_range(repo_dir, tag, tags[-2] if len(tags) > 1 else None)
