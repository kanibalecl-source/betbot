"""Argon2id password hashing using cryptography's PHC implementation."""
from __future__ import annotations

import os

from cryptography.exceptions import InvalidKey
from cryptography.hazmat.primitives.kdf.argon2 import Argon2id


def hash_password(password: str) -> str:
    if len(password) < 14:
        raise ValueError("Password must contain at least 14 characters")
    return Argon2id(
        salt=os.urandom(16),
        length=32,
        iterations=3,
        lanes=4,
        memory_cost=64 * 1024,
    ).derive_phc_encoded(password.encode("utf-8"))


def verify_password_hash(password_hash: str, password: str) -> bool:
    if not str(password_hash or "").startswith("$argon2id$"):
        return False
    try:
        Argon2id.verify_phc_encoded(password.encode("utf-8"), password_hash)
        return True
    except (InvalidKey, ValueError, TypeError):
        return False
