import yaml
import os
from typing import Dict, Any

# App-wide configuration, loaded from YAML
# This is a simple dictionary-based config. For a real app, you might want
# a class-based system with validation (e.g., Pydantic).
_config: Dict[str, Any] = {}

def load_config(path: str = "config.yaml") -> None:
    """Loads configuration from a YAML file into the global _config dict."""
    global _config
    if not os.path.exists(path):
        # If running from root of project, try server/config.yaml
        path = os.path.join("server", path)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Configuration file not found at {path}")

    with open(path, "r") as f:
        _config = yaml.safe_load(f)

def get_config() -> Dict[str, Any]:
    """Returns the loaded configuration dictionary."""
    if not _config:
        load_config()
    return _config
