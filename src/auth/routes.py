from uuid import uuid4

from fastapi import APIRouter, Depends, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import User
from src.auth.msal_client import acquire_token_by_code, get_auth_url
from src.auth.token_cache import DBTokenCache
from src.database import get_db

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Redirect the user to Microsoft's authorization page."""
    state = str(uuid4())
    request.session["oauth_state"] = state
    auth_url = get_auth_url(state=state)
    return RedirectResponse(url=auth_url)


@router.get("/callback")
async def callback(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle the OAuth2 callback from Microsoft."""
    # Validate CSRF state
    params = request.query_params
    expected_state = request.session.pop("oauth_state", None)
    received_state = params.get("state")

    if not expected_state or expected_state != received_state:
        return RedirectResponse(url="/")

    code = params.get("code")
    if not code:
        return RedirectResponse(url="/")

    # Exchange authorization code for tokens
    cache = DBTokenCache()
    token_response = acquire_token_by_code(code=code, cache=cache)

    if "error" in token_response:
        return RedirectResponse(url="/")

    # Extract user info from id_token_claims
    claims = token_response.get("id_token_claims", {})
    user_id = claims.get("oid", "")
    email = claims.get("preferred_username", "")
    display_name = claims.get("name", "")
    tenant_id = claims.get("tid", "")

    # Upsert the user in the database
    user = User(
        id=user_id,
        email=email,
        display_name=display_name,
        tenant_id=tenant_id,
    )
    await db.merge(user)
    await db.commit()

    # Save the token cache to the database
    await cache.save(db=db, user_id=user_id)

    # Store user_id in the session
    request.session["user_id"] = user_id

    return RedirectResponse(url="/")


@router.get("/me")
async def me(request: Request) -> dict:
    """Return the current user's info from the session."""
    user_id = request.session.get("user_id")
    if not user_id:
        from fastapi import HTTPException

        raise HTTPException(status_code=401, detail="Not authenticated")

    return {
        "user_id": user_id,
    }


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    """Clear the session and redirect to the home page."""
    request.session.clear()
    return RedirectResponse(url="/")
