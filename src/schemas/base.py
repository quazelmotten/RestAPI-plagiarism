"""
Base Pydantic model with common configuration and utilities.

All schema models should inherit from this base class to ensure
consistent behavior across the API.
"""

from datetime import datetime

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict


def datetime_encoder(dt: datetime) -> str:
    """Encode datetime to ISO format with timezone."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
    return dt.isoformat()


class CustomBaseModel(BaseModel):
    """
    Base model with standardized configuration.

    Features:
    - Accepts both field names and aliases when populating
    - Allows population from ORM models (attributes)
    - Serializes datetime fields to ISO format with timezone
    - Provides serializable_dict() for safe JSON encoding
    """

    model_config = ConfigDict(
        json_encoders={datetime: datetime_encoder},
        populate_by_name=True,
        from_attributes=True,
    )

    def serializable_dict(self, **kwargs):
        """
        Return a dict that contains only serializable fields.

        Useful for responses that need to be JSON-encoded.
        """
        default_dict = self.model_dump(**kwargs)
        return jsonable_encoder(default_dict)
