from sqlalchemy.inspection import inspect
from datetime import datetime

def model_to_dict(model):
    """Convert SQLAlchemy model to dictionary, handling relationships"""
    if model is None:
        return None
        
    result = {}
    for key in inspect(model).mapper.column_attrs.keys():
        value = getattr(model, key)
        # Handle datetime serialization
        if isinstance(value, datetime):
            value = value.isoformat()
        result[key] = value
    return result 