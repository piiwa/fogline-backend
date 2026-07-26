from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_subject

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/device")


async def get_current_identity(token: str = Depends(oauth2_scheme)) -> str:
    """Resolve the exploration identity (the JWT subject) or reject with 401."""
    subject = decode_subject(token)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return subject
