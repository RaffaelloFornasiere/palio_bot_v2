"""JSON editor tool using JSONPath for structured editing."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
from jsonpath_ng import parse
from jsonpath_ng.ext import parse as parse_ext

from .models import Tool, ToolResult


class JSONEditorTool:
    """Tool for editing JSON files using JSONPath expressions."""
    
    def __init__(self, file_path: str = "palio.json"):
        self.file_path = Path(file_path)
        self._last_content: Optional[str] = None
    
    def _load_json(self) -> tuple[dict, Optional[str]]:
        """Load JSON from file. Returns (data, error_message)."""
        try:
            if not self.file_path.exists():
                return {}, f"File {self.file_path.name} non trovato."
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            data = json.loads(content)
            return data, None
        except json.JSONDecodeError as e:
            return {}, f"File JSON non valido: {str(e)}"
        except Exception as e:
            return {}, f"Errore nel leggere il file: {str(e)}"
    
    def _save_json(self, data: dict) -> Optional[str]:
        """Save JSON to file. Returns error message if any."""
        try:
            # Backup current content for undo
            if self.file_path.exists():
                with open(self.file_path, 'r', encoding='utf-8') as f:
                    self._last_content = f.read()
            
            # Write new content with nice formatting
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return None
        except Exception as e:
            return f"Errore nel salvare il file: {str(e)}"
    
    def view(self, path: Optional[str] = None) -> ToolResult:
        """View JSON content, optionally filtered by JSONPath.
        
        Args:
            path: Optional JSONPath expression (e.g., "$.palio.eventi[0]")
                 If not provided, shows entire JSON
        """
        data, error = self._load_json()
        if error:
            return ToolResult(success=False, error=error)
        
        if not path:
            # Return entire JSON
            return ToolResult(
                success=True,
                data={
                    "content": json.dumps(data, ensure_ascii=False, indent=2),
                    "path": "$",
                    "matches": 1
                },
                message="File JSON visualizzato completamente"
            )
        
        try:
            # Parse and apply JSONPath
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun elemento trovato per il path: {path}"
                )
            
            # Format results
            if len(matches) == 1:
                result_data = {
                    "content": json.dumps(matches[0].value, ensure_ascii=False, indent=2),
                    "path": str(matches[0].full_path),
                    "matches": 1
                }
                message = f"Trovato 1 elemento per il path: {path}"
            else:
                results = []
                for match in matches:
                    results.append({
                        "path": str(match.full_path),
                        "value": match.value
                    })
                result_data = {
                    "content": json.dumps(results, ensure_ascii=False, indent=2),
                    "paths": [str(m.full_path) for m in matches],
                    "matches": len(matches)
                }
                message = f"Trovati {len(matches)} elementi per il path: {path}"
            
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
    
    def set_field(self, path: str, value: Any) -> ToolResult:
        """Set a field value at the specified JSONPath.
        
        Args:
            path: JSONPath expression (e.g., "$.palio.anno" or "$.palio.eventi[0].nome")
            value: The value to set (can be string, number, boolean, object, or array)
        """
        data, error = self._load_json()
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
                save_error = self._save_json(data)
                if save_error:
                    return ToolResult(success=False, error=save_error)
                
                return ToolResult(
                    success=True,
                    message=f"Campo impostato con successo: {path} = {json.dumps(value, ensure_ascii=False)}",
                    data={"path": path, "value": value}
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
    
    def delete_field(self, path: str) -> ToolResult:
        """Delete a field at the specified JSONPath.
        
        Args:
            path: JSONPath expression pointing to field to delete
        """
        data, error = self._load_json()
        if error:
            return ToolResult(success=False, error=error)
        
        try:
            # Parse JSONPath
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun elemento trovato per il path: {path}"
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
            save_error = self._save_json(data)
            if save_error:
                return ToolResult(success=False, error=save_error)
            
            return ToolResult(
                success=True,
                message=f"Eliminati {deleted_count} elementi dal path: {path}",
                data={"path": path, "deleted_count": deleted_count}
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nell'eliminare il campo: {str(e)}"
            )
    
    def append(self, path: str, value: Any) -> ToolResult:
        """Append a value to an array at the specified JSONPath.
        
        Args:
            path: JSONPath expression pointing to an array
            value: The value to append
        """
        data, error = self._load_json()
        if error:
            return ToolResult(success=False, error=error)
        
        try:
            # Parse JSONPath
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun array trovato per il path: {path}"
                )
            
            # Append to first match (should be an array)
            target = matches[0].value
            if not isinstance(target, list):
                return ToolResult(
                    success=False,
                    error=f"Il path {path} non punta a un array"
                )
            
            target.append(value)
            
            # Save the modified data
            save_error = self._save_json(data)
            if save_error:
                return ToolResult(success=False, error=save_error)
            
            return ToolResult(
                success=True,
                message=f"Valore aggiunto all'array: {path}",
                data={
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
    
    def insert_at(self, path: str, index: int, value: Any) -> ToolResult:
        """Insert a value into an array at a specific index.
        
        Args:
            path: JSONPath expression pointing to an array
            index: The index where to insert (0-based)
            value: The value to insert
        """
        data, error = self._load_json()
        if error:
            return ToolResult(success=False, error=error)
        
        try:
            # Parse JSONPath
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun array trovato per il path: {path}"
                )
            
            # Insert into first match (should be an array)
            target = matches[0].value
            if not isinstance(target, list):
                return ToolResult(
                    success=False,
                    error=f"Il path {path} non punta a un array"
                )
            
            # Validate index
            if index < 0 or index > len(target):
                return ToolResult(
                    success=False,
                    error=f"Indice non valido: {index}. L'array ha {len(target)} elementi."
                )
            
            target.insert(index, value)
            
            # Save the modified data
            save_error = self._save_json(data)
            if save_error:
                return ToolResult(success=False, error=save_error)
            
            return ToolResult(
                success=True,
                message=f"Valore inserito nell'array {path} all'indice {index}",
                data={
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
    
    def remove_at(self, path: str, index: int) -> ToolResult:
        """Remove an element from an array at a specific index.
        
        Args:
            path: JSONPath expression pointing to an array
            index: The index of element to remove (0-based)
        """
        data, error = self._load_json()
        if error:
            return ToolResult(success=False, error=error)
        
        try:
            # Parse JSONPath
            jsonpath_expr = parse_ext(path)
            matches = jsonpath_expr.find(data)
            
            if not matches:
                return ToolResult(
                    success=False,
                    error=f"Nessun array trovato per il path: {path}"
                )
            
            # Remove from first match (should be an array)
            target = matches[0].value
            if not isinstance(target, list):
                return ToolResult(
                    success=False,
                    error=f"Il path {path} non punta a un array"
                )
            
            # Validate index
            if index < 0 or index >= len(target):
                return ToolResult(
                    success=False,
                    error=f"Indice non valido: {index}. L'array ha {len(target)} elementi."
                )
            
            removed_value = target.pop(index)
            
            # Save the modified data
            save_error = self._save_json(data)
            if save_error:
                return ToolResult(success=False, error=save_error)
            
            return ToolResult(
                success=True,
                message=f"Elemento rimosso dall'array {path} all'indice {index}",
                data={
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
    
    def undo(self) -> ToolResult:
        """Undo the last modification."""
        try:
            if self._last_content is None:
                return ToolResult(
                    success=False,
                    error="Nessuna operazione da annullare."
                )
            
            # Restore previous content
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(self._last_content)
            
            # Clear backup
            self._last_content = None
            
            return ToolResult(
                success=True,
                message="Ultima modifica annullata con successo."
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nell'annullamento: {str(e)}"
            )


def create_json_editor_tools(file_path: str = "palio.json") -> Dict[str, Tool]:
    """Create all JSON editor tools for the given file."""
    editor = JSONEditorTool(file_path)
    
    tools = {
        "json_view": Tool(
            name="json_view",
            description="Visualizza il contenuto JSON, opzionalmente filtrato da JSONPath. Esempi: '$' per tutto, '$.palio.eventi' per array eventi, '$.palio.eventi[0]' per primo evento",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "JSONPath expression (opzionale). Se omesso mostra tutto il JSON"
                    }
                },
                "required": []
            },
            function=editor.view
        ),
        
        "json_set": Tool(
            name="json_set",
            description="Imposta un valore a un path JSON specifico. Crea campi intermedi se necessario. Esempi: '$.palio.anno' per campo semplice, '$.palio.eventi[0].nome' per campo in array",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "JSONPath dove impostare il valore (es. '$.palio.anno')"
                    },
                    "value": {
                        "type": ["string", "number", "boolean", "object", "array", "null"],
                        "description": "Il valore da impostare (stringa, numero, booleano, oggetto o array)"
                    }
                },
                "required": ["path", "value"]
            },
            function=editor.set_field
        ),
        
        "json_delete": Tool(
            name="json_delete",
            description="Elimina un campo o elemento al path JSON specificato",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "JSONPath dell'elemento da eliminare"
                    }
                },
                "required": ["path"]
            },
            function=editor.delete_field
        ),
        
        "json_append": Tool(
            name="json_append",
            description="Aggiunge un valore alla fine di un array JSON",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "JSONPath dell'array (es. '$.palio.eventi')"
                    },
                    "value": {
                        "type": ["string", "number", "boolean", "object", "array", "null"],
                        "description": "Il valore da aggiungere all'array"
                    }
                },
                "required": ["path", "value"]
            },
            function=editor.append
        ),
        
        "json_insert": Tool(
            name="json_insert",
            description="Inserisce un valore in un array JSON a un indice specifico",
            parameters_schema={
                "type": "object",
                "properties": {
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
                "required": ["path", "index", "value"]
            },
            function=editor.insert_at
        ),
        
        "json_remove": Tool(
            name="json_remove",
            description="Rimuove un elemento da un array JSON a un indice specifico",
            parameters_schema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "JSONPath dell'array"
                    },
                    "index": {
                        "type": "integer",
                        "description": "Indice dell'elemento da rimuovere (0-based)"
                    }
                },
                "required": ["path", "index"]
            },
            function=editor.remove_at
        ),
        
        "json_undo": Tool(
            name="json_undo",
            description="Annulla l'ultima modifica al file JSON",
            parameters_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            function=editor.undo
        )
    }
    
    return tools