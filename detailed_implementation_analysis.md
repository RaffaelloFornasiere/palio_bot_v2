# Detailed Implementation Analysis: General JSON File Editing

## Current Architecture

### 1. JSON Editor Tool (`json_editor_tool.py`)
- **Hardcoded to single file**: Constructor takes `file_path` but defaults to `"palio_updated.json"`
- **All operations work on single file**: view, set_field, delete_field, append, etc.
- **Currently initialized in `container.py`** with `config.palio_games_status_temp_path`
- **No file validation**: No checks for allowed files or permissions

### 2. File Management in `system.py`
- **Copy-on-write pattern already implemented**:
  - Session start: `palio_games_status.json` → `palio_games_status_tmp.json`
  - Session close: `palio_games_status_tmp.json` → `palio_games_status.json`
  - Session cancel: Delete `palio_games_status_tmp.json`
- **Only manages one editable file**: `palio_games_status.json`
- **Leaderboard update**: Happens on session close via `LeaderboardUpdater`

### 3. Existing Pydantic Models
- **`PalioData`** (palio_models.py): For `palio.json`
- **`PalioGamesStatus`** (game_status_models.py): For `palio_games_status.json`
- **`Leaderboard`** (leaderboard_models.py): For `leaderboard.json`
- **All models already defined** with proper validation

### 4. Configuration (`config.py`)
- All file paths are hardcoded as dataclass fields
- No dynamic file registry
- No file permissions or metadata

## Detailed Changes Required

### 1. Create File Registry System (NEW FILE)
```python
# palio_bot/tools/file_registry.py
from typing import Dict, Optional, Type
from pathlib import Path
from pydantic import BaseModel, Field

class FileConfig(BaseModel):
    """Configuration for a registered file."""
    path: Path = Field(..., description="Path to the JSON file")
    temp_suffix: str = Field("_tmp", description="Suffix for temporary files")
    validator: Optional[Type[BaseModel]] = Field(None, description="Pydantic model for validation")
    allow_edit: bool = Field(True, description="Whether agent can edit this file")
    use_safety_copy: bool = Field(True, description="Whether to use copy-on-write pattern")

class FileRegistry:
    def __init__(self):
        self.files: Dict[str, FileConfig] = {}
    
    def register(self, name: str, config: FileConfig):
        self.files[name] = config
    
    def get_temp_path(self, name: str) -> Path:
        config = self.files[name]
        return config.path.with_suffix(config.temp_suffix + config.path.suffix)
```

### 2. Refactor JSON Editor Tool
**Changes to `json_editor_tool.py`**:
- Add `file_name` parameter to EVERY method (view, set_field, etc.)
- Add file registry dependency
- Add validation before save
- Check file permissions from metadata

**Key changes**:
```python
class JSONEditorTool:
    def __init__(self, file_registry: FileRegistry):
        self.registry = file_registry
        self._last_content: Dict[str, str] = {}  # Track per file
    
    def view(self, file_name: str, path: Optional[str] = None) -> ToolResult:
        # Check if file is registered
        if file_name not in self.registry.files:
            return ToolResult(success=False, error=f"File '{file_name}' not registered")
        
        # Load from temp path if exists, otherwise from main path
        file_config = self.registry.files[file_name]
        file_path = self.registry.get_temp_path(file_name) if file_config.use_safety_copy else file_config.path
        
        # Check metadata for permissions
        data, error = self._load_json(file_path)
        if not error and "_metadata" in data:
            if data["_metadata"].get("locked", False):
                return ToolResult(success=False, error="File is locked")
```

### 3. Update System.py
**Major changes needed**:
- Track multiple files in session
- Generalize copy-on-write for all registered files
- Handle multiple file closures/cancellations

```python
class System:
    def __init__(self, ..., file_registry: FileRegistry):
        self.file_registry = file_registry
        self.modified_files: Set[str] = set()
    
    def _create_session(self):
        # Copy ALL registered files that use safety copy
        for name, config in self.file_registry.files.items():
            if config.use_safety_copy and config.path.exists():
                shutil.copy2(config.path, self.file_registry.get_temp_path(name))
    
    def close_session(self):
        # Copy all modified files back
        for name in self.modified_files:
            config = self.file_registry.files[name]
            temp_path = self.file_registry.get_temp_path(name)
            if temp_path.exists():
                shutil.copy2(temp_path, config.path)
```

### 4. Update Container.py
**Changes**:
- Initialize file registry
- Register all editable files
- Pass registry to JSON editor tool

```python
def __init__(self, ...):
    self._file_registry = self._create_file_registry()

def _create_file_registry(self) -> FileRegistry:
    registry = FileRegistry()
    
    # Register palio.json
    registry.register("palio", FileConfig(
        path=self.config.palio_file_path,
        validator=PalioData,
        use_safety_copy=False  # No safety copy for read-only
    ))
    
    # Register palio_games_status.json
    registry.register("games", FileConfig(
        path=self.config.palio_games_status_path,
        validator=PalioGamesStatus,
        use_safety_copy=True
    ))
    
    # Register leaderboard.json
    registry.register("leaderboard", FileConfig(
        path=self.config.leaderboard_file_path,
        validator=Leaderboard,
        use_safety_copy=True
    ))
    
    return registry
```

### 5. Update Tool Creation
**In `json_editor_tool.py`**:
- Update ALL tool schemas to include `file_name` parameter
- Update function signatures

```python
"json_view": Tool(
    parameters_schema={
        "type": "object",
        "properties": {
            "file_name": {
                "type": "string",
                "description": "Name of file to view (palio, games, leaderboard)",
                "enum": ["palio", "games", "leaderboard"]
            },
            "path": {...}
        },
        "required": ["file_name"]
    }
)
```

### 6. Update Agent System Prompt
Add instructions about multiple files:
```python
<tools>
Strumenti disponibili per modificare file JSON:
- json_view: Visualizza contenuto di un file (specificare file_name: "games", "leaderboard", "palio")
- json_set: Imposta valore in un file
- ...

File disponibili:
- "palio": Definizione del palio (read-only)
- "games": Stato dei giochi (palio_games_status.json)
- "leaderboard": Classifica generale
</tools>
```

## Implementation Complexity by Component

1. **File Registry (NEW)**: ~150 lines
   - New module, clean implementation
   - Complexity: LOW

2. **JSON Editor Tool**: ~300 lines of changes
   - Add file_name to all methods
   - Add validation logic
   - Update all tool schemas
   - Complexity: MEDIUM-HIGH

3. **System.py**: ~100 lines of changes
   - Generalize file management
   - Track modified files
   - Complexity: MEDIUM

4. **Container.py**: ~50 lines of changes
   - Create registry
   - Wire dependencies
   - Complexity: LOW

5. **Config.py**: No changes needed
   - Paths already defined

6. **Agent prompt**: ~20 lines
   - Update instructions
   - Complexity: LOW

## Total Estimated Changes
- **New code**: ~150 lines (FileRegistry)
- **Modified code**: ~470 lines across 4 files
- **Files touched**: 5 (1 new, 4 modified)
- **Breaking changes**: Yes - tool signatures change
- **Migration needed**: Update any code calling tools directly

## Risk Assessment
- **High Risk**: Changing tool signatures breaks existing usage
- **Medium Risk**: File safety mechanism needs careful testing
- **Low Risk**: Validation is additive, won't break existing flow
