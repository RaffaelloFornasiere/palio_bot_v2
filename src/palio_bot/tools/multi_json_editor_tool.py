"""Multi-file JSON editor tool using JSONPath for structured editing."""

import json
import logging
from typing import Any, Dict, Optional

from jsonpath_ng.ext import parse as parse_ext

from palio_bot.agent.models import Tool, ToolResult
from palio_bot.tools.file_registry import FileRegistry

logger = logging.getLogger(__name__)


ROOT_PATH = "$"


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

    def __init__(self, file_registry: FileRegistry):
        self.registry = file_registry
        self._last_content: Dict[str, str] = {}  # undo buffer per file
        self._viewed_paths: Dict[str, set[str]] = {}  # view-before-edit guardrail

    # ---------- file IO helpers ----------

    def _load_json(self, file_name: str) -> tuple[dict, Optional[str]]:
        try:
            config = self.registry.get_config(file_name)
            if not config:
                return {}, (
                    f"File '{file_name}' non registrato. "
                    f"File disponibili: {', '.join(self.registry.list_files())}"
                )

            file_path = self.registry.get_active_path(file_name)
            if not file_path or not file_path.exists():
                return {}, f"File {file_name} ({file_path}) non trovato."

            with open(file_path, "r", encoding="utf-8") as f:
                return json.loads(f.read()), None
        except json.JSONDecodeError as e:
            return {}, f"File JSON non valido: {str(e)}"
        except Exception as e:
            return {}, f"Errore nel leggere il file: {str(e)}"

    def _save_json(self, file_name: str, data: dict) -> Optional[str]:
        try:
            config = self.registry.get_config(file_name)
            if not config:
                return f"File '{file_name}' non registrato"

            if self.registry.check_file_locked(file_name, data):
                return f"File '{file_name}' è bloccato e non può essere modificato"

            if not config.allow_edit:
                return f"File '{file_name}' è in sola lettura"

            is_valid, error_msg = self.registry.validate_content(file_name, data)
            if not is_valid:
                return error_msg

            file_path = self.registry.get_active_path(file_name)
            if not file_path:
                return f"Impossibile determinare il percorso per '{file_name}'"

            # Backup current content for undo
            if file_path.exists():
                with open(file_path, "r", encoding="utf-8") as f:
                    self._last_content[file_name] = f.read()

            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)

            self.registry.mark_modified(file_name)
            # Invalidate the view-before-edit guardrail for this file — content changed
            self._viewed_paths.pop(file_name, None)

            logger.info(f"File '{file_name}' salvato con successo")
            return None

        except Exception as e:
            return f"Errore nel salvare il file: {str(e)}"

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
                return ToolResult(
                    success=False,
                    error=f"Nessun elemento trovato in '{file_name}' per il path: {path}",
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

            file_path = self.registry.get_active_path(file_name)
            if not file_path:
                return ToolResult(
                    success=False,
                    error=f"Impossibile determinare il percorso per '{file_name}'",
                )

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(self._last_content[file_name])

            del self._last_content[file_name]
            self._viewed_paths.pop(file_name, None)

            return ToolResult(
                success=True,
                message=f"Ultima modifica annullata per '{file_name}'.",
            )

        except Exception as e:
            return ToolResult(success=False, error=f"Errore nell'annullamento: {str(e)}")


def create_multi_json_editor_tools(file_registry: FileRegistry) -> Dict[str, Tool]:
    """Create all JSON editor tools for multiple files."""
    editor = MultiJSONEditorTool(file_registry)

    editable_files = file_registry.get_editable_files()
    file_list = ", ".join(f'"{f}"' for f in editable_files)

    value_schema = {"type": ["string", "number", "boolean", "object", "array", "null"]}

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
                f"Deep-merge di un oggetto parziale nel sottoalbero al path indicato: i campi non specificati "
                f"vengono preservati. Per le liste usa invece json_append. Richiede una precedente view(). "
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
