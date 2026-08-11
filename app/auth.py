"""Authentication and authorization helpers.

Password hashing is done with bcrypt via passlib. JWTs are HS256-signed via
python-jose. Token signing reads ``SECRET_KEY`` (and ``ACCESS_TOKEN_EXPIRE_MINUTES``)
from the environment; if ``SECRET_KEY`` is missing a clearly-insecure dev fallback
is used so local development never breaks, and a warning is printed once at import.
"""

import os
import warnings
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from app import crud, models
from app.database import get_db
from app.security import verify_password
from app.utils import FORBIDDEN, UNAUTHORIZED, APIError


# --- Configuration ----------------------------------------------------------

# Token signing key. In production set SECRET_KEY in the environment.
# The fallback exists so local dev "just works" — it prints a warning.
SECRET_KEY = os.getenv("SECRET_KEY")
if not SECRET_KEY:
    SECRET_KEY = "dev-insecure-secret-change-me"
    warnings.warn(
        "SECRET_KEY is not set; using insecure dev fallback. "
        "Set SECRET_KEY in the environment before deploying.",
        RuntimeWarning,
        stacklevel=2,
    )

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "30"))


# Password hashing lives in app/security.py to break an import cycle
# between auth.py -> crud.py -> auth.py.


# --- JWT ---------------------------------------------------------------------


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
    extra_claims: Optional[dict] = None,
) -> str:
    """Issue an HS256 JWT. ``subject`` is the user id encoded as a string."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)

    expire = datetime.now(timezone.utc) + expires_delta
    to_encode: dict = {"sub": subject, "exp": expire}

    if extra_claims:
        to_encode.update(extra_claims)

    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError as exc:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Could not validate credentials",
            code=UNAUTHORIZED,
            details=str(exc),
        ) from exc


# --- Current-user dependency ------------------------------------------------

# tokenUrl points at the /token route in main.py; the path is referenced as a
# string so this module doesn't import main (avoiding a circular import).
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def authenticate_user(
    db: Session,
    username: str,
    password: str,
) -> Optional[models.User]:
    user = crud.get_user_by_username(db, username)

    if user is None:
        return None

    if not verify_password(password, user.hashed_password):
        return None

    return user


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    payload = _decode_token(token)
    subject = payload.get("sub")

    if subject is None:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Could not validate credentials",
            code=UNAUTHORIZED,
        )

    try:
        user_id = int(subject)
    except (TypeError, ValueError) as exc:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Could not validate credentials",
            code=UNAUTHORIZED,
        ) from exc

    user = crud.get_user(db, user_id)

    if user is None:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Could not validate credentials",
            code=UNAUTHORIZED,
        )

    if not user.is_active:
        raise APIError(
            status_code=status.HTTP_401_UNAUTHORIZED,
            message="Inactive user",
            code=UNAUTHORIZED,
        )

    return user


# --- Role-based guard -------------------------------------------------------


def require_role(*allowed_roles: str):
    """Dependency factory: only allow users whose role is in ``allowed_roles``."""

    allowed = set(allowed_roles)

    def _checker(
        current_user: models.User = Depends(get_current_user),
    ) -> models.User:
        if current_user.role not in allowed:
            raise APIError(
                status_code=status.HTTP_403_FORBIDDEN,
                message="Operation not permitted for your role",
                code=FORBIDDEN,
            )

        return current_user

    return _checker
