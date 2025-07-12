"""Text editor tool for managing palio.json file."""

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from .models import Tool, ToolResult


class TextEditorTool:
    """Tool for editing the palio.json file with view, str_replace, insert, and undo operations."""
    
    def __init__(self, file_path: str = "palio.json"):
        self.file_path = Path(file_path)
        self.backup_path = Path(f"{file_path}.backup")
        self._last_content: Optional[str] = None
    
    def view(self) -> ToolResult:
        """View the current content of palio.json."""
        try:
            if not self.file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File {self.file_path.name} non trovato."
                )
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Validate JSON
            try:
                json.loads(content)
            except json.JSONDecodeError as e:
                return ToolResult(
                    success=False,
                    error=f"File JSON non valido: {str(e)}",
                    data={"content": content}
                )
            
            return ToolResult(
                success=True,
                data={
                    "content": content,
                    "lines": len(content.splitlines()),
                    "size": len(content)
                },
                message=f"File visualizzato: {len(content.splitlines())} righe, {len(content)} caratteri"
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nel leggere il file: {str(e)}"
            )
    
    def str_replace(self, old_string: str, new_string: str) -> ToolResult:
        """Replace a string in the file with validation."""
        try:
            # Read current content
            if not self.file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File {self.file_path.name} non trovato."
                )
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            # Check if old_string exists and count occurrences
            if old_string not in current_content:
                return ToolResult(
                    success=False,
                    error=f"Stringa non trovata: '{old_string}'"
                )
            
            # Check for multiple occurrences
            occurrence_count = current_content.count(old_string)
            if occurrence_count > 1:
                return ToolResult(
                    success=False,
                    error=f"Trovate {occurrence_count} occorrenze di '{old_string}'. Usa una stringa più specifica per sostituire una sola occorrenza."
                )
            
            # Backup current content for undo
            self._last_content = current_content
            
            # Perform replacement
            new_content = current_content.replace(old_string, new_string)
            
            # Validate JSON after replacement
            try:
                json.loads(new_content)
            except json.JSONDecodeError as e:
                return ToolResult(
                    success=False,
                    error=f"La sostituzione produrrebbe JSON non valido: {str(e)}",
                    data={"preview": new_content[:200] + "..." if len(new_content) > 200 else new_content}
                )
            
            # Write new content
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return ToolResult(
                success=True,
                message="Stringa sostituita con successo.",
                data={
                    "old_string": old_string,
                    "new_string": new_string,
                    "lines_changed": abs(len(new_content.splitlines()) - len(current_content.splitlines()))
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nella sostituzione: {str(e)}"
            )
    
    def insert(self, line_number: int, text: str) -> ToolResult:
        """Insert text at a specific line number."""
        try:
            # Read current content
            if not self.file_path.exists():
                return ToolResult(
                    success=False,
                    error=f"File {self.file_path.name} non trovato."
                )
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                current_content = f.read()
            
            # Backup current content for undo
            self._last_content = current_content
            
            lines = current_content.splitlines()
            
            # Validate line number
            if line_number < 1 or line_number > len(lines) + 1:
                return ToolResult(
                    success=False,
                    error=f"Numero di riga non valido: {line_number}. Il file ha {len(lines)} righe."
                )
            
            # Insert text (line_number is 1-based)
            lines.insert(line_number - 1, text)
            new_content = '\n'.join(lines)
            
            # Validate JSON after insertion
            try:
                json.loads(new_content)
            except json.JSONDecodeError as e:
                return ToolResult(
                    success=False,
                    error=f"L'inserimento produrrebbe JSON non valido: {str(e)}",
                    data={"preview": new_content[:200] + "..." if len(new_content) > 200 else new_content}
                )
            
            # Write new content
            with open(self.file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
            
            return ToolResult(
                success=True,
                message=f"Testo inserito alla riga {line_number}.",
                data={
                    "inserted_text": text,
                    "line_number": line_number,
                    "total_lines": len(lines)
                }
            )
            
        except Exception as e:
            return ToolResult(
                success=False,
                error=f"Errore nell'inserimento: {str(e)}"
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


def create_text_editor_tools(file_path: str = "palio.json") -> Dict[str, Tool]:
    """Create all text editor tools for the given file."""
    editor = TextEditorTool(file_path)
    
    tools = {
        "view": Tool(
            name="view",
            description="Visualizza il contenuto completo del file palio.json",
            parameters_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            function=editor.view
        ),
        
        "str_replace": Tool(
            name="str_replace",
            description="Sostituisce una stringa specifica nel file con una nuova stringa. Valida che il JSON rimanga valido.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "old_string": {
                        "type": "string",
                        "description": "La stringa da sostituire"
                    },
                    "new_string": {
                        "type": "string", 
                        "description": "La nuova stringa"
                    }
                },
                "required": ["old_string", "new_string"]
            },
            function=editor.str_replace
        ),
        
        "insert": Tool(
            name="insert",
            description="Inserisce testo a un numero di riga specifico. Valida che il JSON rimanga valido.",
            parameters_schema={
                "type": "object",
                "properties": {
                    "line_number": {
                        "type": "integer",
                        "description": "Il numero di riga dove inserire il testo (1-based)",
                        "minimum": 1
                    },
                    "text": {
                        "type": "string",
                        "description": "Il testo da inserire"
                    }
                },
                "required": ["line_number", "text"]
            },
            function=editor.insert
        ),
        
        "undo": Tool(
            name="undo", 
            description="Annulla l'ultima modifica effettuata al file",
            parameters_schema={
                "type": "object",
                "properties": {},
                "required": []
            },
            function=editor.undo
        )
    }
    
    return tools