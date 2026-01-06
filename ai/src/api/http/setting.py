from fastapi import APIRouter
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["Settings"])

schema = lambda: {
        "properties": {
            "site_name": {
            "lable": "نام نرم افزار",
            "type": "string",
            "default": "Sina AI"
            },
            "text_agent_model": {
            "lable": "مدل هوش مصنوعی چت",
            "type": "string",
            "enum": [
                "gpt-3.5-turbo-0125",
                "gpt-4.1-mini-2025-04-14",
                "gpt-4.1-2025-04-14",
                "gpt-5.1-2025-11-13",
                "gpt-5-mini-2025-08-07"
            ],
            "default": "gpt-3.5-turbo-0125"
            },
            "voice_to_text_service": {
            "lable": "سرویس تبدیل گفتار به متن",
            "type": "string",
            "enum": ["google", "openai"],
            "default": "google"
            }
        },
        "required": ["site_name", "text_agent_model", "voice_to_text_service"]
    }


def initialize_settings():
    """Initialize settings with default values if settings file doesn't exist"""
    
    # Create default settings from schema
    default_settings = {}
    for prop_name, prop_config in schema.get('properties', {}).items():
        default_settings[prop_name] = prop_config.get('default')
    
    return default_settings

@router.get(
    "/settings",
    summary="Get System Settings",
    description="Fetch current system settings from JSON file",
)
async def get_system_settings():
    pass


@router.post(
    "/settings",
    summary="Update System Settings",
    description="Update system settings and validate using JSON schema",
)
async def update_system_settings(new_settings: dict):
    pass


@router.get(
    "/settings-schema",
    summary="Get System Settings Schema and Allowed Models",
    description="Fetch the JSON schema for system settings and the allowed text models from config/ai.json",
)
async def get_setting_schema():
    return schema
