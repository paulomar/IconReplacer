"""Factory and helpers for the external icon sources."""

from __future__ import annotations

import os
from collections.abc import Iterable, Sequence
from pathlib import Path

from iconreplacer.catalog.external_base import ExternalSourceBase, shutdown_pool
from iconreplacer.catalog.github_source import GitHubRepoSource, parse_repo, source_id_for
from iconreplacer.catalog.iconify_source import default_iconify_sources
from iconreplacer.catalog.local_source import LocalFolderSource, local_source_id
from iconreplacer.catalog.net import Transport

DEFAULT_GITHUB_REPOS: tuple[str, ...] = ("LaviMahal/WindowsIcons", "sameerasw/folder-icons")

__all__ = [
    "DEFAULT_GITHUB_REPOS",
    "add_local_folder",
    "build_external_sources",
    "github_source_id",
    "local_source_id",
    "parse_github_repo",
    "remove_local_folder",
    "shutdown_all",
]


def parse_github_repo(text: str) -> tuple[str, str]:
    """``owner/repo`` or ``https://github.com/owner/repo[.git]`` -> ``(owner, repo)``.

    Raises ``ValueError`` for anything else.
    """
    return parse_repo(text)


def github_source_id(owner: str, repo: str) -> str:
    return source_id_for(owner, repo)


def build_external_sources(
    *,
    network_allowed: bool,
    github_repos: Sequence[str] | None = None,
    local_folders: Iterable[Path] = (),
    transport: Transport | None = None,
) -> list[ExternalSourceBase]:
    """Default online sources + configured GitHub repositories + local folders.

    Invalid or duplicate repository references are skipped. ``github_repos=None`` uses
    the defaults; an empty list means no GitHub sources.
    """
    sources: list[ExternalSourceBase] = list(
        default_iconify_sources(network_allowed=network_allowed, transport=transport)
    )
    seen = {s.info.id for s in sources}
    for ref in DEFAULT_GITHUB_REPOS if github_repos is None else github_repos:
        try:
            owner, repo = parse_repo(ref)
        except ValueError:
            continue
        if source_id_for(owner, repo) in seen:
            continue
        gh = GitHubRepoSource(owner, repo, network_allowed=network_allowed, transport=transport)
        seen.add(gh.info.id)
        sources.append(gh)
    for folder in local_folders:
        if local_source_id(Path(folder)) not in seen:
            local = LocalFolderSource(folder)
            seen.add(local.info.id)
            sources.append(local)
    return sources


def add_local_folder(sources: list[ExternalSourceBase], path: Path | str) -> LocalFolderSource:
    """Append a local folder source (or return the existing one for that folder)."""
    folder = Path(os.path.abspath(path))
    sid = local_source_id(folder)
    for s in sources:
        if s.info.id == sid and isinstance(s, LocalFolderSource):
            return s
    source = LocalFolderSource(folder)
    sources.append(source)
    return source


def remove_local_folder(sources: list[ExternalSourceBase], path_or_id: Path | str) -> bool:
    """Remove a local folder source by folder path or source id; True when removed."""
    wanted = {str(path_or_id), local_source_id(Path(path_or_id))}
    for s in sources:
        if isinstance(s, LocalFolderSource) and s.info.id in wanted:
            sources.remove(s)
            return True
    return False


def shutdown_all(sources: Iterable[ExternalSourceBase] = ()) -> None:
    """Fast shutdown: close ``sources``, cancel queued work, never wait for in-flight HTTP.

    Worker threads are daemons, so a request blocked on the network cannot delay exit.
    """
    for s in sources:
        s.close()
    shutdown_pool()
