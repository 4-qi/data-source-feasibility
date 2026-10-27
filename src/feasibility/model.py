from dataclasses import dataclass, field
import hashlib


@dataclass
class Record:
    source: str
    kind: str
    key: str | None
    text: str | None
    parent: str | None = None
    created: str | int | None = None
    updated: str | int | None = None
    author_type: str | None = None
    fields: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def fingerprint(self):
        if self.key is None:
            return None
        return hashlib.sha256(f"{self.source}:{self.kind}:{self.key}".encode()).hexdigest()


@dataclass
class Collected:
    records: list = field(default_factory=list)
    observations: list = field(default_factory=list)
    excluded: dict = field(default_factory=dict)
    repeat_config: dict = field(default_factory=dict)
