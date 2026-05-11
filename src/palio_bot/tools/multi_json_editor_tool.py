"""Multi-file JSON editor tool using JSONPath for structured editing."""

import json
import logging
import re
from typing import Any, Dict, Optional

from jsonpath_ng.ext import parse as parse_ext

from palio_bot.agent.models import Tool, ToolResult
from palio_bot.file_store import (
    DirectFileStore,
    FileStore,
    FileStoreLockConflict,
    FileStoreNotFound,
    FileStoreReadOnly,
    FileStoreValidationError,
)
from palio_bot.tools.file_registry import FileRegistry

logger = logging.getLogger(__name__)


ROOT_PATH = "$"


def _coerce_json_string(value: Any) -> Any:
    """If `value` is a string that parses as a JSON object or array, return the
    parsed structure; otherwise return the value unchanged.

    Weaker LLMs (e.g. some fine-tunes routed via OpenRouter) sometimes pass
    complex arguments as stringified JSON instead of as nested objects. This
    helper silently corrects that at the tool boundary.
    """
    if not isinstance(value, str):
        return value
    stripped = value.strip()
    if not stripped or stripped[0] not in ("{", "["):
        return value
    try:
        parsed = json.loads(stripped)
    except (json.JSONDecodeError, ValueError):
        return value
    if isinstance(parsed, (dict, list)):
        logger.warning(
            "Coerced stringified JSON argument (len=%d) into %s.",
            len(value),
            type(parsed).__name__,
        )
        return parsed
    return value


def _strip_surrounding_quotes(value: Any) -> Any:
    """Recursively strip enclosing double-quote characters from dict keys and
    short string values.

    Guards against a specific bad pattern from weaker models (notably gemma),
    which emit tool-call dicts like:

        {"\"Salt\"": "\"30s\"", ...}

    — the keys and values include literal `"` characters because the model
    JSON-encoded them a second time. Left alone this garbage gets written to
    disk and corrupts subsequent reads.

    Only strips if the string begins AND ends with `"` and the inner content
    has no embedded quotes (so we never mangle legitimate values that happen
    to contain a quote).
    """
    def _unquote(s: str) -> str:
        if len(s) >= 2 and s[0] == '"' and s[-1] == '"' and '"' not in s[1:-1]:
            return s[1:-1]
        return s

    if isinstance(value, dict):
        return {
            (_unquote(k) if isinstance(k, str) else k): _strip_surrounding_quotes(v)
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_strip_surrounding_quotes(x) for x in value]
    if isinstance(value, str):
        return _unquote(value)
    return value


def _deep_merge(target: Any, source: Any) -> Any:
    """Recursively merge `source` into `target` and return the result.

    - dicts: merged key-wise
    - other types: `source` replaces `target`

    Lists are replaced, not concatenated (use `append` for list additions).
    """
    if isinstance(target, dict) and isinstance(source, dict):
        for key, value in source.items():
            if key in target:
                target[key] = _deep_merge(target[key], value)
            else:
                target[key] = value
        return target
    return source


# Matches a trailing path segment: either `.name` or `[…]` (index/key/filter).
_TRAILING_SEGMENT = re.compile(r"(?:\.[^.\[\]]+|\[[^\]]+\])$")


def _deepest_existing_ancestor(path: str, data: Any) -> Optional[str]:
    """Walk up `path` one segment at a time and return the deepest ancestor
    that resolves against `data`. Returns None if even the root isn't usable.
    """
    current = path
    while current and current != ROOT_PATH:
        m = _TRAILING_SEGMENT.search(current)
        if not m:
            break
        current = current[: m.start()] or ROOT_PATH
        try:
            if parse_ext(current).find(data):
                return current
        except Exception:
            continue
    # Fallback: root if it resolves (it should, for any dict/list data).
    try:
        if parse_ext(ROOT_PATH).find(data):
            return ROOT_PATH
    except Exception:
        pass
    return None


def _is_ancestor(viewed: str, target: str) -> bool:
    """Return True if `viewed` is an ancestor path of (or equal to) `target`.

    The root path `$` is an ancestor of every path. Otherwise the match is
    prefix-based with `.` or `[` as the boundary delimiter so that
    `$.a.b` is NOT an ancestor of `$.a.bc`.
    """
    if viewed == ROOT_PATH:
        return True
    if viewed == target:
        return True
    if target.startswith(viewed + ".") or target.startswith(viewed + "["):
        return True
    return False


class MultiJSONEditorTool:
    """Tool for editing multiple JSON files using JSONPath expressions."""

    def __init__(
        self,
        file_registry: FileRegistry,
        file_store: Optional[FileStore] = None,
    ):
        self.registry = file_registry
        self.store: FileStore = file_store or DirectFileStore(file_registry)
        self._last_content: Dict[str, str] = {}  # undo buffer per file
        self._viewed_paths: Dict[str, set[str]] = {}  # view-before-edit guardrail

    # ---------- file IO helpers ----------

    def _load_json(self, file_name: str) -> tuple[dict, Optional[str]]:
        config = self.registry.get_config(file_name)
        if not config:
            return {}, (
                f"File '{file_name}' non registrato. "
                f"File disponibili: {', '.join(self.registry.list_files())}"
            )

        try:
            return self.store.load(file_name), None
        except FileStoreNotFound:
            return {}, f"File {file_name} non trovato."
        except json.JSONDecodeError as e:
            return {}, f"File JSON non valido: {str(e)}"
        except Exception as e:
            return {}, f"Errore nel leggere il file: {str(e)}"

    def _save_json(self, file_name: str, data: dict) -> Optional[str]:
        config = self.registry.get_config(file_name)
        if not config:
            return f"File '{file_name}' non registrato"

        if self.registry.check_file_locked(file_name, data):
            return f"File '{file_name}' è bloccato e non può essere modificato"

        if not config.allow_edit:
            return f"File '{file_name}' è in sola lettura"

        # Backup current content for undo BEFORE writing. Stash as JSON string
        # so undo() can restore via the store regardless of backend.
        try:
            prev = self.store.load(file_name)
            self._last_content[file_name] = json.dumps(prev, ensure_ascii=False)
        except FileStoreNotFound:
            # First write — nothing to undo to.
            pass
        except Exception:
            # Best-effort backup; don't block the write if it fails.
            pass

        try:
            self.store.save(file_name, data)
        except FileStoreValidationError as exc:
            return exc.message
        except FileStoreReadOnly:
            return f"File '{file_name}' è in sola lettura"
        except FileStoreLockConflict as exc:
            return (
                f"Il file '{file_name}' è in uso dalla sessione "
                f"{exc.holder_session_id}. Riprova più tardi."
            )
        except Exception as e:
            return f"Errore nel salvare il file: {str(e)}"

        # Intentionally DO NOT clear _viewed_paths — the agent is doing
        # sequential edits within a subtree it already saw, and wiping
        # the set after every write forces it to re-view before each
        # follow-up edit (thrashes token usage for no safety gain).

        logger.info(f"File '{file_name}' salvato con successo")
        return None

    # ---------- view-before-edit guardrail ----------

    def _mark_viewed(self, file_name: str, path: str) -> None:
        self._viewed_paths.setdefault(file_name, set()).add(path)

    def _require_viewed(self, file_name: str, target_path: str) -> Optional[str]:
        """Return an error string if no viewed ancestor covers target_path, else None.

        Readonly / unregistered files are skipped here — those errors are surfaced
        by `_save_json` with more specific messages.
        """
        config = self.registry.get_config(file_name)
        if not config or not config.allow_edit:
            return None
        viewed = self._viewed_paths.get(file_name, set())
        if any(_is_ancestor(v, target_path) for v in viewed):
            return None
        return (
            f"Per modificare '{file_name}' al path '{target_path}' "
            f"devi prima chiamare view('{file_name}', ...) su quel path o un suo antenato."
        )

    # ---------- view ----------

    def view(self, file_name: str, path: Optional[str] = None) -> ToolResult:
        """View JSON content, optionally filtered by JSONPath.

        Viewing a path (or the whole file via no `path`) marks it as viewed,
        satisfying the view-before-edit guardrail.
        """
        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)

        if not path:
            self._mark_viewed(file_name, ROOT_PATH)
            return ToolResult(
                success=True,
                data={
                    "file": file_name,
                    "content": json.dumps(data, ensure_ascii=False, indent=2),
                    "path": ROOT_PATH,
                    "matches": 1,
                },
                message=f"File '{file_name}' visualizzato completamente",
            )

        try:
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)

            if not matches:
                # Path doesn't exist. Don't silently mark it as viewed —
                # point the agent at the deepest existing ancestor so a
                # follow-up view(ancestor) gives them real context and
                # satisfies the guardrail for the eventual create.
                suggested = _deepest_existing_ancestor(path, data) or ROOT_PATH
                return ToolResult(
                    success=False,
                    error=(
                        f"Nessun elemento trovato in '{file_name}' per il path: {path}. "
                        f"Visualizza prima il path esistente più vicino "
                        f"('{suggested}') per vedere il contesto, poi crea la chiave."
                    ),
                )

            # Mark every matched full_path as viewed so descendants can be edited
            for m in matches:
                self._mark_viewed(file_name, str(m.full_path))
            # Also mark the queried path itself (wildcards/filters may expand)
            self._mark_viewed(file_name, path)

            if len(matches) == 1:
                result_data = {
                    "file": file_name,
                    "content": json.dumps(matches[0].value, ensure_ascii=False, indent=2),
                    "path": str(matches[0].full_path),
                    "matches": 1,
                }
                message = f"Trovato 1 elemento in '{file_name}' per il path: {path}"
            else:
                results = [{"path": str(m.full_path), "value": m.value} for m in matches]
                result_data = {
                    "file": file_name,
                    "content": json.dumps(results, ensure_ascii=False, indent=2),
                    "paths": [str(m.full_path) for m in matches],
                    "matches": len(matches),
                }
                message = f"Trovati {len(matches)} elementi in '{file_name}' per il path: {path}"

            return ToolResult(success=True, data=result_data, message=message)

        except Exception as e:
            return ToolResult(success=False, error=f"Errore nella visualizzazione: {str(e)}")

    # ---------- set / merge / delete ----------

    def set_field(self, file_name: str, path: str, value: Any) -> ToolResult:
        """Set a value at a JSONPath. Creates intermediate keys as needed."""
        if err := self._require_viewed(file_name, path):
            return ToolResult(success=False, error=err)

        value = _strip_surrounding_quotes(_coerce_json_string(value))
        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)

        try:
            jsonpath_expr = parse_ext(path)
            updated = jsonpath_expr.update_or_create(data, value)

            save_error = self._save_json(file_name, updated)
            if save_error:
                return ToolResult(success=False, error=save_error)

            return ToolResult(
                success=True,
                message=f"Campo impostato in '{file_name}': {path}",
                data={"file": file_name, "path": path, "value": value},
            )
        except Exception as e:
            return ToolResult(
                success=False, error=f"Errore nell'impostare il campo: {str(e)}"
            )

    def merge(self, file_name: str, path: str, partial: Any) -> ToolResult:
        """Deep-merge `partial` into the subtree at `path`.

        Unchanged keys in the existing subtree are preserved. Lists are
        replaced, not concatenated — use `append` for list additions.
        """
        if err := self._require_viewed(file_name, path):
            return ToolResult(success=False, error=err)

        partial = _strip_surrounding_quotes(_coerce_json_string(partial))
        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)

        try:
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun elemento trovato in '{file_name}' per il path: {path}",
                )

            for match in matches:
                merged = _deep_merge(match.value, partial)
                match.full_path.update(data, merged)

            save_error = self._save_json(file_name, data)
            if save_error:
                return ToolResult(success=False, error=save_error)

            return ToolResult(
                success=True,
                message=f"Campi uniti in '{file_name}' al path: {path}",
                data={
                    "file": file_name,
                    "path": path,
                    "merged_paths": [str(m.full_path) for m in matches],
                },
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Errore nel merge: {str(e)}")

    def delete_field(self, file_name: str, path: str) -> ToolResult:
        """Delete the JSONPath target(s) in place, without tree-wide side effects."""
        if err := self._require_viewed(file_name, path):
            return ToolResult(success=False, error=err)

        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)

        try:
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun elemento trovato in '{file_name}' per il path: {path}",
                )

            deleted_count = 0
            # Collect list deletions grouped by parent, so we can drop highest
            # index first and keep earlier indices stable.
            list_deletions: dict[int, tuple[list, list[int]]] = {}

            for match in matches:
                parent = match.context.value
                if isinstance(parent, dict):
                    key = str(match.path)
                    if key in parent:
                        del parent[key]
                        deleted_count += 1
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
                        deleted_count += 1

            save_error = self._save_json(file_name, data)
            if save_error:
                return ToolResult(success=False, error=save_error)

            return ToolResult(
                success=True,
                message=f"Eliminati {deleted_count} elementi da '{file_name}' al path: {path}",
                data={"file": file_name, "path": path, "deleted_count": deleted_count},
            )

        except Exception as e:
            return ToolResult(
                success=False, error=f"Errore nell'eliminare il campo: {str(e)}"
            )

    # ---------- array ops ----------

    def append(self, file_name: str, path: str, value: Any) -> ToolResult:
        if err := self._require_viewed(file_name, path):
            return ToolResult(success=False, error=err)

        value = _strip_surrounding_quotes(_coerce_json_string(value))
        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)

        try:
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun array trovato in '{file_name}' per il path: {path}",
                )

            target = matches[0].value
            if not isinstance(target, list):
                return ToolResult(
                    success=False,
                    error=f"Il path {path} in '{file_name}' non punta a un array",
                )

            target.append(value)

            save_error = self._save_json(file_name, data)
            if save_error:
                return ToolResult(success=False, error=save_error)

            return ToolResult(
                success=True,
                message=f"Valore aggiunto all'array in '{file_name}': {path}",
                data={
                    "file": file_name,
                    "path": path,
                    "value": value,
                    "new_length": len(target),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False, error=f"Errore nell'aggiungere all'array: {str(e)}"
            )

    def insert_at(self, file_name: str, path: str, index: int, value: Any) -> ToolResult:
        if err := self._require_viewed(file_name, path):
            return ToolResult(success=False, error=err)

        value = _strip_surrounding_quotes(_coerce_json_string(value))
        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)

        try:
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun array trovato in '{file_name}' per il path: {path}",
                )

            target = matches[0].value
            if not isinstance(target, list):
                return ToolResult(
                    success=False,
                    error=f"Il path {path} in '{file_name}' non punta a un array",
                )

            if index < 0 or index > len(target):
                return ToolResult(
                    success=False,
                    error=f"Indice non valido: {index}. L'array ha {len(target)} elementi.",
                )

            target.insert(index, value)

            save_error = self._save_json(file_name, data)
            if save_error:
                return ToolResult(success=False, error=save_error)

            return ToolResult(
                success=True,
                message=f"Valore inserito nell'array in '{file_name}' {path} all'indice {index}",
                data={
                    "file": file_name,
                    "path": path,
                    "index": index,
                    "value": value,
                    "new_length": len(target),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False, error=f"Errore nell'inserire nell'array: {str(e)}"
            )

    def remove_at(self, file_name: str, path: str, index: int) -> ToolResult:
        if err := self._require_viewed(file_name, path):
            return ToolResult(success=False, error=err)

        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)

        try:
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun array trovato in '{file_name}' per il path: {path}",
                )

            target = matches[0].value
            if not isinstance(target, list):
                return ToolResult(
                    success=False,
                    error=f"Il path {path} in '{file_name}' non punta a un array",
                )

            if index < 0 or index >= len(target):
                return ToolResult(
                    success=False,
                    error=f"Indice non valido: {index}. L'array ha {len(target)} elementi.",
                )

            removed_value = target.pop(index)

            save_error = self._save_json(file_name, data)
            if save_error:
                return ToolResult(success=False, error=save_error)

            return ToolResult(
                success=True,
                message=f"Elemento rimosso dall'array in '{file_name}' {path} all'indice {index}",
                data={
                    "file": file_name,
                    "path": path,
                    "index": index,
                    "removed_value": removed_value,
                    "new_length": len(target),
                },
            )
        except Exception as e:
            return ToolResult(
                success=False, error=f"Errore nel rimuovere dall'array: {str(e)}"
            )

    # ---------- undo ----------

    def undo(self, file_name: str) -> ToolResult:
        try:
            if file_name not in self._last_content:
                return ToolResult(
                    success=False,
                    error=f"Nessuna operazione da annullare per '{file_name}'.",
                )

            prev = json.loads(self._last_content[file_name])
            try:
                self.store.save(file_name, prev)
            except FileStoreValidationError as exc:
                return ToolResult(success=False, error=exc.message)
            except FileStoreReadOnly:
                return ToolResult(
                    success=False, error=f"File '{file_name}' è in sola lettura"
                )
            except Exception as e:
                return ToolResult(
                    success=False, error=f"Errore nell'annullamento: {str(e)}"
                )

            del self._last_content[file_name]
            self._viewed_paths.pop(file_name, None)

            return ToolResult(
                success=True,
                message=f"Ultima modifica annullata per '{file_name}'.",
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Errore nell'annullamento: {str(e)}")


def create_multi_json_editor_tools(
    file_registry: FileRegistry,
    file_store: Optional[FileStore] = None,
) -> Dict[str, Tool]:
    """Create all JSON editor tools for multiple files.

    `file_store` defaults to `DirectFileStore(file_registry)` for
    backward-compatible local use; adapters should pass a
    `RemoteFileStore` bound to palio-core.
    """
    editor = MultiJSONEditorTool(file_registry, file_store)

    editable_files = file_registry.get_editable_files()
    file_list = ", ".join(f'"{f}"' for f in editable_files)

    # No `type` on `value` — JSON Schema allows any type when omitted, and this
    # keeps us portable across providers. Gemini in particular rejects the
    # array-typed form `["string","number",...]`, and then fails the whole tool
    # declaration because `required` references a "missing" property.
    value_schema: Dict[str, Any] = {}

    tools = {
        "json_view": Tool(
            name="json_view",
            description=(
                f"Visualizza il contenuto JSON di un file specifico, opzionalmente filtrato da JSONPath. "
                f"File disponibili: {file_list}. "
                "Chiamare view su un path abilita le successive modifiche su quel path o i suoi discendenti."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": f"Nome del file da visualizzare ({file_list})",
                        "enum": editable_files,
                    },
                    "path": {
                        "type": "string",
                        "description": "JSONPath expression (opzionale). Se omesso mostra tutto il JSON",
                    },
                },
                "required": ["file_name"],
            },
            function=editor.view,
        ),
        "json_set": Tool(
            name="json_set",
            description=(
                f"Imposta un valore in un file JSON specifico al path indicato (sostituisce il sottoalbero). "
                f"Richiede una precedente view() sul path o su un antenato. "
                f"File disponibili: {file_list}"
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "enum": editable_files},
                    "path": {
                        "type": "string",
                        "description": "JSONPath dove impostare il valore (es. '$.palio.anno')",
                    },
                    "value": {**value_schema, "description": "Il valore da impostare"},
                },
                "required": ["file_name", "path", "value"],
            },
            function=editor.set_field,
        ),
        "json_merge": Tool(
            name="json_merge",
            description=(
                "Deep-merge di un oggetto parziale nel sottoalbero al path indicato.\n"
                "REGOLE:\n"
                "  • Dict: unione chiave-per-chiave. Le chiavi non menzionate nel "
                "partial vengono preservate. ✓ usa il merge per questo.\n"
                "  • Liste: SOSTITUZIONE completa — la lista in `partial` rimpiazza "
                "tutta la lista esistente. Elementi non menzionati SCOMPAIONO.\n"
                "    → Se vuoi modificare UN elemento di una lista, NON mettere la "
                "lista nel partial. Usa json_set con il path all'elemento specifico, "
                "es. '$.a.b[0].status', oppure json_append/json_insert/json_remove.\n"
                "  • Scalari: sostituzione.\n"
                "Richiede una precedente view() sul path o un antenato.\n"
                f"File disponibili: {file_list}"
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "enum": editable_files},
                    "path": {"type": "string", "description": "JSONPath del sottoalbero da aggiornare"},
                    "partial": {
                        "type": "object",
                        "description": "Oggetto parziale da fondere nel sottoalbero",
                    },
                },
                "required": ["file_name", "path", "partial"],
            },
            function=editor.merge,
        ),
        "json_delete": Tool(
            name="json_delete",
            description=(
                f"Elimina un campo in un file JSON specifico. Richiede una precedente view(). "
                f"File disponibili: {file_list}"
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "enum": editable_files},
                    "path": {"type": "string", "description": "JSONPath dell'elemento da eliminare"},
                },
                "required": ["file_name", "path"],
            },
            function=editor.delete_field,
        ),
        "json_append": Tool(
            name="json_append",
            description=(
                f"Aggiunge un valore in coda a un array. Richiede una precedente view(). "
                f"File disponibili: {file_list}"
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "enum": editable_files},
                    "path": {"type": "string", "description": "JSONPath dell'array"},
                    "value": {**value_schema, "description": "Il valore da aggiungere"},
                },
                "required": ["file_name", "path", "value"],
            },
            function=editor.append,
        ),
        "json_insert": Tool(
            name="json_insert",
            description=(
                f"Inserisce un valore in un array a un indice specifico. Richiede una precedente view(). "
                f"File disponibili: {file_list}"
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "enum": editable_files},
                    "path": {"type": "string", "description": "JSONPath dell'array"},
                    "index": {"type": "integer", "description": "Indice dove inserire (0-based)"},
                    "value": {**value_schema, "description": "Il valore da inserire"},
                },
                "required": ["file_name", "path", "index", "value"],
            },
            function=editor.insert_at,
        ),
        "json_remove": Tool(
            name="json_remove",
            description=(
                f"Rimuove un elemento da un array a un indice specifico. Richiede una precedente view(). "
                f"File disponibili: {file_list}"
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "enum": editable_files},
                    "path": {"type": "string", "description": "JSONPath dell'array"},
                    "index": {"type": "integer", "description": "Indice dell'elemento da rimuovere (0-based)"},
                },
                "required": ["file_name", "path", "index"],
            },
            function=editor.remove_at,
        ),
        "json_undo": Tool(
            name="json_undo",
            description=f"Annulla l'ultima modifica a un file JSON specifico. File disponibili: {file_list}",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {"type": "string", "enum": editable_files},
                },
                "required": ["file_name"],
            },
            function=editor.undo,
        ),
    }

    return tools
