from typing import Any

from .base import CustomBaseModel


class PaginatedResponse(CustomBaseModel):
    """Standard paginated response wrapper for all list endpoints."""

    items: list[Any]
    total: int
    limit: int
    offset: int
