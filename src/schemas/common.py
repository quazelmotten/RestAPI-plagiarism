from pydantic import BaseModel
from typing import List, Any


class PaginatedResponse(BaseModel):
    """Standard paginated response wrapper for all list endpoints."""
    items: List[Any]
    total: int
    limit: int
    offset: int
