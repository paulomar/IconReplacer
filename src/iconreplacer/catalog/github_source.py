"""Icon source for a public GitHub repository that holds icon files."""

from __future__ import annotations

import hashlib
import json
import re
import time
from typing import Any
from urllib.parse import quote

from iconreplacer.catalog.categories import categorize, iter_tags
from iconreplacer.catalog.external_base import ExternalSourceBase
from iconreplacer.catalog.net import MAX_FILE_BYTES, MAX_INDEX_BYTES, HttpError, Transport
from iconreplacer.core.models import (
    IconEntry,
    IconKind,
    IconRef,
    RefKind,
    Section,
    SourceInfo,
)

API = "https://api.github.com"
RAW = "https://raw.githubusercontent.com"
HOSTS = ("api.github.com", "raw.githubusercontent.com")
NO_LICENSE = "No license declared - personal use at your own discretion"
MAX_ICON_BYTES = 2 * 1024 * 1024
# Extension preference when one icon exists in several formats.
EXT_ORDER = (".ico", ".svg", ".png", ".icns")
_FORMAT_DIRS = frozenset({"ico", "icos", "png", "pngs", "svg", "svgs", "icns"})
_OWNER = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})")
_REPO = re.compile(r"[A-Za-z0-9._-]{1,100}")
_GENERIC_DIRS = frozenset({"icons", "icon", "src", "assets", "images", "img", "resources"})


def parse_repo(text: str) -> tuple[str, str]:
    """Parse ``owner/repo`` or ``https://github.com/owner/repo[.git]`` strictly."""
    value = text.strip()
    m = re.fullmatch(
        r"(?:https://github\.com/)?([A-Za-z0-9-]{1,39})/([A-Za-z0-9._-]{1,100}?)(?:\.git)?/?",
        value,
    )
    if not m:
        raise ValueError(f"not a GitHub repository reference: {text!r}")
    owner, repo = m.group(1), m.group(2)
    if not _OWNER.fullmatch(owner) or not _REPO.fullmatch(repo) or repo in (".", ".."):
        raise ValueError(f"not a GitHub repository reference: {text!r}")
    return owner, repo


def source_id_for(owner: str, repo: str) -> str:
    return "gh-" + re.sub(r"[^a-z0-9]+", "-", f"{owner}-{repo}".lower()).strip("-")


def raw_url(owner: str, repo: str, branch: str, path: str) -> str:
    head = f"{RAW}/{quote(owner, safe='')}/{quote(repo, safe='')}"
    return f"{head}/{quote(branch, safe='/')}/{quote(path, safe='/')}"


def pick_files(files: list[tuple[str, int]]) -> list[tuple[str, int]]:
    """Filter by extension/size and dedupe by (directory without format folders, stem)."""
    best: dict[str, tuple[int, str, int]] = {}
    for path, size in files:
        dot = path.rfind(".")
        ext = path[dot:].lower() if dot > path.rfind("/") else ""
        if ext not in EXT_ORDER or size > MAX_ICON_BYTES:
            continue
        parts = path[:dot].split("/")
        folders = [p for p in parts[:-1] if p.casefold() not in _FORMAT_DIRS]
        key = "/".join([*folders, parts[-1]]).casefold()
        rank = EXT_ORDER.index(ext)
        current = best.get(key)
        if current is None or rank < current[0]:
            best[key] = (rank, path, size)
    return sorted(((p, s) for _, p, s in best.values()), key=lambda t: t[0].casefold())


def pretty_stem(stem: str) -> str:
    text = re.sub(r"[-_]+", " ", stem).strip()
    text = re.sub(r"\s+", " ", text)
    return text.title() if text == text.lower() else text


class GitHubRepoSource(ExternalSourceBase):
    def __init__(
        self,
        owner: str,
        repo: str,
        *,
        network_allowed: bool = True,
        transport: Transport | None = None,
    ) -> None:
        owner, repo = parse_repo(f"{owner}/{repo}")
        self.owner, self.repo = owner, repo
        self._license = NO_LICENSE
        self._branch = ""
        super().__init__(
            self._make_info(source_id_for(owner, repo), owner, repo),
            hosts=HOSTS,
            network_allowed=network_allowed,
            transport=transport,
        )

    def _make_info(self, sid: str, owner: str, repo: str) -> SourceInfo:
        return SourceInfo(
            id=sid,
            name=f"{owner}/{repo}",
            description=f"Icons from github.com/{owner}/{repo}",
            section=Section.ONLINE,
            license=self._license,
            requires_network=True,
        )

    # -- listing ------------------------------------------------------------
    def _refresh_task(self, force: bool) -> None:
        self._run_listing("index", self._fetch_index, self._build_entries, force=force, gen=None)

    def _get_json(self, url: str, max_bytes: int) -> Any:
        return json.loads(self._http.get(url, max_bytes=max_bytes, accept="application/json").body)

    def _fetch_index(self) -> dict[str, Any]:
        base = f"{API}/repos/{quote(self.owner, safe='')}/{quote(self.repo, safe='')}"
        meta = self._get_json(base, MAX_FILE_BYTES)
        branch = str(meta["default_branch"])
        lic = meta.get("license") or {}
        spdx = lic.get("spdx_id")
        license_name = None
        if spdx and spdx != "NOASSERTION":
            license_name = spdx
        elif lic.get("name"):
            license_name = str(lic["name"])
        tree = self._get_json(
            f"{base}/git/trees/{quote(branch, safe='')}?recursive=1", MAX_INDEX_BYTES
        )
        files = [
            [item["path"], int(item.get("size") or 0)]
            for item in tree["tree"]
            if item.get("type") == "blob"
        ]
        return {
            "branch": branch,
            "license": license_name,
            "truncated": bool(tree.get("truncated")),
            "files": [f for f in files if pick_files([(f[0], f[1])])],
        }

    def _build_entries(self, raw: dict[str, Any]) -> list[IconEntry]:
        branch = str(raw["branch"])
        self._branch = branch
        license_name = raw.get("license")
        self._license = str(license_name) if license_name else NO_LICENSE
        self._set_info(self._make_info(self._info.id, self.owner, self.repo))
        out: list[IconEntry] = []
        for path, _size in pick_files([(str(p), int(s)) for p, s in raw["files"]]):
            out.append(self._make_entry(branch, path))
        return out

    def _make_entry(self, branch: str, path: str) -> IconEntry:
        parts = path.split("/")
        stem = parts[-1].rsplit(".", 1)[0]
        folders = [
            p
            for p in parts[:-1]
            if p.casefold() not in _FORMAT_DIRS and p.casefold() not in _GENERIC_DIRS
        ]
        digest = hashlib.sha1(path.encode("utf-8")).hexdigest()[:16]  # noqa: S324
        return IconEntry(
            id=f"{self._info.id}:{digest}",
            name=pretty_stem(stem),
            source_id=self._info.id,
            ref=IconRef(RefKind.REMOTE, raw_url(self.owner, self.repo, branch, path)),
            categories=categorize(*folders, stem),
            tags=frozenset({*iter_tags(stem, *folders), self.owner.lower(), self.repo.lower()}),
            license=self._license,
            kind=IconKind.FULL,
        )

    # -- bytes --------------------------------------------------------------
    def _download(self, entry: IconEntry) -> bytes:
        url = self._http.check_url(entry.ref.location)
        return self._http.get(url, max_bytes=MAX_FILE_BYTES, accept="*/*").body

    def _describe_http(self, exc: HttpError) -> str:
        if exc.rate_limited:
            reset = exc.headers.get("x-ratelimit-reset", "")
            when = ""
            if reset.isdigit():
                when = f" (resets at {time.strftime('%H:%M', time.localtime(int(reset)))})"
            return f"GitHub rate limit reached{when}. Cached icons are still available."
        if exc.status == 404:
            return f"Repository {self.owner}/{self.repo} was not found."
        if exc.status == 403:
            return "GitHub denied the request (HTTP 403)."
        return f"GitHub request failed (HTTP {exc.status})."
