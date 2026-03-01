from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.msal_client import acquire_token_silent
from src.auth.token_cache import DBTokenCache
from src.database import get_db


class AuthenticatedUser(BaseModel):
    user_id: str
    email: str
    display_name: str
    access_token: str


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthenticatedUser:
    """FastAPI dependency that resolves the current authenticated user.

    Reads the user_id from the session, loads the MSAL token cache from the
    database, and attempts a silent token acquisition. Raises HTTP 401 if
    the user is not logged in or the token cannot be refreshed.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    # Load the token cache from the database
    cache = DBTokenCache()
    await cache.load(db=db, user_id=user_id)

    # Attempt silent token acquisition
    access_token = acquire_token_silent(user_id=user_id, cache=cache)
    if not access_token:
        raise HTTPException(
            status_code=401, detail="Session expired. Please log in again."
        )

    # Save the cache in case MSAL refreshed the tokens
    await cache.save(db=db, user_id=user_id)

    # Retrieve user details from the database
    from sqlalchemy import select

    from src.auth.models import User

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return AuthenticatedUser(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        access_token=access_token,
    )
