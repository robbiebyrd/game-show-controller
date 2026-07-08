from __future__ import annotations
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import yaml

log = logging.getLogger(__name__)

SHOWS_DIR = "shows"  # default folder that holds hot-loadable show configs
_SUFFIXES = (".yml", ".yaml")


@dataclass(frozen=True)
class ShowEntry:
    filename: str  # name relative to the shows dir, e.g. "trivia.yml"
    name: str      # display name: the show's `name`, else the filename stem


def _read_show_name(path: str) -> Optional[str]:
    """Best-effort read of the ``show.name`` from a config file; None on failure."""
    try:
        with open(path) as f:
            raw = yaml.safe_load(f) or {}
        name = (raw.get("show") or {}).get("name")
        return str(name) if name else None
    except (OSError, ValueError, yaml.YAMLError) as exc:
        log.warning("Could not read show name from %s (%s)", path, exc)
        return None


def list_shows(shows_dir: Optional[str] = None) -> list[ShowEntry]:
    """Enumerate show configs in ``shows_dir`` (default ``SHOWS_DIR``).

    Returns entries sorted by filename. Non-YAML files are ignored; a file whose
    metadata can't be read still appears, with its name falling back to the stem.
    A missing directory yields an empty list.
    """
    directory = shows_dir or SHOWS_DIR
    if not os.path.isdir(directory):
        return []
    entries: list[ShowEntry] = []
    for filename in sorted(os.listdir(directory)):
        if not filename.endswith(_SUFFIXES):
            continue
        name = _read_show_name(os.path.join(directory, filename)) or Path(filename).stem
        entries.append(ShowEntry(filename=filename, name=name))
    return entries
