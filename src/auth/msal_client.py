import msal

from src.config import settings


def build_msal_app(
    cache: msal.SerializableTokenCache | None = None,
) -> msal.ConfidentialClientApplication:
    """Build an MSAL ConfidentialClientApplication with optional token cache."""
    return msal.ConfidentialClientApplication(
        client_id=settings.azure_client_id,
        client_credential=settings.azure_client_secret,
        authority=settings.azure_authority,
        token_cache=cache,
    )


def get_auth_url(state: str) -> str:
    """Generate the Microsoft authorization URL for the login redirect."""
    app = build_msal_app()
    return app.get_authorization_request_url(
        scopes=settings.azure_scopes,
        state=state,
        redirect_uri=settings.redirect_uri,
    )


def acquire_token_by_code(
    code: str, cache: msal.SerializableTokenCache
) -> dict:
    """Exchange an authorization code for tokens."""
    app = build_msal_app(cache=cache)
    return app.acquire_token_by_authorization_code(
        code=code,
        scopes=settings.azure_scopes,
        redirect_uri=settings.redirect_uri,
    )


def acquire_token_silent(
    user_id: str, cache: msal.SerializableTokenCache
) -> str | None:
    """Attempt to silently acquire an access token from the cache.

    Returns the access token string, or None if silent acquisition fails.
    """
    app = build_msal_app(cache=cache)
    accounts = app.get_accounts()

    # Find the account matching the given user_id (Azure OID)
    account = None
    for acc in accounts:
        if acc.get("local_account_id") == user_id:
            account = acc
            break

    if account is None:
        return None

    result = app.acquire_token_silent(
        scopes=settings.azure_scopes,
        account=account,
    )

    if result and "access_token" in result:
        return result["access_token"]
    return None
