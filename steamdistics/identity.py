import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field

NOREPLY = re.compile(r'^(?:\d+\+)?([^@]+)@users\.noreply\.github\.com$', re.IGNORECASE)


@dataclass
class Member:
    name: str
    login: str | None = None
    emails: set = field(default_factory=set)
    authored: list = field(default_factory=list)
    co_authored: list = field(default_factory=list)
    merges: list = field(default_factory=list)

    @property
    def has_activity(self):
        return bool(self.authored or self.co_authored or self.merges)


def normalize_name(name):
    ascii_name = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode()
    return ' '.join(ascii_name.lower().split())


def login_from_email(email):
    match = NOREPLY.match(email)
    return match.group(1).lower() if match else None


class _UnionFind:
    def __init__(self):
        self.parent = {}

    def find(self, node):
        self.parent.setdefault(node, node)
        while self.parent[node] != node:
            self.parent[node] = self.parent[self.parent[node]]
            node = self.parent[node]
        return node

    def union(self, a, b):
        self.parent[self.find(a)] = self.find(b)


def _link_contact(uf, name, email, login=None):
    email_node = f'e:{email}'
    uf.find(email_node)
    normalized = normalize_name(name or '')
    if len(normalized.split()) >= 2:
        uf.union(f'n:{normalized}', email_node)
    for candidate in (login, login_from_email(email)):
        if candidate:
            uf.union(f'l:{candidate.lower()}', email_node)
    return email_node


def group_members(commits, merges=(), logins_by_sha=None, roster=None):
    logins_by_sha = logins_by_sha or {}
    uf = _UnionFind()
    names_by_node = {}

    def register(name, email, login=None):
        node = _link_contact(uf, name, email, login)
        names_by_node.setdefault(node, Counter())[name] += 1
        return node

    author_nodes = {c.sha: register(c.author_name, c.author_email, logins_by_sha.get(c.sha)) for c in commits}
    co_author_nodes = {c.sha: [register(n, e) for n, e in c.co_authors] for c in commits}
    merge_nodes = [(m, register(m.author_name, m.author_email)) for m in merges]
    for login in roster or ():
        uf.find(f'l:{login.lower()}')

    groups = {}

    def member_for(node):
        root = uf.find(node)
        if root not in groups:
            groups[root] = Member(name='')
        return groups[root]

    for commit in commits:
        member_for(author_nodes[commit.sha]).authored.append(commit)
        author_root = uf.find(author_nodes[commit.sha])
        for node in co_author_nodes[commit.sha]:
            if uf.find(node) != author_root:
                member_for(node).co_authored.append(commit)
    for merge, node in merge_nodes:
        member_for(node).merges.append(merge)
    for login in roster or ():
        member_for(f'l:{login.lower()}')

    name_counts = {}
    for node in list(uf.parent):
        root = uf.find(node)
        member = member_for(node) if root in groups else None
        if member is None:
            continue
        if node.startswith('e:'):
            member.emails.add(node[2:])
            name_counts.setdefault(root, Counter()).update(names_by_node.get(node, Counter()))
        elif node.startswith('l:') and not member.login:
            member.login = node[2:]

    for root, member in groups.items():
        counts = name_counts.get(root)
        member.name = counts.most_common(1)[0][0] if counts else (member.login or 'desconocido')

    return sorted(groups.values(), key=lambda m: normalize_name(m.name))
