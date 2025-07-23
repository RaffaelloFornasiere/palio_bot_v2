"""Multi-file JSON editor tool using JSONPath for structured editing."""

import json
from pathlib import Path
from typing import Any, Dict, Optional
from jsonpath_ng.ext import parse as parse_ext
import logging

from palio_bot.agent.models import Tool, ToolResult
from palio_bot.tools.file_registry import FileRegistry

logger = logging.getLogger(__name__)


class MultiJSONEditorTool:
    """Tool for editing multiple JSON files using JSONPath expressions."""
    
    def __init__(self, file_registry: FileRegistry):
        """Initialize with file registry.
        
        Args:
            file_registry: Registry of allowed files and their configurations
        """
        self.registry = file_registry
        self._last_content: Dict[str, str] = {}  # Track last content per file
    
    def _load_json(self, file_name: str) -> tuple[dict, Optional[str]]:
        """Load JSON from a registered file. Returns (data, error_message)."""
        try:
            # Get file configuration
            config = self.registry.get_config(file_name)
            if not config:
                return {}, f"File '{file_name}' non registrato. File disponibili: {', '.join(self.registry.list_files())}"
            
            # Get active path (temp if exists, otherwise main)
            file_path = self.registry.get_active_path(file_name)
            if not file_path or not file_path.exists():
                return {}, f"File {file_name} ({file_path}) non trovato."
            
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            data = json.loads(content)
            return data, None
        except json.JSONDecodeError as e:
            return {}, f"File JSON non valido: {str(e)}"
        except Exception as e:
            return {}, f"Errore nel leggere il file: {str(e)}"
    
    def _save_json(self, file_name: str, data: dict) -> Optional[str]:
        """Save JSON to file with validation. Returns error message if any."""
        try:
            # Get file configuration
            config = self.registry.get_config(file_name)
            if not config:
                return f"File '{file_name}' non registrato"
            
            # Check if file is locked
            if self.registry.check_file_locked(file_name, data):
                return f"File '{file_name}' è bloccato e non può essere modificato"
            
            # Check if editing is allowed
            if not config.allow_edit:
                return f"File '{file_name}' è in sola lettura"
            
            # Validate content if validator is configured
            is_valid, error_msg = self.registry.validate_content(file_name, data)
            if not is_valid:
                return error_msg
            
            # Get active path
            file_path = self.registry.get_active_path(file_name)
            if not file_path:
                return f"Impossibile determinare il percorso per '{file_name}'"
            
            # Backup current content for undo
            if file_path.exists():
                with open(file_path, 'r', encoding='utf-8') as f:
                    self._last_content[file_name] = f.read()
            
            # Write new content with nice formatting
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Mark file as modified
            self.registry.mark_modified(file_name)
            
            logger.info(f"File '{file_name}' salvato con successo")
            return None
            
        except Exception as e:
            return f"Errore nel salvare il file: {str(e)}"
    
    def view(self, file_name: str, path: Optional[str] = None) -> ToolResult:
        """View JSON content from a specific file, optionally filtered by JSONPath.
        
        Args:
            file_name: Name of the registered file (e.g., "palio", "games", "leaderboard")
            path: Optional JSONPath expression (e.g., "$.palio.eventi[0]")
                 If not provided, shows entire JSON
        """
        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)
        
        if not path:
            # Return entire JSON
            return ToolResult(
                success=True,
                data={
                    "file": file_name,
                    "content": json.dumps(data, ensure_ascii=False, indent=2),
                    "path": "$",
                    "matches": 1
                },
                message=f"File '{file_name}' visualizzato completamente"
            )
        
        try:
            # Parse and apply JSONPath
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun elemento trovato in '{file_name}' per il path: {path}"
                )
            
            # Format results
            if len(matches) == 1:
                result_data = {
                    "file": file_name,
                    "content": json.dumps(matches[0].value, ensure_ascii=False, indent=2),
                    "path": str(matches[0].full_path),
                    "matches": 1
                }
                message = f"Trovato 1 elemento in '{file_name}' per il path: {path}"
            else:
                results = []
                for match in matches:
                    results.append({
                        "path": str(match.full_path),
                        "value": match.value
                    })
                result_data = {
                    "file": file_name,
                    "content": json.dumps(results, ensure_ascii=False, indent=2),
                    "paths": [str(m.full_path) for m in matches],
                    "matches": len(matches)
                }
                message = f"Trovati {len(matches)} elementi in '{file_name}' per il path: {path}"
            
            return ToolResult(
                success=True,
                data=result_data,
                message=message
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nella visualizzazione: {str(e)}"
            )
    
    def set_field(self, file_name: str, path: str, value: Any) -> ToolResult:
        """Set a field value in a specific file at the specified JSONPath.
        
        Args:
            file_name: Name of the registered file
            path: JSONPath expression (e.g., "$.palio.anno" or "$.palio.eventi[0].nome")
            value: The value to set (can be string, number, boolean, object, or array)
        """
        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)
        
        try:
            # Handle simple paths for setting values
            if path.startswith("$."):
                # Split path into segments
                segments = path[2:].split(".")
                current = data
                
                # Navigate to parent of target
                for i, segment in enumerate(segments[:-1]):
                    # Handle array indices
                    if "[" in segment and "]" in segment:
                        field, index_str = segment.split("[")
                        index = int(index_str.rstrip("]"))
                        
                        if field:
                            if field not in current:
                                current[field] = []
                            current = current[field]
                        
                        # Ensure array is large enough
                        while len(current) <= index:
                            current.append({})
                        current = current[index]
                    else:
                        if segment not in current:
                            current[segment] = {}
                        current = current[segment]
                
                # Set the final value
                final_segment = segments[-1]
                if "[" in final_segment and "]" in final_segment:
                    field, index_str = final_segment.split("[")
                    index = int(index_str.rstrip("]"))
                    
                    if field:
                        if field not in current:
                            current[field] = []
                        while len(current[field]) <= index:
                            current[field].append(None)
                        current[field][index] = value
                    else:
                        while len(current) <= index:
                            current.append(None)
                        current[index] = value
                else:
                    current[final_segment] = value
                
                # Save the modified data
                save_error = self._save_json(file_name, data)
                if save_error:
                    return ToolResult(success=False, error=save_error)
                
                return ToolResult(
                    success=True,
                    message=f"Campo impostato in '{file_name}': {path} = {json.dumps(value, ensure_ascii=False)}",
                    data={"file": file_name, "path": path, "value": value}
                )
            else:
                return ToolResult(
                    success=False,
                    error=f"Path non supportato. Usa il formato $.campo.sottocampo"
                )
                
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nell'impostare il campo: {str(e)}"
            )
    
    def delete_field(self, file_name: str, path: str) -> ToolResult:
        """Delete a field in a specific file at the specified JSONPath.
        
        Args:
            file_name: Name of the registered file
            path: JSONPath expression pointing to field to delete
        """
        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)
        
        try:
            # Parse JSONPath
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun elemento trovato in '{file_name}' per il path: {path}"
                )
            
            # Delete each match
            deleted_count = 0
            for match in matches:
                parent = match.context.value
                if isinstance(parent, dict):
                    # Delete from object
                    if str(match.path) in parent:
                        del parent[str(match.path)]
                        deleted_count += 1
                elif isinstance(parent, list):
                    # Delete from array (need to handle indices carefully)
                    # For now, set to None and filter later
                    parent[match.path] = None
                    deleted_count += 1
            
            # Clean up None values from arrays
            def clean_arrays(obj):
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        if isinstance(value, list):
                            obj[key] = [v for v in value if v is not None]
                        clean_arrays(value)
                elif isinstance(obj, list):
                    for item in obj:
                        clean_arrays(item)
            
            clean_arrays(data)
            
            # Save the modified data
            save_error = self._save_json(file_name, data)
            if save_error:
                return ToolResult(success=False, error=save_error)
            
            return ToolResult(
                success=True,
                message=f"Eliminati {deleted_count} elementi da '{file_name}' al path: {path}",
                data={"file": file_name, "path": path, "deleted_count": deleted_count}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nell'eliminare il campo: {str(e)}"
            )
    
    def append(self, file_name: str, path: str, value: Any) -> ToolResult:
        """Append a value to an array in a specific file at the specified JSONPath.
        
        Args:
            file_name: Name of the registered file
            path: JSONPath expression pointing to an array
            value: The value to append
        """
        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)
        
        try:
            # Parse JSONPath
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun array trovato in '{file_name}' per il path: {path}"
                )
            
            # Append to first match (should be an array)
            target = matches[0].value
            if not isinstance(target, list):
                return ToolResult(
                    success=False,
                    error=f"Il path {path} in '{file_name}' non punta a un array"
                )
            
            target.append(value)
            
            # Save the modified data
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
                    "new_length": len(target)
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nell'aggiungere all'array: {str(e)}"
            )
    
    def insert_at(self, file_name: str, path: str, index: int, value: Any) -> ToolResult:
        """Insert a value into an array in a specific file at a specific index.
        
        Args:
            file_name: Name of the registered file
            path: JSONPath expression pointing to an array
            index: The index where to insert (0-based)
            value: The value to insert
        """
        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)
        
        try:
            # Parse JSONPath
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun array trovato in '{file_name}' per il path: {path}"
                )
            
            # Insert into first match (should be an array)
            target = matches[0].value
            if not isinstance(target, list):
                return ToolResult(
                    success=False,
                    error=f"Il path {path} in '{file_name}' non punta a un array"
                )
            
            # Validate index
            if index < 0 or index > len(target):
                return ToolResult(
                    success=False,
                    error=f"Indice non valido: {index}. L'array ha {len(target)} elementi."
                )
            
            target.insert(index, value)
            
            # Save the modified data
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
                    "new_length": len(target)
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nell'inserire nell'array: {str(e)}"
            )
    
    def remove_at(self, file_name: str, path: str, index: int) -> ToolResult:
        """Remove an element from an array in a specific file at a specific index.
        
        Args:
            file_name: Name of the registered file
            path: JSONPath expression pointing to an array
            index: The index of element to remove (0-based)
        """
        data, error = self._load_json(file_name)
        if error:
            return ToolResult(success=False, error=error)
        
        try:
            # Parse JSONPath
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun array trovato in '{file_name}' per il path: {path}"
                )
            
            # Remove from first match (should be an array)
            target = matches[0].value
            if not isinstance(target, list):
                return ToolResult(
                    success=False,
                    error=f"Il path {path} in '{file_name}' non punta a un array"
                )
            
            # Validate index
            if index < 0 or index >= len(target):
                return ToolResult(
                    success=False,
                    error=f"Indice non valido: {index}. L'array ha {len(target)} elementi."
                )
            
            removed_value = target.pop(index)
            
            # Save the modified data
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
                    "new_length": len(target)
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nel rimuovere dall'array: {str(e)}"
            )
    
    def undo(self, file_name: str) -> ToolResult:
        """Undo the last modification to a specific file.
        
        Args:
            file_name: Name of the registered file
        """
        try:
            if file_name not in self._last_content:
                return ToolResult(
                    success=False,
                    error=f"Nessuna operazione da annullare per '{file_name}'."
                )
            
            # Get file path
            file_path = self.registry.get_active_path(file_name)
            if not file_path:
                return ToolResult(
                    success=False,
                    error=f"Impossibile determinare il percorso per '{file_name}'"
                )
            
            # Restore previous content
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(self._last_content[file_name])
            
            # Clear backup for this file
            del self._last_content[file_name]
            
            return ToolResult(
                success=True,
                message=f"Ultima modifica annullata per '{file_name}'."
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nell'annullamento: {str(e)}"
            )


def create_multi_json_editor_tools(file_registry: FileRegistry) -> Dict[str, Tool]:
    """Create all JSON editor tools for multiple files.
    
    Args:
        file_registry: Registry of allowed files and their configurations
    """
    editor = MultiJSONEditorTool(file_registry)
    
    # Get list of editable files for tool descriptions
    editable_files = file_registry.get_editable_files()
    file_list = ", ".join(f'"{f}"' for f in editable_files)
    
    tools = {
        "json_view": Tool(
            name="json_view",
            description=f"Visualizza il contenuto JSON di un file specifico, opzionalmente filtrato da JSONPath. File disponibili: {file_list}",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": f"Nome del file da visualizzare ({file_list})",
                        "enum": editable_files
                    },
                    "path": {
                        "type": "string",
                        "description": "JSONPath expression (opzionale). Se omesso mostra tutto il JSON"
                    }
                },
                "required": ["file_name"]
            },
            function=editor.view
        ),
        
        "json_set": Tool(
            name="json_set",
            description=f"Imposta un valore in un file JSON specifico. File disponibili: {file_list}",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": f"Nome del file da modificare ({file_list})",
                        "enum": editable_files
                    },
                    "path": {
                        "type": "string",
                        "description": "JSONPath dove impostare il valore (es. '$.palio.anno')"
                    },
                    "value": {
                        "type": ["string", "number", "boolean", "object", "array", "null"],
                        "description": "Il valore da impostare"
                    }
                },
                "required": ["file_name", "path", "value"]
            },
            function=editor.set_field
        ),
        
        "json_delete": Tool(
            name="json_delete",
            description=f"Elimina un campo in un file JSON specifico. File disponibili: {file_list}",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": f"Nome del file da modificare ({file_list})",
                        "enum": editable_files
                    },
                    "path": {
                        "type": "string",
                        "description": "JSONPath dell'elemento da eliminare"
                    }
                },
                "required": ["file_name", "path"]
            },
            function=editor.delete_field
        ),
        
        "json_append": Tool(
            name="json_append",
            description=f"Aggiunge un valore a un array in un file JSON specifico. File disponibili: {file_list}",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": f"Nome del file da modificare ({file_list})",
                        "enum": editable_files
                    },
                    "path": {
                        "type": "string",
                        "description": "JSONPath dell'array"
                    },
                    "value": {
                        "type": ["string", "number", "boolean", "object", "array", "null"],
                        "description": "Il valore da aggiungere"
                    }
                },
                "required": ["file_name", "path", "value"]
            },
            function=editor.append
        ),
        
        "json_insert": Tool(
            name="json_insert",
            description=f"Inserisce un valore in un array di un file JSON specifico. File disponibili: {file_list}",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": f"Nome del file da modificare ({file_list})",
                        "enum": editable_files
                    },
                    "path": {
                        "type": "string",
                        "description": "JSONPath dell'array"
                    },
                    "index": {
                        "type": "integer",
                        "description": "Indice dove inserire (0-based)"
                    },
                    "value": {
                        "type": ["string", "number", "boolean", "object", "array", "null"],
                        "description": "Il valore da inserire"
                    }
                },
                "required": ["file_name", "path", "index", "value"]
            },
            function=editor.insert_at
        ),
        
        "json_remove": Tool(
            name="json_remove",
            description=f"Rimuove un elemento da un array in un file JSON specifico. File disponibili: {file_list}",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": f"Nome del file da modificare ({file_list})",
                        "enum": editable_files
                    },
                    "path": {
                        "type": "string",
                        "description": "JSONPath dell'array"
                    },
                    "index": {
                        "type": "integer",
                        "description": "Indice dell'elemento da rimuovere (0-based)"
                    }
                },
                "required": ["file_name", "path", "index"]
            },
            function=editor.remove_at
        ),
        
        "json_undo": Tool(
            name="json_undo",
            description=f"Annulla l'ultima modifica a un file JSON specifico. File disponibili: {file_list}",
            parameters_schema={
                "type": "object",
                "properties": {
                    "file_name": {
                        "type": "string",
                        "description": f"Nome del file per cui annullare l'ultima modifica ({file_list})",
                        "enum": editable_files
                    }
                },
                "required": ["file_name"]
            },
            function=editor.undo
        )
    }
    
    return tools