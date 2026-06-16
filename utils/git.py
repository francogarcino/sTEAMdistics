import subprocess
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


def get_git_stats(commit_range, collect_diffs=False):
    by_email = {}
    name_counts = defaultdict(lambda: defaultdict(int))

    def ensure(email):
        if email not in by_email:
            by_email[email] = empty_author_entry()
        return by_email[email]

    def flush_patch(email, lines):
        if collect_diffs and email and lines:
            entry = ensure(email)
            if len(entry['diff_summary']) < MAX_DIFFS_PER_AUTHOR:
                patch = '\n'.join(lines).strip()
                if patch:
                    entry['diff_summary'].append(patch[:MAX_DIFF_CHARS])

    cmd = ["git", "log", "--no-merges", "-M", "--patch",
           "--format=COMMIT|||%an|||%ae|||%H|||%s", commit_range]

    current_email = None
    current_file = None
    pending_old   = None   # filepath del lado --- (para archivos eliminados)
    patch_lines   = []

    for line in run(cmd).split('\n'):
        if line.startswith('COMMIT|||'):
            flush_patch(current_email, patch_lines)
            patch_lines = []
            parts = line.split('|||', 4)
            if len(parts) == 5:
                _, name, email, _, message = (p.strip() for p in parts)
                current_email = email or None
                current_file  = None
                pending_old   = None
                if current_email:
                    name_counts[current_email][name] += 1
                    if 'merge' not in message.lower():
                        ensure(current_email)['commits'].append(message)

        elif line.startswith('diff --git '):
            current_file = None
            pending_old  = None

        elif line.startswith('--- a/'):
            pending_old = line[6:].strip()

        elif line.startswith('+++ b/'):
            current_file = line[6:].strip()
            pending_old  = None

        elif line.startswith('+++ /dev/null'):
            current_file = pending_old   # archivo eliminado: usamos el path del lado ---
            pending_old  = None

        elif current_email and current_file:
            if line.startswith('+') and not line.startswith('+++'):
                if line[1:].strip():     # ignora líneas en blanco
                    s = ensure(current_email)
                    s['added'] += 1
                    s['packages'][map_file_to_package(current_file)]['added'] += 1
                if collect_diffs:
                    patch_lines.append(line)
            elif line.startswith('-') and not line.startswith('---'):
                if line[1:].strip():     # ignora líneas en blanco
                    s = ensure(current_email)
                    s['deleted'] += 1
                    s['packages'][map_file_to_package(current_file)]['deleted'] += 1
                if collect_diffs:
                    patch_lines.append(line)
            elif collect_diffs and line and not line.startswith('\\'):
                patch_lines.append(line)

    flush_patch(current_email, patch_lines)

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
