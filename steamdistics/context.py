import re
import string

TRUNCATED_MARK = '[... diff recortado por presupuesto]'


def assign_aliases(members):
    letters = string.ascii_uppercase
    return [
        f"Integrante {letters[i % 26]}{i // 26 or ''}" for i in range(len(members))
    ]


def _identity_terms(member):
    terms = {member.name, *member.emails}
    if member.login:
        terms.add(member.login)
    for commit in member.authored:
        terms.add(commit.author_name)
    for commit in member.authored + member.co_authored:
        for name, email in commit.co_authors:
            if email in member.emails:
                terms.update({name, email})
    return {t for t in terms if t and len(t) >= 3}


def build_scrubber(members, aliases):
    replacements = {}
    for member, alias in zip(members, aliases):
        for term in _identity_terms(member):
            replacements.setdefault(term.lower(), alias)
    if not replacements:
        return lambda text: text
    pattern = re.compile(
        r'\b(?:' + '|'.join(re.escape(t) for t in sorted(replacements, key=len, reverse=True)) + r')\b',
        re.IGNORECASE,
    )
    return lambda text: pattern.sub(lambda m: replacements[m.group(0).lower()], text)


def commit_block(commit):
    lines = [f'=== {commit.sha[:8]} {commit.date:%Y-%m-%d %H:%M} "{commit.subject}"']
    if commit.co_authors:
        lines.append('(commit en pareja)')
    for change in commit.counted_files:
        lines.append(f'--- {change.path} [{change.layer}]')
        lines.extend(change.patch)
    if not commit.counted_files:
        lines.append('(sin cambios de código relevantes)')
    return '\n'.join(lines)


def fit_budget(blocks, budget):
    total = sum(len(b) for b in blocks)
    if total <= budget:
        return list(blocks), False
    cap = _water_level(sorted(len(b) for b in blocks), budget)
    fitted = [b if len(b) <= cap else b[:max(cap - len(TRUNCATED_MARK) - 1, 0)] + '\n' + TRUNCATED_MARK
              for b in blocks]
    return fitted, True


def _water_level(sorted_sizes, budget):
    remaining = budget
    count = len(sorted_sizes)
    for index, size in enumerate(sorted_sizes):
        share = remaining // (count - index)
        if size > share:
            return share
        remaining -= size
    return remaining


def member_diff(member, budget):
    blocks = [commit_block(c) for c in sorted(member.authored, key=lambda c: c.date)]
    fitted, truncated = fit_budget(blocks, budget)
    return '\n\n'.join(fitted), truncated
