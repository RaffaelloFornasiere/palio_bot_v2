# Plan: General JSON File Editing with Safety

## Goal
Enable the model to edit any JSON file (including leaderboard.json) with the same safety mechanism as palio_games_status.json.

## Solution: Generalize JSON Editor Tool

### 1. Extend `json_editor_tool.py`
Add support for multiple files beyond just palio.json:

```python
class JSONEditorTool:
    def __init__(self, allowed_files: dict[str, str]):
        """
        allowed_files = {
            "palio": "data/palio.json",
            "games": "data/palio_games_status.json", 
            "leaderboard": "data/leaderboard.json"
        }
        """
```

### 2. File Locking Mechanism
Add optional `_metadata` field to any JSON file:

```json
{
  "_metadata": {
    "locked": false,
    "editable_by_agent": true,
    "last_modified": "2024-01-15T10:30:00"
  },
  // ... actual content
}
```

### 3. Pydantic Validation
Each file has a corresponding Pydantic model for validation:

```python
file_validators = {
    "palio": PalioData,              # from palio_models.py
    "games": GamesStatusData,        # from game_status_models.py
    "leaderboard": Leaderboard       # from leaderboard_models.py
}

# Before saving any edit:
def validate_json(file_key: str, data: dict) -> ToolResult:
    try:
        model_class = file_validators[file_key]
        validated = model_class(**data)
        return ToolResult(success=True, data=validated.dict())
    except ValidationError as e:
        return ToolResult(success=False, error=str(e))
```

### 4. Safety Pattern (Same as palio_games_status)
- Create `{filename}_updated.json` during active session
- Work on the updated copy
- Validate before each save using Pydantic models
- On session close: copy updated → original
- On session cancel: discard updated

### 5. Implementation
1. Modify `system.py` to handle multiple editable files
2. Update `json_editor_tool.py` to:
   - Check file permissions via `_metadata`
   - Validate with Pydantic before saving
   - Return validation errors to agent
3. Add file management for all editable JSONs

### 6. Usage
```
User: "Aggiungi 10 punti bonus a Villa nella classifica"
Agent: [edits leaderboard.json via json_editor_tool]
```

## Benefits
- Uniform editing interface for all JSON files
- Consistent safety mechanism
- User control via locking
- Structure validation prevents invalid data
- Simple to extend to new files