from collections import Counter
from dataclasses import dataclass, field
from datetime import timedelta


@dataclass
class MemberMetrics:
    commits: int = 0
    paired_commits: int = 0
    added: int = 0
    deleted: int = 0
    files_touched: int = 0
    layers: dict = field(default_factory=dict)
    commits_by_day: dict = field(default_factory=dict)
    late_share: dict = field(default_factory=dict)
    merges: int = 0
    reverts: int = 0

    @property
    def activity(self):
        return self.added + self.deleted

    @property
    def active_days(self):
        return len(self.commits_by_day)

    def layer_share(self, layer):
        if not self.activity:
            return 0
        added, deleted = self.layers.get(layer, (0, 0))
        return round((added + deleted) * 100 / self.activity)


def compute_member_metrics(member, tag_date, config):
    worked = member.authored + member.co_authored
    metrics = MemberMetrics(
        commits=len(member.authored),
        paired_commits=sum(1 for c in member.authored if c.co_authors) + len(member.co_authored),
        merges=len(member.merges),
        reverts=sum(1 for c in member.authored if c.is_revert),
    )
    layers = {layer: [0, 0] for layer in config.layers}
    files = set()
    day_counter = Counter()
    late_lines = Counter()
    for commit in worked:
        day_counter[commit.date.date().isoformat()] += 1
        for change in commit.counted_files:
            files.add(change.path)
            layers[change.layer][0] += change.added
            layers[change.layer][1] += change.deleted
        lines = commit.added + commit.deleted
        metrics.added += commit.added
        metrics.deleted += commit.deleted
        for hours in config.late_windows_hours:
            if tag_date - commit.date <= timedelta(hours=hours):
                late_lines[hours] += lines
    metrics.layers = {layer: tuple(values) for layer, values in layers.items()}
    metrics.files_touched = len(files)
    metrics.commits_by_day = dict(sorted(day_counter.items()))
    metrics.late_share = {
        hours: round(late_lines[hours] * 100 / metrics.activity) if metrics.activity else 0
        for hours in config.late_windows_hours
    }
    return metrics


def activity_shares(metrics_by_member):
    total = sum(m.activity for m in metrics_by_member.values())
    return {
        key: round(m.activity * 100 / total) if total else 0
        for key, m in metrics_by_member.items()
    }
