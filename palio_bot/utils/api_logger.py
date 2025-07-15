"""API request/response logger with YAML format."""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import yaml


class APILogger:
    """Logger for LLM API requests and responses in YAML format."""
    
    def __init__(self, log_dir: str = "logs"):
        """Initialize the logger.
        
        Args:
            log_dir: Directory to store log files (default: "logs")
        """
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
    
    def _get_daily_dir(self) -> Path:
        """Get or create directory for today's logs."""
        today = datetime.now().strftime("%Y-%m-%d")
        daily_dir = self.log_dir / today
        daily_dir.mkdir(exist_ok=True)
        return daily_dir
    
    def _cleanup_old_logs(self) -> None:
        """Remove log directories older than 7 days."""
        cutoff_date = datetime.now() - timedelta(days=7)
        
        for item in self.log_dir.iterdir():
            if item.is_dir():
                try:
                    # Parse directory name as date
                    dir_date = datetime.strptime(item.name, "%Y-%m-%d")
                    if dir_date < cutoff_date:
                        # Remove all files in the directory
                        for file in item.iterdir():
                            file.unlink()
                        # Remove the directory
                        item.rmdir()
                except ValueError:
                    # Skip directories that don't match date format
                    pass
    
    def _serialize_for_yaml(self, obj: Any) -> Any:
        """Convert objects to YAML-serializable format."""
        if hasattr(obj, "model_dump"):
            # Handle Pydantic models
            return obj.model_dump()
        elif hasattr(obj, "__dict__"):
            # Handle regular objects
            return {
                k: self._serialize_for_yaml(v)
                for k, v in obj.__dict__.items()
                if not k.startswith("_")
            }
        elif isinstance(obj, dict):
            return {k: self._serialize_for_yaml(v) for k, v in obj.items()}
        elif isinstance(obj, list | tuple):
            return [self._serialize_for_yaml(item) for item in obj]
        elif isinstance(obj, str | int | float | bool | type(None)):
            return obj
        else:
            # Fallback to string representation
            return str(obj)
    
    def log_request(self, request_data: dict[str, Any], provider: str = "unknown") -> str:
        """Log an API request and return the log filename.
        
        Args:
            request_data: The request data to log
            provider: The LLM provider (e.g., "anthropic", "llamacpp")
            
        Returns:
            The filepath of the logged request
        """
        self._cleanup_old_logs()
        
        daily_dir = self._get_daily_dir()
        timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]  # HH:MM:SS.mmm
        filename = f"{timestamp}_{provider}_request.yaml"
        filepath = daily_dir / filename
        
        # Prepare log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "request",
            "provider": provider,
            "data": self._serialize_for_yaml(request_data),
        }
        
        # Write to YAML file
        with open(filepath, "w") as f:
            yaml.dump(log_entry, f, default_flow_style=False, sort_keys=False)
        
        return str(filepath)
    
    def log_response(
        self, response_data: Any, request_filepath: str | None = None, provider: str = "unknown"
    ) -> str:
        """Log an API response and return the log filename.
        
        Args:
            response_data: The response data to log
            request_filepath: Path to the corresponding request file
            provider: The LLM provider (e.g., "anthropic", "llamacpp")
            
        Returns:
            The filepath of the logged response
        """
        daily_dir = self._get_daily_dir()
        
        if request_filepath:
            # Use matching timestamp from request file
            request_path = Path(request_filepath)
            base_name = request_path.stem.replace(f"_{provider}_request", "")
            filename = f"{base_name}_{provider}_response.yaml"
        else:
            timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
            filename = f"{timestamp}_{provider}_response.yaml"
        
        filepath = daily_dir / filename
        
        # Prepare log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "response",
            "provider": provider,
            "request_file": request_filepath,
            "data": self._serialize_for_yaml(response_data),
        }
        
        # Write to YAML file
        with open(filepath, "w") as f:
            yaml.dump(log_entry, f, default_flow_style=False, sort_keys=False)
        
        return str(filepath)
    
    def log_error(self, error: Exception, request_filepath: str | None = None, provider: str = "unknown") -> str:
        """Log an API error and return the log filename.
        
        Args:
            error: The exception that occurred
            request_filepath: Path to the corresponding request file
            provider: The LLM provider (e.g., "anthropic", "llamacpp")
            
        Returns:
            The filepath of the logged error
        """
        daily_dir = self._get_daily_dir()
        
        if request_filepath:
            # Use matching timestamp from request file
            request_path = Path(request_filepath)
            base_name = request_path.stem.replace(f"_{provider}_request", "")
            filename = f"{base_name}_{provider}_error.yaml"
        else:
            timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
            filename = f"{timestamp}_{provider}_error.yaml"
        
        filepath = daily_dir / filename
        
        # Prepare log entry
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "error",
            "provider": provider,
            "request_file": request_filepath,
            "error": {
                "type": type(error).__name__,
                "message": str(error),
                "details": self._serialize_for_yaml(getattr(error, "__dict__", {})),
            },
        }
        
        # Write to YAML file
        with open(filepath, "w") as f:
            yaml.dump(log_entry, f, default_flow_style=False, sort_keys=False)
        
        return str(filepath)