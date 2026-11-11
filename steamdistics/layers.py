from pathlib import PurePosixPath
from steamdistics.config import DEFAULT_LAYER


def map_layer(path, config):
    parts = PurePosixPath(path.lower()).parts
    directories = set(parts[:-1])
    stem = PurePosixPath(parts[-1]).stem if parts else ''
    for rule in config.rules:
        if directories & rule.segments:
            return rule.layer
        if rule.suffixes and stem.endswith(rule.suffixes):
            return rule.layer
    return DEFAULT_LAYER


def is_generated(path, config):
    return bool(config.generated_pattern.search(path))
