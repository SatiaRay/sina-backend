import json
import os
from pathlib import Path
from typing import Dict, Any

def initialize_system_settings():
    """Initialize system settings with default values if settings file doesn't exist"""
    # Use absolute paths based on the current file's location
    current_dir = Path(__file__).parent
    settings_path = current_dir / "../data/system_settings.json"
    schema_path = current_dir / "../data/settings_schema.json"
    
    # Resolve to absolute paths
    settings_path = settings_path.resolve()
    schema_path = schema_path.resolve()
    
    # Create data directory if it doesn't exist
    settings_path.parent.mkdir(parents=True, exist_ok=True)
    
    if not settings_path.exists():
        print(f"System settings file not found at {settings_path}. Creating with default values...")
        
        if not schema_path.exists():
            raise FileNotFoundError(f"Settings schema not found at {schema_path}")
        
        # Load schema to get default values
        with open(schema_path, 'r', encoding='utf-8') as f:
            schema = json.load(f)
        
        # Create default settings from schema
        default_settings = {}
        for prop_name, prop_config in schema.get('properties', {}).items():
            default_settings[prop_name] = prop_config.get('default')
        
        # Save default settings
        with open(settings_path, 'w', encoding='utf-8') as f:
            json.dump(default_settings, f, indent=2, ensure_ascii=False)
        
        print(f"Default system settings created at {settings_path}")
    
    return str(settings_path)  # Return string path for Dynaconf