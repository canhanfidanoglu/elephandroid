import msal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.auth.models import TokenCacheEntry


class DBTokenCache(msal.SerializableTokenCache):
    """MSAL token cache backed by SQLAlchemy async sessions (SQLite or PostgreSQL)."""

    async def load(self, db: AsyncSession, user_id: str) -> None:
        """Load the serialized cache blob from the database for the given user."""
        stmt = select(TokenCacheEntry).where(TokenCacheEntry.user_id == user_id)
        result = await db.execute(stmt)
        entry = result.scalar_one_or_none()
        if entry and entry.cache_blob:
            self.deserialize(entry.cache_blob)

    async def save(self, db: AsyncSession, user_id: str) -> None:
        """Persist the cache to the database if its state has changed."""
        if not self.has_state_changed:
            return

        blob = self.serialize()
        entry = TokenCacheEntry(user_id=user_id, cache_blob=blob)
        await db.merge(entry)
        await db.commit()
