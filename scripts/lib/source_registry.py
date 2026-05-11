"""Source registry for Plutus Wire."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceDefinition:
    name: str
    label: str
    default_enabled: bool
    adapter_command: str
    notes: str = ""


SOURCES: tuple[SourceDefinition, ...] = (
    SourceDefinition(
        name="following",
        label="Following",
        default_enabled=True,
        adapter_command="timeline --type following",
    ),
    SourceDefinition(
        name="for-you",
        label="For You",
        default_enabled=True,
        adapter_command="timeline --type for-you",
    ),
    SourceDefinition(
        name="ai",
        label="AI home tab",
        default_enabled=False,
        adapter_command="timeline --type ai",
        notes="Only enable when detected for the user's account.",
    ),
    SourceDefinition(
        name="likes",
        label="Likes",
        default_enabled=False,
        adapter_command="likes",
    ),
    SourceDefinition(
        name="bookmarks",
        label="Bookmarks",
        default_enabled=False,
        adapter_command="bookmarks",
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
            if name not in names:
                names.append(name)
    return names
