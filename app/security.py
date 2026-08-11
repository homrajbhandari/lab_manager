"""Password hashing helpers — separated from auth.py to break an import cycle
between auth -> crud -> auth. Reused by both auth (for verifying login) and
crud (for hashing on create/update).

Uses the ``bcrypt`` library directly rather than ``passlib`` because passlib
1.7.4 has a known incompatibility with bcrypt >= 4.x (``__about__`` was removed
on the bcrypt side, so passlib's backend probe crashes).
"""

import bcrypt


def get_password_hash(password: str) -> str:
    # bcrypt rejects passwords longer than 72 bytes; truncate explicitly so
    # the behavior matches what we'd get if passlib handled it for us.
    pw_bytes = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    pw_bytes = plain_password.encode("utf-8")[:72]
    try:
        hashed_bytes = hashed_password.encode("utf-8")
    except AttributeError:
        return False
    return bcrypt.checkpw(pw_bytes, hashed_bytes)