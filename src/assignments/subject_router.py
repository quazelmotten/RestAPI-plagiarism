"""
Subject router - re-exports the subject router from the main assignments router.
This file is kept for backwards compatibility but delegates to assignments.router.
"""

from assignments.router import subject_router  # noqa: F401, E402

__all__ = ["subject_router"]
