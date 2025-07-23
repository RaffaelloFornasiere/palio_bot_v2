# Multi-File JSON Editing Implementation

## Overview
The system now supports multi-file JSON editing by default, allowing the model to edit multiple JSON files (games, leaderboard, etc.) with the same safety mechanisms as the original single-file system. Multi-file editing is now the default behavior.

## Key Components

### 1. File Registry (`tools/file_registry.py`)
- `FileConfig`: Pydantic model for file configuration
  - Path, validator, permissions, safety copy settings
- `FileRegistry`: Central registry for all editable files
  - Tracks modified files
  - Handles validation and locking
  - Manages temp file paths

### 2. Multi-File JSON Editor (`tools/multi_json_editor_tool.py`)
- `MultiJSONEditorTool`: Supports editing multiple files
  - All operations require `file_name` parameter
  - Validates content before saving
  - Checks file permissions and locks
  - Maintains undo history per file

### 3. System (`system.py`)
- Requires file registry for multi-file support
- Manages temp files for all registered files
- Handles session management and file synchronization

### 4. Container (`container.py`)
- Always creates file registry and registers all files
- Uses multi-file JSON editor tools by default
- No configuration flags needed

### 5. Agent (`agent.py`)
- Uses multi-file aware system prompt
- Same async generator pattern

### 6. System Prompt (`agent/system_prompt.py`)
- Instructions for using multiple files
- Examples with `file_name` parameter
- Guidelines for both games and leaderboard

## Usage

### Basic Setup
```python
from palio_bot.container import Container

# Initialize container (multi-file is now default)
container = Container()
await container.init_container()
system = container.system()
```

### Example Commands
```python
# View games file
await system.send_message("mostra lo stato dei giochi")

# View leaderboard
await system.send_message("mostra la classifica")

# Update game result
await system.send_message("villa vince 2-0 contro salt")

# Modify leaderboard
await system.send_message("aggiungi 10 punti bonus a Villa")

# Close session to save
system.close_session()
```

## File Safety

The system maintains the same safety guarantees:
1. **Copy-on-write**: Temp files during active session
2. **Validation**: Pydantic models validate before save
3. **Atomic updates**: All files saved together on close
4. **Rollback**: Cancel discards all changes

## File Configuration

In `container.py`, files are registered with specific settings:

```python
# Read-only reference file
registry.register("palio", FileConfig(
    path=config.palio_file_path,
    validator=PalioData,
    allow_edit=False,
    use_safety_copy=False
))

# Editable with safety copy
registry.register("games", FileConfig(
    path=config.palio_games_status_path,
    validator=PalioGamesStatus,
    allow_edit=True,
    use_safety_copy=True
))
```

## File Locking

Files can include optional `_metadata` to control access:

```json
{
  "_metadata": {
    "locked": true,
    "editable_by_agent": false
  },
  // ... rest of content
}
```

## Testing

Use the provided test scripts:
- `test_multi_file.py`: Comprehensive test of multi-file operations
- `example_multi_file_usage.py`: Simple usage examples

## Changes Summary

The implementation has been simplified:
- Multi-file editing is now the default behavior
- No configuration flags needed
- All backward compatibility code has been removed
- System always uses file registry and multi-file tools

## Adding New Files

To add more editable files:
1. Register them in `container.py` with appropriate FileConfig
2. Add Pydantic validator models if needed
3. The model will automatically be able to edit them