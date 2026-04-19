"""Apply `{path, set|delete}` patches declaratively to a JSON-like dict.

Mirrors the semantics of the JSON editor tool so expected states are built
from the same primitives the agent uses.
"""

from __future__ import annotations

import copy
from typing import Any, Iterable

from jsonpath_ng.ext import parse as parse_ext


class PatchError(ValueError):
    """Raised when a patch is malformed or can't be applied."""


def apply_patches(data: Any, patches: Iterable[dict]) -> Any:
    """Return a new object = `data` with each patch applied in order.

    Each patch is `{"path": <jsonpath>, "set": <value>}` or
    `{"path": <jsonpath>, "delete": true}`.
    """
    result = copy.deepcopy(data)

    for patch in patches:
        path = patch.get("path")
        if not path:
            raise PatchError(f"patch missing 'path': {patch}")
        expr = parse_ext(path)

        if "set" in patch:
            expr.update_or_create(result, patch["set"])

        elif patch.get("delete"):
            # Collect list-index deletions per-parent so we can drop highest-first.
            list_deletions: dict[int, tuple[list, list[int]]] = {}
            for match in expr.find(result):
                parent = match.context.value
                if isinstance(parent, dict):
                    parent.pop(str(match.path), None)
                elif isinstance(parent, list):
                    idx = getattr(match.path, "index", None)
                    if idx is None:
                        continue
                    bucket = list_deletions.setdefault(id(parent), (parent, []))
                    bucket[1].append(idx)
            for parent, indices in list_deletions.values():
                for idx in sorted(set(indices), reverse=True):
                    if 0 <= idx < len(parent):
                        parent.pop(idx)

        else:
            raise PatchError(
                f"patch must have 'set' or 'delete': {patch}"
            )

    return result
