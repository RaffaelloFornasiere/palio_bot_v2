"""Git-backed history & rollback for the data directory.

A small layer over `pygit2` that turns every session save into a git
commit and tags festival-day boundaries. Read paths:
    public webapp  -> `refs/palio/last_save`
    edit webapp    -> working tree
    agent          -> working tree

See `docs/refactor/03_history_and_rollback.md` for the full model.

Concurrency: all mutating operations are serialised by `_repo_lock` so
two concurrent FastAPI handlers can't race on `.git/index` or refs.
The lock is `threading.Lock` rather than `asyncio.Lock` because pygit2
calls are blocking C calls and FastAPI happily runs sync handlers on a
threadpool.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from zoneinfo import ZoneInfo

import pygit2

logger = logging.getLogger(__name__)


# Mutable ref that points to the last successful save. The public webapp
# reads from this; tags point to past values of it.
LAST_SAVE_REF = "refs/palio/last_save"

# Identity used for every commit. The human/source goes in trailers.
_AUTHOR_NAME = "palio-core"
_AUTHOR_EMAIL = "noreply@palio"

# Festival day boundary. Activity up to 04:59 stays in the previous day.
_FESTIVAL_DAY_CUTOFF_HOURS = 5
_FESTIVAL_TZ = ZoneInfo("Europe/Rome")


def festival_day(ts: datetime) -> str:
    """Return the festival-day string (YYYY-MM-DD) for a UTC timestamp."""
    local = ts.astimezone(_FESTIVAL_TZ)
    shifted = local - timedelta(hours=_FESTIVAL_DAY_CUTOFF_HOURS)
    return shifted.strftime("%Y-%m-%d")


@dataclass
class CommitInfo:
    sha: str
    summary: str
    ts: datetime
    source: Optional[str]
    committer: Optional[str]
    tool: Optional[str] = None


@dataclass
class HistoryEntry:
    """One row in `json_history` / `GET /api/history/{file}`.

    `kind` is "tag" for festival-day checkpoints or "save" for intra-day
    saves. `ref` is what the rollback endpoint takes.
    """
    kind: str
    ref: str
    summary: str
    ts: datetime


class HistoryService:
    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir).resolve()
        self._repo: Optional[pygit2.Repository] = None
        self._lock = threading.Lock()

    # ---------- init ----------

    def init_repo(self, tracked_files: List[Path]) -> None:
        """Initialise (or open) the git repo in `data_dir`.

        Idempotent. If the repo doesn't exist, creates it and seeds an
        initial commit of the currently-existing tracked files. The
        `last_save` ref is set to that initial commit.
        """
        with self._lock:
            if (self.data_dir / ".git").exists():
                self._repo = pygit2.Repository(str(self.data_dir))
                logger.info("history: opened existing repo at %s", self.data_dir)
                self._maybe_gc()
                return

            self.data_dir.mkdir(parents=True, exist_ok=True)
            self._repo = pygit2.init_repository(str(self.data_dir), bare=False)
            logger.info("history: initialised new repo at %s", self.data_dir)

            existing = [p for p in tracked_files if p.exists()]
            for p in existing:
                rel = p.resolve().relative_to(self.data_dir)
                self._repo.index.add(str(rel))
            self._repo.index.write()

            tree = self._repo.index.write_tree()
            sig = self._signature()
            sha = self._repo.create_commit(
                "HEAD", sig, sig, "seed: initial commit\n\nsource: bootstrap\n",
                tree, []
            )
            self._set_ref(LAST_SAVE_REF, sha)
            logger.info("history: seeded initial commit %s", str(sha)[:8])

    def _maybe_gc(self) -> None:
        """Best-effort housekeeping on startup. Cheap if nothing to do."""
        # pygit2 doesn't expose `gc --auto`; the closest is a manual repack,
        # but for the app's usage pattern (2 weeks/year) we don't even need
        # that. Skip; revisit if loose objects ever become a problem.
        return

    # ---------- write hook (per-tool-call commits) ----------

    def record_write(
        self,
        *,
        file_name: str,
        source: str,
        committer: Optional[str],
        session_id: Optional[str],
        tool: Optional[str] = None,
        summary: Optional[str] = None,
    ) -> Optional[str]:
        """Commit the currently-on-disk version of `file_name` as a single
        intra-session commit. Does NOT move `last_save` or create tags.

        Returns the new HEAD SHA, or `None` if nothing changed (tree
        identical to HEAD). Called from `SessionService.put` after
        `LocalFileStore.write_atomic` has placed the new content on disk.
        """
        repo = self._require_repo()
        with self._lock:
            path = self.data_dir / file_name
            if not path.exists():
                return None
            rel = str(path.relative_to(self.data_dir))
            repo.index.add(rel)
            repo.index.write()

            try:
                head_tree = repo.head.peel(pygit2.Commit).tree
            except (pygit2.GitError, KeyError):
                head_tree = None
            new_tree_oid = repo.index.write_tree()
            if head_tree is not None and new_tree_oid == head_tree.id:
                logger.debug("history: nothing to commit for %s", file_name)
                return None

            parents = [repo.head.target] if not repo.head_is_unborn else []
            header = summary or self._mechanical_summary([file_name])
            body = self._format_trailers(
                source=source, committer=committer, session=session_id,
                tool=tool, files=[file_name],
            )
            sig = self._signature()
            sha = repo.create_commit(
                "HEAD", sig, sig, f"{header}\n\n{body}", new_tree_oid, parents
            )
            logger.info("history: recorded write %s (%s, source=%s, tool=%s)",
                        str(sha)[:8], file_name, source, tool)
            return str(sha)

    # ---------- save (squash + move last_save + maybe daily-tag) ----------

    def finalize_save(
        self,
        *,
        source: str,
        committer: Optional[str],
        session_id: Optional[str],
        files_touched: List[str],
    ) -> Optional[str]:
        """Squash every commit between `last_save` and HEAD into one,
        move `last_save` to it, and lazy-create a daily tag if the
        festival day rolled over.

        Returns the squashed commit SHA, or `None` if there is nothing
        to save (HEAD == last_save).
        """
        repo = self._require_repo()
        with self._lock:
            last_save = self._read_ref(LAST_SAVE_REF)
            if last_save is None:
                # First save ever: just create one commit from HEAD's tree.
                if repo.head_is_unborn:
                    return None
                head_commit = repo.head.peel(pygit2.Commit)
                tree_oid = head_commit.tree.id
                parents: List = []
            else:
                head_sha = str(repo.head.target)
                if head_sha == last_save:
                    return None  # nothing to save
                head_commit = repo.head.peel(pygit2.Commit)
                tree_oid = head_commit.tree.id
                parents = [last_save]

            header = self._mechanical_summary(files_touched)
            body = self._format_trailers(
                source=source, committer=committer, session=session_id,
                files=files_touched,
            )
            sig = self._signature()
            # Create without updating any ref so pygit2 doesn't enforce the
            # "first parent must be current HEAD" rule. Then move HEAD and
            # last_save explicitly (squash semantics: bypass per-PUT commits).
            new_sha = repo.create_commit(
                None, sig, sig, f"{header}\n\n{body}", tree_oid, parents
            )
            repo.set_head(new_sha)

            # Lazy daily tag on the previous last_save value before moving it.
            if last_save is not None:
                try:
                    prev_commit = repo.get(last_save).peel(pygit2.Commit)
                    prev_ts = datetime.fromtimestamp(
                        prev_commit.commit_time, tz=timezone.utc
                    )
                    now_ts = datetime.now(timezone.utc)
                    if festival_day(prev_ts) != festival_day(now_ts):
                        tag_name = festival_day(prev_ts)
                        if tag_name not in self._list_tag_names():
                            repo.references.create(
                                f"refs/tags/{tag_name}", last_save, force=False
                            )
                            logger.info("history: tagged %s -> %s", tag_name,
                                        str(last_save)[:8])
                except Exception:
                    logger.exception("history: lazy daily tag failed; skipped")

            self._set_ref(LAST_SAVE_REF, new_sha)
            logger.info("history: finalized save %s (squash, %d file(s), "
                        "source=%s)", str(new_sha)[:8], len(files_touched),
                        source)
            return str(new_sha)

    # ---------- snap (admin reset; new "baseline" commit) ----------

    def snap_workdir(
        self,
        *,
        tracked_files: List[Path],
        source: str = "admin",
        committer: Optional[str] = None,
        label: str = "reset",
    ) -> Optional[str]:
        """Capture the current working tree as a new commit and move both
        HEAD and `last_save` to it.

        Use after operations that bypass the session layer (e.g. admin
        reset replacing canonical files with seeds via shutil.copy):
        without this, `last_save` keeps pointing at the pre-reset state
        and a subsequent agent `json_revert(n=all)` would undo past the
        reset boundary.

        Returns the new commit SHA, or `None` if the working tree is
        identical to HEAD (no commit needed).
        """
        repo = self._require_repo()
        with self._lock:
            for p in tracked_files:
                if not p.exists():
                    continue
                try:
                    rel = p.resolve().relative_to(self.data_dir)
                except ValueError:
                    continue
                repo.index.add(str(rel))
            repo.index.write()

            try:
                head_tree = repo.head.peel(pygit2.Commit).tree
            except (pygit2.GitError, KeyError):
                head_tree = None
            new_tree_oid = repo.index.write_tree()
            if head_tree is not None and new_tree_oid == head_tree.id:
                # Nothing changed; still anchor last_save at current HEAD
                # so it's never behind for future revert math.
                self._set_ref(LAST_SAVE_REF, str(repo.head.target))
                return None

            sig = self._signature()
            header = f"{source}: {label}"
            body = self._format_trailers(
                source=source, committer=committer, session=None,
                files=[p.name for p in tracked_files if p.exists()],
            )
            parents = [repo.head.target] if not repo.head_is_unborn else []
            new_sha = repo.create_commit(
                None, sig, sig, f"{header}\n\n{body}", new_tree_oid, parents
            )
            repo.set_head(new_sha)
            self._set_ref(LAST_SAVE_REF, new_sha)
            logger.info("history: snap_workdir %s (-> %s)",
                        label, str(new_sha)[:8])
            return str(new_sha)

    # ---------- session discard (revert intra-session writes) ----------

    def revert_session_files(
        self,
        *,
        files_touched: List[str],
        source: str,
        committer: Optional[str],
        session_id: Optional[str],
    ) -> Optional[str]:
        """Restore each file in `files_touched` to its state at
        `last_save`, then commit "cancel session <id>". Called from
        `SessionService.discard` to undo per-PUT commits.
        """
        if not files_touched:
            return None
        repo = self._require_repo()
        with self._lock:
            last_save = self._read_ref(LAST_SAVE_REF)
            if last_save is None:
                return None
            for f in files_touched:
                try:
                    blob = repo.revparse_single(f"{last_save}:{f}")
                except (KeyError, pygit2.GitError):
                    continue
                (self.data_dir / f).write_bytes(bytes(blob.data))
                repo.index.add(f)
            repo.index.write()

            try:
                head_tree = repo.head.peel(pygit2.Commit).tree
            except (pygit2.GitError, KeyError):
                head_tree = None
            new_tree_oid = repo.index.write_tree()
            if head_tree is not None and new_tree_oid == head_tree.id:
                return None

            header = f"cancel session {session_id or ''}".strip()
            body = self._format_trailers(
                source=source, committer=committer, session=session_id,
                files=files_touched,
            )
            sig = self._signature()
            sha = repo.create_commit(
                "HEAD", sig, sig, f"{header}\n\n{body}", new_tree_oid,
                [repo.head.target]
            )
            logger.info("history: cancelled session %s (-%d file(s))",
                        session_id, len(files_touched))
            return str(sha)

    # ---------- read paths ----------

    def read_at_ref(self, file_name: str, ref: str = LAST_SAVE_REF) -> Optional[bytes]:
        """Return raw bytes of `file_name` at `ref`, or `None` if absent."""
        repo = self._require_repo()
        with self._lock:
            try:
                obj = repo.revparse_single(f"{ref}:{file_name}")
            except (KeyError, pygit2.GitError):
                return None
            return bytes(obj.data) if obj.type == pygit2.GIT_OBJECT_BLOB else None

    # ---------- history listings ----------

    def list_session_commits(
        self, file_name: str, limit: int = 10
    ) -> List[CommitInfo]:
        """Commits between `last_save` and HEAD that touched `file_name`.

        Scope = "current session" (everything after the last save). Used
        by the agent's `json_history` tool. Empty if nothing pending.
        """
        repo = self._require_repo()
        with self._lock:
            last_save = self._read_ref(LAST_SAVE_REF)
            if last_save is None or repo.head_is_unborn:
                return []
            head = repo.head.target
            if head == last_save:
                return []
            return self._walk_commits(
                start=head, stop=last_save, file_name=file_name, limit=limit
            )

    def list_history(
        self, file_name: str, limit: int = 20
    ) -> List[HistoryEntry]:
        """For the manual rollback UI: daily tags + intra-day saves.

        Daily tags first (newest first), then any saves between the
        latest tag and `last_save` that touched `file_name`.
        """
        repo = self._require_repo()
        with self._lock:
            entries: List[HistoryEntry] = []

            tags = self._tags_sorted_desc()
            for tag_name, sha in tags[:limit]:
                if not self._commit_touches_file(sha, file_name):
                    continue
                commit = repo.get(sha).peel(pygit2.Commit)
                entries.append(HistoryEntry(
                    kind="tag",
                    ref=tag_name,
                    summary=commit.message.split("\n", 1)[0],
                    ts=datetime.fromtimestamp(commit.commit_time, tz=timezone.utc),
                ))

            last_save = self._read_ref(LAST_SAVE_REF)
            latest_tag_sha = tags[0][1] if tags else None
            if last_save is not None and latest_tag_sha != last_save:
                stop = latest_tag_sha
                intra = self._walk_commits(
                    start=last_save, stop=stop, file_name=file_name,
                    limit=max(0, limit - len(entries))
                )
                for c in intra:
                    entries.append(HistoryEntry(
                        kind="save", ref=c.sha, summary=c.summary, ts=c.ts,
                    ))

            return entries[:limit]

    # ---------- rollback ops ----------

    def revert_steps(
        self,
        *,
        file_name: str,
        n_steps: int,
        source: str,
        committer: Optional[str],
    ) -> Optional[str]:
        """Revert `file_name` by `n_steps` writes within the current
        session (commits between `last_save` and HEAD that touched
        the file). Returns the new HEAD SHA, or `None` if out of range.

        - `n_steps=1` undoes the most recent write only.
        - `n_steps=N` where N is the total session writes for this file
          restores `file_name` to its `last_save` state.
        """
        if n_steps < 1:
            return None
        # Fetch up to n_steps commits — we only need to confirm the depth.
        commits = self.list_session_commits(file_name=file_name, limit=n_steps)
        if len(commits) < n_steps:
            return None

        # State to restore = the file at "before the oldest commit we
        # want to undo", i.e. the parent of commits[n_steps-1]. If that's
        # past `last_save` we use `last_save` directly. Otherwise the
        # parent is just the next-older session commit, but we don't have
        # it in our list; pygit2 can resolve it via `<sha>^`.
        oldest_to_undo = commits[n_steps - 1].sha
        target_ref = f"{oldest_to_undo}^"

        repo = self._require_repo()
        with self._lock:
            try:
                blob_obj = repo.revparse_single(f"{target_ref}:{file_name}")
            except (KeyError, pygit2.GitError):
                return None
            blob_bytes = bytes(blob_obj.data)

            (self.data_dir / file_name).write_bytes(blob_bytes)
            repo.index.add(file_name)
            repo.index.write()

            try:
                head_tree = repo.head.peel(pygit2.Commit).tree
            except (pygit2.GitError, KeyError):
                head_tree = None
            new_tree_oid = repo.index.write_tree()
            if head_tree is not None and new_tree_oid == head_tree.id:
                return None

            sig = self._signature()
            header = f"revert {n_steps} step(s) on {file_name}"
            body = self._format_trailers(
                source=source, committer=committer, session=None,
                files=[file_name],
            )
            sha = repo.create_commit(
                "HEAD", sig, sig, f"{header}\n\n{body}", new_tree_oid,
                [repo.head.target]
            )
            logger.info("history: reverted %s by %d step(s) -> %s",
                        file_name, n_steps, str(sha)[:8])
            return str(sha)

    def rollback_to_ref(
        self,
        *,
        file_name: str,
        ref: str,
        source: str,
        committer: Optional[str],
    ) -> Optional[str]:
        """Restore `file_name` to its state at `ref` (tag name or SHA),
        creating a new commit. `last_save` does NOT move — the rollback
        is just a working-tree change like any other.
        """
        repo = self._require_repo()
        with self._lock:
            try:
                blob_obj = repo.revparse_single(f"{ref}:{file_name}")
            except (KeyError, pygit2.GitError):
                return None
            (self.data_dir / file_name).write_bytes(bytes(blob_obj.data))
            repo.index.add(file_name)
            repo.index.write()

            tree_oid = repo.index.write_tree()
            sig = self._signature()
            header = f"rollback {file_name} to {ref}"
            body = self._format_trailers(
                source=source, committer=committer, session=None, files=[file_name]
            )
            sha = repo.create_commit(
                "HEAD", sig, sig, f"{header}\n\n{body}", tree_oid,
                [repo.head.target]
            )
            logger.info("history: rolled %s back to %s -> %s",
                        file_name, ref, str(sha)[:8])
            return str(sha)

    # ---------- internals ----------

    def _require_repo(self) -> pygit2.Repository:
        if self._repo is None:
            raise RuntimeError("HistoryService.init_repo() not called")
        return self._repo

    def _signature(self) -> pygit2.Signature:
        return pygit2.Signature(_AUTHOR_NAME, _AUTHOR_EMAIL)

    def _read_ref(self, name: str) -> Optional[str]:
        repo = self._require_repo()
        try:
            ref = repo.references[name]
        except KeyError:
            return None
        return str(ref.target)

    def _set_ref(self, name: str, sha) -> None:
        repo = self._require_repo()
        sha_str = str(sha)
        if name in repo.references:
            repo.references[name].set_target(sha_str)
        else:
            repo.references.create(name, sha_str)

    def _list_tag_names(self) -> List[str]:
        repo = self._require_repo()
        return [r.split("refs/tags/", 1)[1]
                for r in repo.references
                if r.startswith("refs/tags/")]

    def _tags_sorted_desc(self) -> List[Tuple[str, str]]:
        """Return tags as (name, sha) sorted by committer date desc."""
        repo = self._require_repo()
        out: List[Tuple[str, str, int]] = []
        for r in repo.references:
            if not r.startswith("refs/tags/"):
                continue
            try:
                commit = repo.references[r].peel(pygit2.Commit)
            except Exception:
                continue
            out.append((r.split("refs/tags/", 1)[1], str(commit.id),
                         commit.commit_time))
        out.sort(key=lambda x: x[2], reverse=True)
        return [(name, sha) for name, sha, _ in out]

    def _walk_commits(
        self, *, start: str, stop: Optional[str],
        file_name: str, limit: int
    ) -> List[CommitInfo]:
        repo = self._require_repo()
        # SORT_TIME alone is unstable when commits share a timestamp;
        # combine with SORT_TOPOLOGICAL so newest-first walks the actual
        # parent chain (newest commit -> parent -> ...).
        walker = repo.walk(
            str(start),
            pygit2.GIT_SORT_TIME | pygit2.GIT_SORT_TOPOLOGICAL,
        )
        if stop is not None:
            walker.hide(str(stop))
        out: List[CommitInfo] = []
        for commit in walker:
            if not self._commit_touches_file(str(commit.id), file_name):
                continue
            out.append(CommitInfo(
                sha=str(commit.id),
                summary=commit.message.split("\n", 1)[0],
                ts=datetime.fromtimestamp(commit.commit_time, tz=timezone.utc),
                source=_extract_trailer(commit.message, "source"),
                committer=_extract_trailer(commit.message, "committer"),
                tool=_extract_trailer(commit.message, "tool"),
            ))
            if len(out) >= limit:
                break
        return out

    def _commit_touches_file(self, sha: str, file_name: str) -> bool:
        repo = self._require_repo()
        commit = repo.get(sha).peel(pygit2.Commit)
        parents = commit.parents
        if not parents:
            return file_name in _list_tree_paths(commit.tree)
        diff = repo.diff(parents[0], commit)
        for patch in diff:
            if patch.delta.new_file.path == file_name or \
               patch.delta.old_file.path == file_name:
                return True
        return False

    def _mechanical_summary(self, files: List[str]) -> str:
        if len(files) == 1:
            return f"update {files[0]}"
        return f"update {len(files)} files"

    def _format_trailers(self, *, source: str, committer: Optional[str],
                          session: Optional[str], files: List[str],
                          tool: Optional[str] = None) -> str:
        lines = [f"source: {source}"]
        if committer:
            lines.append(f"committer: {committer}")
        if tool:
            lines.append(f"tool: {tool}")
        if session:
            lines.append(f"session: {session}")
        if files:
            lines.append(f"files: {', '.join(files)}")
        return "\n".join(lines) + "\n"


def _list_tree_paths(tree) -> List[str]:
    out: List[str] = []
    for entry in tree:
        out.append(entry.name)
    return out


def _extract_trailer(message: str, key: str) -> Optional[str]:
    prefix = f"{key}:"
    for line in reversed(message.splitlines()):
        line = line.strip()
        if line.startswith(prefix):
            return line[len(prefix):].strip()
    return None
