import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from steamdistics.config import load_analysis_config, load_course_config
from steamdistics.gitlog import Commit, FileChange

ANALYSIS_CONFIG = load_analysis_config()
COURSE_CONFIG = load_course_config()


class RepoBuilder:
    def __init__(self, path):
        self.path = Path(path)
        self.path.mkdir(parents=True, exist_ok=True)
        self._git('init', '-q', '-b', 'main')
        self._git('config', 'user.name', 'Bot')
        self._git('config', 'user.email', 'bot@example.com')
        self._git('config', 'commit.gpgsign', 'false')
        self._git('config', 'tag.gpgsign', 'false')

    def _git(self, *args, env=None):
        result = subprocess.run(['git', '-C', str(self.path), *args], capture_output=True, text=True,
                                env={**os.environ, **(env or {})})
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        return result.stdout.strip()

    def commit(self, files, message, author=('Ana Gomez', 'ana@example.com'),
               date='2026-05-01T10:00:00+00:00', co_authors=()):
        for relative, content in files.items():
            target = self.path / relative
            if content is None:
                target.unlink()
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
        body = message
        if co_authors:
            body += '\n\n' + '\n'.join(f'Co-authored-by: {n} <{e}>' for n, e in co_authors)
        self._git('add', '-A')
        self._git('commit', '-q', '--allow-empty', '-m', body, env={
            'GIT_AUTHOR_NAME': author[0], 'GIT_AUTHOR_EMAIL': author[1],
            'GIT_AUTHOR_DATE': date, 'GIT_COMMITTER_DATE': date,
        })
        return self._git('rev-parse', 'HEAD')

    def tag(self, name, ref='HEAD', date='2026-05-01T10:00:00+00:00', force=False):
        args = ['tag', '-a', name, ref, '-m', name] + (['-f'] if force else [])
        self._git(*args, env={'GIT_COMMITTER_DATE': date})

    def branch(self, name, start='HEAD'):
        self._git('checkout', '-q', '-b', name, start)

    def checkout(self, name):
        self._git('checkout', '-q', name)

    def merge(self, branch, author=('Ana Gomez', 'ana@example.com'), date='2026-05-01T10:00:00+00:00'):
        self._git('merge', '-q', '--no-ff', branch, '-m', f'Merge branch {branch}', env={
            'GIT_AUTHOR_NAME': author[0], 'GIT_AUTHOR_EMAIL': author[1],
            'GIT_AUTHOR_DATE': date, 'GIT_COMMITTER_DATE': date,
        })


def make_commit(sha='a' * 40, name='Ana Gomez', email='ana@example.com',
                date='2026-05-01T10:00:00+00:00', subject='agrega algo', co_authors=(), files=()):
    return Commit(sha=sha, author_name=name, author_email=email, date=datetime.fromisoformat(date),
                  subject=subject, co_authors=list(co_authors), files=list(files))


def make_change(path, layer, added, deleted, patch=(), generated=False):
    return FileChange(path=path, layer=layer, generated=generated, added=added, deleted=deleted,
                      patch=list(patch))


def utc(text):
    return datetime.fromisoformat(text).astimezone(timezone.utc)
