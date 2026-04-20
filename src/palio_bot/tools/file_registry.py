"""File registry system for managing editable JSON files."""

from typing import Any, Dict, Optional, Set, Type
from pathlib import Path
from pydantic import BaseModel, Field, ValidationError
import json
import logging

logger = logging.getLogger(__name__)


_VILLAGE_FIELD_KEYS = {"scores", "palio_leaderboard", "game_leaderboards"}


def _collect_village_refs(obj: Any, refs: Set[str]) -> None:
    """Walk a JSON tree and collect every string that appears as a village name.

    Picks up:
      - dict keys under `scores` / `palio_leaderboard` / any inner dict of
        `game_leaderboards`
      - string values of any `village` field (score_penalties, round scores,
        applied_bonuses/penalties)
    """
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k in _VILLAGE_FIELD_KEYS and isinstance(v, dict):
                if k == "game_leaderboards":
                    for inner in v.values():
                        if isinstance(inner, dict):
                            refs.update(inner.keys())
                else:
                    refs.update(v.keys())
            if k == "village" and isinstance(v, str):
                refs.add(v)
            _collect_village_refs(v, refs)
    elif isinstance(obj, list):
        for x in obj:
            _collect_village_refs(x, refs)


class FileConfig(BaseModel):
    """Configuration for a registered file."""
    path: Path = Field(..., description="Path to the JSON file")
    temp_suffix: str = Field("_tmp", description="Suffix for temporary files")
    validator: Optional[Type[BaseModel]] = Field(None, description="Pydantic model for validation")
    allow_edit: bool = Field(True, description="Whether agent can edit this file")
    use_safety_copy: bool = Field(True, description="Whether to use copy-on-write pattern")
    
    class Config:
        """Pydantic configuration."""
        arbitrary_types_allowed = True  # Allow Type[BaseModel] in fields


class FileRegistry:
    """Registry for managing multiple editable JSON files."""
    
    def __init__(self):
        """Initialize empty registry."""
        self.files: Dict[str, FileConfig] = {}
        self._modified_files: set[str] = set()
    
    def register(self, name: str, config: FileConfig) -> None:
        """Register a file configuration.
        
        Args:
            name: Unique name for the file (e.g., "palio", "palio_games_status", "leaderboard")
            config: File configuration
        """
        self.files[name] = config
        logger.info(f"Registered file '{name}' -> {config.path}")
    
    def get_config(self, name: str) -> Optional[FileConfig]:
        """Get configuration for a file.
        
        Args:
            name: File name
            
        Returns:
            FileConfig if found, None otherwise
        """
        return self.files.get(name)
    
    def get_temp_path(self, name: str) -> Optional[Path]:
        """Get temporary file path for a registered file.
        
        Args:
            name: File name
            
        Returns:
            Temporary file path if file uses safety copy, None otherwise
        """
        config = self.files.get(name)
        if not config or not config.use_safety_copy:
            return None
        
        # Create temp path by inserting suffix before extension
        return config.path.with_name(
            config.path.stem + config.temp_suffix + config.path.suffix
        )
    
    def get_active_path(self, name: str) -> Optional[Path]:
        """Get the active path for editing (temp if exists, otherwise main).
        
        Args:
            name: File name
            
        Returns:
            Path to use for editing
        """
        config = self.files.get(name)
        if not config:
            return None
        
        if config.use_safety_copy:
            temp_path = self.get_temp_path(name)
            if temp_path and temp_path.exists():
                return temp_path
        
        return config.path
    
    def validate_content(self, name: str, data: dict) -> tuple[bool, Optional[str]]:
        """Validate JSON content against registered validator.
        
        Args:
            name: File name
            data: JSON data to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        config = self.files.get(name)
        if not config or not config.validator:
            return True, None
        
        try:
            # Validate with Pydantic model
            validated = config.validator(**data)
        except ValidationError as e:
            # Format validation errors
            errors = []
            for error in e.errors():
                loc = " -> ".join(str(x) for x in error["loc"])
                msg = error["msg"]
                errors.append(f"{loc}: {msg}")

            error_msg = f"Validation errors in {name}:\n" + "\n".join(errors)
            return False, error_msg
        except Exception as e:
            return False, f"Validation error: {str(e)}"

        # Whitelist check: every village name used in editable files must be
        # listed in palio.json. Catches typos ("vila") and garbage from weaker
        # models (e.g. double-quoted keys like "\"Salt\"" post-sanitization
        # leftovers, or hallucinated villages like "Cividale").
        if name in ("palio_games_status", "leaderboard"):
            known = self._get_known_villages()
            if known:
                refs: Set[str] = set()
                _collect_village_refs(data, refs)
                unknown = refs - known
                if unknown:
                    return False, (
                        f"Borghi sconosciuti in {name}: {sorted(unknown)}. "
                        f"I borghi validi sono: {sorted(known)}."
                    )

        return True, None

    def _get_known_villages(self) -> Optional[Set[str]]:
        """Load the village whitelist from the registered palio.json, if any."""
        palio = self.files.get("palio")
        if not palio or not palio.path.exists():
            return None
        try:
            data = json.loads(palio.path.read_text(encoding="utf-8"))
            villages = data.get("villages")
            if isinstance(villages, list) and villages:
                return {v for v in villages if isinstance(v, str)}
        except Exception as exc:
            logger.warning(f"Could not load villages from palio.json: {exc}")
        return None
    
    def check_file_locked(self, name: str, data: dict) -> bool:
        """Check if file is locked via metadata.
        
        Args:
            name: File name
            data: JSON data containing potential _metadata
            
        Returns:
            True if file is locked, False otherwise
        """
        if "_metadata" in data:
            metadata = data["_metadata"]
            if metadata.get("locked", False):
                return True
            if not metadata.get("editable_by_agent", True):
                return True
        return False
    
    def mark_modified(self, name: str) -> None:
        """Mark a file as modified in this session."""
        self._modified_files.add(name)
    
    def get_modified_files(self) -> set[str]:
        """Get set of modified file names."""
        return self._modified_files.copy()
    
    def clear_modified(self) -> None:
        """Clear the modified files set."""
        self._modified_files.clear()
    
    def list_files(self) -> list[str]:
        """List all registered file names."""
        return list(self.files.keys())
    
    def get_editable_files(self) -> list[str]:
        """List only editable file names."""
        return [name for name, config in self.files.items() if config.allow_edit]