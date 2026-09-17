"""Idempotent, non-destructive ownership migration: python migrate_legacy.py."""
import asyncio
from database import db, client


async def migrate():
    stories = await db.stories.update_many({'user_id': {'$exists': False}},
        {'$set': {'user_id': None, 'ownership': 'legacy/guest'}})
    orders = await db.orders.update_many({'user_id': {'$exists': False}},
        {'$set': {'user_id': None, 'ownership': 'legacy/guest'}})
    # No guessing owners by email/name and no making legacy books public.
    return {'stories_tagged': stories.modified_count, 'orders_tagged': orders.modified_count}


if __name__ == '__main__':
    print(asyncio.run(migrate()))
    client.close()