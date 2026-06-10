import subprocess
import re
from collections import defaultdict
from utils.config import PACKAGES, PACKAGE_PATTERNS, MAX_DIFFS_PER_AUTHOR, MAX_DIFF_CHARS


def run(cmd):
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Comando falló:\n{cmd}\n\nSTDERR:\n{result.stderr}")
    return result.stdout.strip()


def map_file_to_package(filepath):
    for pkg, matches in PACKAGE_PATTERNS:
        if matches(filepath):
            return pkg
    return 'utils/otros'


def empty_author_entry():
    return {
        'added': 0,
        'deleted': 0,
        'packages': {pkg: {'added': 0, 'deleted': 0} for pkg in PACKAGES},
        'commits': [],
        'diff_summary': [],
    }


def same_person(a, b):
    if a.lower().replace(' ', '') == b.lower().replace(' ', ''):
        return True
    a_tokens = set(a.lower().split())
    b_tokens = set(b.lower().split())
    return a_tokens <= b_tokens or b_tokens <= a_tokens


def merge_stats(target, source):
    target['added'] += source['added']
    target['deleted'] += source['deleted']
    target['commits'].extend(source['commits'])
    target['diff_summary'].extend(source['diff_summary'])
    target['diff_summary'] = target['diff_summary'][:MAX_DIFFS_PER_AUTHOR]
    for p in PACKAGES:
        target['packages'][p]['added'] += source['packages'][p]['added']
        target['packages'][p]['deleted'] += source['packages'][p]['deleted']


def get_sorted_tags():
    output = run(["git", "tag", "--sort=creatordate"])
    return [t for t in output.split('\n') if t.strip()]


def _collect_patches(commit_range):
    patch_cmd = ["git", "log", "--no-merges", "--stat", "--patch", "--format=COMMIT|||%ae|||%H", commit_range]
    patches = {}
    current_hash = None
    current_lines = []
    for line in run(patch_cmd).split('\n'):
        if line.startswith('COMMIT|||'):
            if current_hash and current_lines:
                patches[current_hash] = '\n'.join(current_lines).strip()
            parts = line.split('|||', 2)
            current_hash = parts[2] if len(parts) == 3 else None
            current_lines = []
        elif current_hash is not None:
            current_lines.append(line)
    if current_hash and current_lines:
        patches[current_hash] = '\n'.join(current_lines).strip()
    return patches


def get_git_stats(commit_range, collect_diffs=False):
    by_email = {}
    name_counts = defaultdict(lambda: defaultdict(int))

    def ensure(email):
        if email not in by_email:
            by_email[email] = empty_author_entry()
        return by_email[email]

    log_cmd = ["git", "log", "--no-merges", "--format=%an|||%ae|||%s", commit_range]
    for line in run(log_cmd).split('\n'):
        parts = line.split('|||', 2)
        if len(parts) == 3:
            name, email, message = (p.strip() for p in parts)
            if email:
                name_counts[email][name] += 1
                if 'merge' not in message.lower():
                    ensure(email)['commits'].append(message)

    patches = _collect_patches(commit_range) if collect_diffs else {}

    numstat_cmd = ["git", "log", "--no-merges", "--numstat", "--format=COMMIT|||%ae|||%H", commit_range]
    current_email = None
    for line in run(numstat_cmd).split('\n'):
        if line.startswith('COMMIT|||'):
            parts = line.split('|||', 2)
            if len(parts) == 3:
                current_email, commit_hash = parts[1], parts[2]
                entry = ensure(current_email)
                if collect_diffs and len(entry['diff_summary']) < MAX_DIFFS_PER_AUTHOR:
                    diff = patches.get(commit_hash, '')
                    if diff:
                        entry['diff_summary'].append(diff[:MAX_DIFF_CHARS])
        elif line and current_email and '\t' in line:
            parts = line.split('\t', 2)
            if len(parts) == 3 and parts[0] != '-' and parts[1] != '-':
                try:
                    added, deleted, filepath = int(parts[0]), int(parts[1]), parts[2].strip()
                    s = ensure(current_email)
                    s['added'] += added
                    s['deleted'] += deleted
                    pkg = map_file_to_package(filepath)
                    s['packages'][pkg]['added'] += added
                    s['packages'][pkg]['deleted'] += deleted
                except ValueError:
                    pass

    raw_stats = {}
    for email, data in by_email.items():
        canonical = max(name_counts[email], key=lambda n: name_counts[email][n])
        if canonical not in raw_stats:
            raw_stats[canonical] = data
        else:
            merge_stats(raw_stats[canonical], data)

    final_stats = {}
    for name in sorted(raw_stats.keys(), key=len, reverse=True):
        match = next((t for t in final_stats if same_person(name, t)), None)
        if match:
            merge_stats(final_stats[match], raw_stats[name])
        else:
            final_stats[name] = raw_stats[name]

    return final_stats
