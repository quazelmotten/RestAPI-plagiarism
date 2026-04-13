"""Password validation utilities."""

import re
from typing import List

from config.auth import auth_config


def validate_password(password: str) -> List[str]:
    """
    Validate password against configured rules.

    Returns:
        List of validation errors (empty list means valid).
    """
    errors = []

    # Check minimum length
    if len(password) < auth_config.min_password_length:
        errors.append(f"Password must be at least {auth_config.min_password_length} characters")

    # Check uppercase requirement
    if auth_config.require_uppercase and not re.search(r"[A-Z]", password):
        errors.append("Password must contain at least 1 uppercase letter")

    # Check lowercase requirement
    if auth_config.require_lowercase and not re.search(r"[a-z]", password):
        errors.append("Password must contain at least 1 lowercase letter")

    # Check digit requirement
    if auth_config.require_digit and not re.search(r"\d", password):
        errors.append("Password must contain at least 1 digit")

    return errors


def is_password_valid(password: str) -> bool:
    """Check if password is valid (no errors)."""
    return len(validate_password(password)) == 0
