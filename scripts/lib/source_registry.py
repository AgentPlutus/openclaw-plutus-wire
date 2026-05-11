"""Source registry for Plutus Wire."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    label: str
    default_enabled: bool
    adapter_name: str
    adapter_args: tuple[str, ...] = ()
    requires_handle: bool = False
    detect_only: bool = False
    notes: str = ""

    @property
    def adapter_command(self) -> str:
        return " ".join((self.adapter_name, *self.adapter_args))


SOURCES: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        name="following",
        label="Following",
        default_enabled=True,
        adapter_name="timeline",
        adapter_args=("--type", "following"),
    ),
    SourceDefinition(
        name="for-you",
        label="For You",
        default_enabled=True,
        adapter_name="timeline",
        adapter_args=("--type", "for-you"),
    ),
    SourceDefinition(
        name="ai",
        label="AI home tab",
        default_enabled=False,
        adapter_name="timeline",
        adapter_args=("--type", "ai"),
        notes="Only enable when detected for the user's account.",
    ),
    SourceDefinition(
        name="likes",
        label="Likes",
        default_enabled=False,
        adapter_name="likes",
        requires_handle=True,
        notes="Requires the X handle selected by the user.",
    ),
    SourceDefinition(
        name="bookmarks",
        label="Bookmarks",
        default_enabled=False,
        adapter_name="bookmarks",
    ),
    SourceDefinition(
        name="home-tabs",
        label="Detected Home tabs",
        default_enabled=False,
        adapter_name="home-tabs",
        detect_only=True,
        notes="Discovery command used by setup; not an ingest source.",
    ),
)


def default_source_names() -> list[str]:
    return [source.name for source in SOURCES if source.default_enabled]


def source_by_name(name: str) -> SourceDefinition:
    for source in SOURCES:
        if source.name == name:
            return source
    raise KeyError(f"unknown source: {name}")


def normalize_sources(values: list[str] | None) -> list[str]:
    if not values:
        return default_source_names()
    names: list[str] = []
    for value in values:
        for part in value.split(","):
            name = part.strip().lower()
            if not name:
                continue
            source_by_name(name)
            if source_by_name(name).detect_only:
                raise ValueError(f"{name} is detection-only and cannot be ingested")
            if name not in names:
                names.append(name)
    return names


def opencli_args_for_source(name: str, *, limit: int, handle: str | None = None) -> list[str]:
    source = source_by_name(name)
    if source.detect_only:
        raise ValueError(f"{name} is detection-only")
    args = ["plutus-wire", source.adapter_name, *source.adapter_args]
    if source.adapter_name in {"timeline", "bookmarks", "likes"}:
        args.extend(["--limit", str(limit)])
    if source.requires_handle:
        if not handle:
            raise ValueError(f"{name} requires --handle")
        args.extend(["--handle", handle.lstrip("@")])
    args.extend(["--format", "json"])
    return args
