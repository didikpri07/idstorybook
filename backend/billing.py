"""Digital entitlement and one free 8-page story, reserved atomically per parent."""
from datetime import datetime, timezone
from fastapi import HTTPException
from pymongo import ReturnDocument
from database import db
from pricing import snapshot, verify_quote


async def prepare_story_billing(story, request_data, user):
    quote = await snapshot(request_data.region, request_data.page_count, 'digital')
    free = False
    if request_data.page_count == 8:
        # A missing price acknowledgement can only use the free offer, never start a charge.
        candidate = await db.users.find_one({'user_id': user['user_id']}, {'_id': 0, 'free_story_id': 1})
        if candidate is not None and not candidate.get('free_story_id'):
            if request_data.expected_amount not in (None, 0):
                raise HTTPException(409, 'Your first 8-page book is free. Please refresh the price.')
            reserved = await db.users.find_one_and_update(
                {'user_id': user['user_id'], 'free_story_id': {'$exists': False}},
                {'$set': {'free_story_id': story['id']}}, projection={'_id': 0, 'user_id': 1},
                return_document=ReturnDocument.AFTER)
            if not reserved:
                raise HTTPException(409, 'Your free story was already started. Please check your library.')
            free = True
    if not free:
        verify_quote(quote, request_data.expected_amount, request_data.pricing_version)
    order_id = None if free else 'dig_' + story['id'].replace('-', '')
    story.update(status='generating' if free else 'awaiting_payment',
                 stage='writing' if free else 'awaiting_payment',
                 billing={**quote, 'kind': 'free' if free else 'paid', 'authorized': free,
                          'amount_minor': 0 if free else quote['amount_minor'], 'order_id': order_id})
    return free


async def create_digital_order(story, user):
    bill = story['billing']
    if bill['kind'] == 'free':
        return
    order = {'id': bill['order_id'], 'kind': 'digital', 'user_id': user['user_id'], 'story_id': story['id'],
             'child_name': story['child_name'], 'format': 'Digital', 'customer_name': user.get('name', ''),
             'email': user['email'], 'status': 'Awaiting payment', 'payment_status': 'pending',
             'payment_gateway': 'midtrans' if bill['region'] == 'ID' else 'stripe',
             'country': 'Indonesia' if bill['region'] == 'ID' else 'Other',
             'price_snapshot': {k: bill[k] for k in ('region', 'currency', 'amount_minor', 'page_count', 'product', 'pricing_version')},
             'currency': bill['currency'], 'amount_minor': bill['amount_minor'], 'page_count': story['page_count'],
             'attempt': 1, 'created_at': datetime.now(timezone.utc).isoformat()}
    await db.orders.update_one({'id': order['id']}, {'$setOnInsert': order}, upsert=True)


async def release_unused_free(story):
    if story.get('billing', {}).get('kind') == 'free':
        await db.users.update_one({'user_id': story['user_id'], 'free_story_id': story['id']},
                                 {'$unset': {'free_story_id': ''}})


async def launch_generation(story_id):
    # Deferred import avoids the server/router import cycle, and keeps the existing AI pipeline.
    from server import generate_story_text, generate_illustration, generate_narration, AUDIO_DIR
    from generation import generate
    await generate(story_id, generate_story_text, generate_illustration, generate_narration, AUDIO_DIR)


async def authorize_paid_story(order, tasks):
    if order.get('kind') != 'digital' or order.get('payment_status') != 'paid':
        return
    changed = await db.stories.update_one(
        {'id': order['story_id'], 'user_id': order['user_id'], 'billing.order_id': order['id'],
         'status': 'awaiting_payment', 'billing.authorized': False},
        {'$set': {'billing.authorized': True, 'status': 'generating', 'stage': 'writing', 'current_page': 1,
                  'paid_at': datetime.now(timezone.utc).isoformat()}})
    if changed.modified_count:
        tasks.add_task(launch_generation, order['story_id'])