import re
from dataclasses import dataclass, field
from datetime import datetime
from steamdistics.gitrepo import git
from steamdistics.layers import map_layer, is_generated

FIELD_SEP = '\x1f'
RECORD_SEP = '\x1e'
TRAILER_SEP = '\x1d'
COMMIT_MARKER = f'{RECORD_SEP}COMMIT{FIELD_SEP}'

HUNK_HEADER = re.compile(r'^@@ -\d+(?:,(\d+))? \+\d+(?:,(\d+))? @@')
CONTACT = re.compile(r'^\s*(.*?)\s*<([^>]+)>\s*$')
REVERT_SUBJECT = re.compile(r'^revert\b', re.IGNORECASE)


@dataclass
class FileChange:
    path: str
    layer: str
    generated: bool
    added: int = 0
    deleted: int = 0
    patch: list = field(default_factory=list)


@dataclass
class Commit:
    sha: str
    author_name: str
    author_email: str
    date: datetime
    subject: str
    co_authors: list = field(default_factory=list)
    files: list = field(default_factory=list)

    @property
    def is_revert(self):
        return bool(REVERT_SUBJECT.match(self.subject))

    @property
    def counted_files(self):
        return [f for f in self.files if not f.generated]

    @property
    def added(self):
        return sum(f.added for f in self.counted_files)

    @property
    def deleted(self):
        return sum(f.deleted for f in self.counted_files)


@dataclass(frozen=True)
class MergeCommit:
    sha: str
    author_name: str
    author_email: str
    subject: str


def parse_contact(raw):
    match = CONTACT.match(raw)
    if not match:
        return None
    return match.group(1), match.group(2).strip()


def _canonical_contacts(repo_dir, contacts, mailmap_file):
    unique = sorted({f"{name} <{email}>" for name, email in contacts})
    if not unique:
        return {}
    output = git(repo_dir, 'check-mailmap', *unique, mailmap_file=mailmap_file)
    resolved = {}
    for original, canonical in zip(unique, output.splitlines()):
        parsed = parse_contact(canonical)
        if parsed:
            resolved[original] = parsed
    return resolved


def _read_metadata(repo_dir, rev_range, mailmap_file):
    fmt = FIELD_SEP.join(['%H', '%aN', '%aE', '%aI', '%s',
                          f'%(trailers:key=Co-authored-by,valueonly,separator=%x1d)']) + '%x1e'
    output = git(repo_dir, 'log', '--no-merges', f'--format={fmt}', rev_range, '--',
                 mailmap_file=mailmap_file)
    commits = []
    for record in output.split(RECORD_SEP):
        record = record.strip('\n')
        if not record:
            continue
        sha, name, email, date, subject, trailers = record.split(FIELD_SEP, 5)
        co_authors = [c for c in (parse_contact(t) for t in trailers.split(TRAILER_SEP)) if c]
        commits.append(Commit(
            sha=sha, author_name=name.strip(), author_email=email.strip().lower(),
            date=datetime.fromisoformat(date), subject=subject.strip(), co_authors=co_authors,
        ))
    return commits


def parse_patch(text, config):
    files = []
    current = None
    pending_old_path = None
    old_left = new_left = 0
    for line in text.split('\n'):
        if old_left > 0 or new_left > 0:
            if line.startswith('\\'):
                continue
            if line.startswith('-'):
                old_left -= 1
                _count(current, line, 'deleted')
            elif line.startswith('+'):
                new_left -= 1
                _count(current, line, 'added')
            else:
                old_left -= 1
                new_left -= 1
            continue
        if line.startswith('diff --git '):
            current, pending_old_path = None, None
        elif line.startswith('--- '):
            pending_old_path = line[6:].rstrip('\t') if line.startswith('--- a/') else None
        elif line.startswith('+++ '):
            path = line[6:].rstrip('\t') if line.startswith('+++ b/') else pending_old_path
            current = FileChange(path, map_layer(path, config), is_generated(path, config)) if path else None
            if current:
                files.append(current)
        elif current and (match := HUNK_HEADER.match(line)):
            old_left = int(match.group(1)) if match.group(1) is not None else 1
            new_left = int(match.group(2)) if match.group(2) is not None else 1
            if not current.generated:
                current.patch.append(line)
    return files


def _count(file_change, line, attribute):
    if file_change is None or file_change.generated:
        return
    file_change.patch.append(line)
    if line[1:].strip():
        setattr(file_change, attribute, getattr(file_change, attribute) + 1)


def _read_patches(repo_dir, rev_range, config):
    output = git(repo_dir, 'log', '--no-merges', '-w', '-M', '--unified=0', '--patch',
                 f'--format={COMMIT_MARKER}%H', rev_range, '--')
    patches = {}
    for chunk in output.split(COMMIT_MARKER)[1:]:
        sha, _, body = chunk.partition('\n')
        patches[sha.strip()] = parse_patch(body, config)
    return patches


def read_commits(repo_dir, rev_range, config, mailmap_file=None):
    commits = _read_metadata(repo_dir, rev_range, mailmap_file)
    patches = _read_patches(repo_dir, rev_range, config)
    contacts = _canonical_contacts(
        repo_dir, [c for commit in commits for c in commit.co_authors], mailmap_file,
    )
    for commit in commits:
        commit.files = patches.get(commit.sha, [])
        commit.co_authors = [
            (name, email.lower()) for name, email in
            (contacts.get(f"{n} <{e}>", (n, e)) for n, e in commit.co_authors)
        ]
    return sorted(commits, key=lambda c: c.date)


def read_merges(repo_dir, rev_range, mailmap_file=None):
    fmt = FIELD_SEP.join(['%H', '%aN', '%aE', '%s']) + '%x1e'
    output = git(repo_dir, 'log', '--merges', f'--format={fmt}', rev_range, '--',
                 mailmap_file=mailmap_file)
    merges = []
    for record in output.split(RECORD_SEP):
        record = record.strip('\n')
        if record:
            sha, name, email, subject = record.split(FIELD_SEP, 3)
            merges.append(MergeCommit(sha, name.strip(), email.strip().lower(), subject.strip()))
    return merges
