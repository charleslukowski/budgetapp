"""Custom JSON encoder for handling Decimal and other special types."""

import json
from decimal import Decimal
from datetime import datetime, date
from typing import Any


class DecimalEncoder(json.JSONEncoder):
    """JSON encoder that handles Decimal, datetime, and other special types."""

    def default(self, obj: Any) -> Any:
        """Convert special types to JSON-serializable formats."""
        if isinstance(obj, Decimal):
            # Convert Decimal to float, preserving precision
            return float(obj)
        elif isinstance(obj, (datetime, date)):
            # Convert datetime/date to ISO format string
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            # Handle SQLAlchemy models or other objects with __dict__
            return obj.__dict__
        return super().default(obj)


def serialize_for_json(obj: Any) -> Any:
    """Recursively convert an object to JSON-serializable format.

    This handles nested structures with Decimals, dates, and other special types.
    """
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, (datetime, date)):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: serialize_for_json(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [serialize_for_json(item) for item in obj]
    elif hasattr(obj, '__dict__'):
        return serialize_for_json(obj.__dict__)
    return obj


def json_dumps(obj: Any, **kwargs) -> str:
    """Serialize object to JSON string with Decimal support."""
    return json.dumps(obj, cls=DecimalEncoder, **kwargs)


def json_loads(s: str, **kwargs) -> Any:
    """Deserialize JSON string (wrapper for consistency)."""
    return json.loads(s, **kwargs)