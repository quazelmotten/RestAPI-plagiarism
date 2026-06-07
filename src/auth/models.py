"""
User models for authentication.

The ``User`` and ``ApiKey`` models live in :mod:`shared.models` so that the
``users`` and ``api_keys`` tables are registered in the shared metadata
for both the API and the worker. They are re-exported here for backward
compatibility with existing imports (``from auth.models import User``).
"""

from shared.models import ApiKey, User, UserRole

__all__ = ["User", "UserRole", "ApiKey"]
