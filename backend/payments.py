"""Real provider checkout and authoritative, idempotent payment reconciliation."""
import asyncio
import hashlib
import hmac
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation

import httpx
import stripe
from emergentintegrations.payments.stripe.checkout import StripeCheckout
from fastapi import HTTPException
from pymongo import ReturnDocument
from database import db
from billing import authorize_paid_story

ORIGIN = os.environ['FRONTEND_URL'].rstrip('/')
STRIPE_KEY = os.environ.get('STRIPE_API_KEY')
MIDTRANS_KEY = os.environ.get('MIDTRANS_SERVER_KEY')
if STRIPE_KEY:
    # Preserve the installed adapter's authenticated gateway for its test-key alias.
    # Use its configured Stripe SDK below to retain idempotency and the raw livemode field,
    # which the adapter's small response models do not expose.
    stripe_adapter = StripeCheckout(api_key=STRIPE_KEY, webhook_url=ORIGIN + '/api/webhook/stripe')
    stripe.default_http_client = stripe.RequestsClient(timeout=20)
logging.getLogger('stripe').setLevel(logging.WARNING)


def now():
    return datetime.now(timezone.utc)


def config():
    return {'stripe_enabled': bool(STRIPE_KEY and STRIPE_KEY.startswith('sk_test_')),
            'stripe_mode': 'test', 'midtrans_enabled': bool(MIDTRANS_KEY and os.environ.get('MIDTRANS_CLIENT_KEY')),
            'midtrans_mode': 'production' if os.environ['MIDTRANS_IS_PRODUCTION'].lower() == 'true' else 'sandbox'}


def wire_checkout(order):
    return {'id': order['id'], 'gateway': order['payment_gateway'], 'checkout_url': order.get('checkout_url'),
            'payment_status': order['payment_status'], 'test_mode': order['payment_gateway'] == 'stripe',
            'amount_minor': order.get('amount_minor'), 'currency': order.get('currency')}


async def start_checkout(order):
    enabled = config()[order['payment_gateway'] + '_enabled']
    if not enabled:
        raise HTTPException(503, 'This payment method is not configured yet.')
    if order.get('payment_status') == 'paid':
        raise HTTPException(409, 'This order has already been paid.')
    if order.get('payment_status') == 'refunded':
        raise HTTPException(409, 'This order was refunded. Please create a new order.')
    if not order.get('price_snapshot'):
        raise HTTPException(409, 'This older checkout cannot be resumed. Please start a new print order.')
    if order.get('checkout_url') and order.get('payment_status') == 'pending':
        return wire_checkout(order)
    locked = await db.orders.find_one_and_update({'id': order['id'],
        '$or': [{'checkout_lock_until': {'$exists': False}}, {'checkout_lock_until': {'$lt': now()}}]},
        {'$set': {'checkout_lock_until': now() + timedelta(seconds=45)}},
        return_document=ReturnDocument.AFTER, projection={'_id': 0})
    if not locked:
        raise HTTPException(409, 'Checkout is already being prepared. Please wait a moment.')
    try:
        order = locked
        if order['payment_status'] == 'failed':
            order['attempt'] = order.get('attempt', 1) + 1
            await db.orders.update_one({'id': order['id']}, {'$set': {'attempt': order['attempt'], 'payment_status': 'pending'},
                '$unset': {'checkout_url': '', 'payment_session_id': '', 'provider_order_id': ''}})
        provider_order_id = f"{order['id']}-a{order.get('attempt', 1)}"
        item = f"IDStorybook {order['format']} - {order['page_count']} pages"
        success = f"{ORIGIN}/checkout/success?order_id={order['id']}"
        if order['payment_gateway'] == 'stripe':
            session = await asyncio.to_thread(stripe.checkout.Session.create,
                api_key=STRIPE_KEY, idempotency_key=provider_order_id, mode='payment',
                success_url=success, cancel_url=f"{ORIGIN}/checkout/cancel?order_id={order['id']}",
                customer_email=order['email'],
                line_items=[{'quantity': 1, 'price_data': {'currency': 'usd', 'unit_amount': order['amount_minor'],
                                                        'product_data': {'name': item}}}],
                metadata={'order_id': order['id'], 'user_id': order['user_id'], 'story_id': order['story_id'], 'kind': order['kind'],
                          'webhook_url': ORIGIN + '/api/webhook/stripe'})
            if session.livemode:
                raise HTTPException(503, 'International checkout must remain in test mode.')
            fields = {'checkout_url': session.url, 'payment_session_id': session.id}
        else:
            payload = {'transaction_details': {'order_id': provider_order_id, 'gross_amount': order['amount_minor']},
                       'customer_details': {'first_name': order['customer_name'][:50], 'email': order['email']},
                       'item_details': [{'id': order['story_id'], 'name': item[:50], 'quantity': 1, 'price': order['amount_minor']}],
                       'custom_field1': order['id'], 'custom_field2': order['kind'], 'callbacks': {'finish': success}}
            async with httpx.AsyncClient(timeout=20) as client:
                response = await client.post(os.environ['MIDTRANS_SNAP_HOST'] + '/snap/v1/transactions',
                    json=payload, auth=(MIDTRANS_KEY, ''), headers={'Accept': 'application/json'})
            if response.status_code not in (200, 201):
                raise HTTPException(502, 'The payment provider could not open checkout. Please try again later.')
            data = response.json()
            fields = {'checkout_url': data['redirect_url'], 'provider_order_id': provider_order_id}
        fields.update(payment_status='pending', checkout_created_at=now().isoformat())
        await db.orders.update_one({'id': order['id']}, {'$set': fields})
        return wire_checkout({**order, **fields})
    except HTTPException:
        raise
    except Exception as error:
        logging.warning('Checkout could not start (%s); provider details omitted.', type(error).__name__)
        raise HTTPException(502, 'Checkout is temporarily unavailable. Your story details are saved; please try again.')
    finally:
        await db.orders.update_one({'id': order['id']}, {'$unset': {'checkout_lock_until': ''}})


async def midtrans_status(order):
    if not order.get('provider_order_id'):
        return 'pending'
    async with httpx.AsyncClient(timeout=12) as client:
        response = await client.get(f"{os.environ['MIDTRANS_API_HOST']}/v2/{order['provider_order_id']}/status",
                                    auth=(MIDTRANS_KEY, ''), headers={'Accept': 'application/json'})
    data = response.json()
    if str(data.get('status_code')) == '404':
        return 'pending'
    if response.status_code != 200 or str(data.get('status_code')) in ('401', '403'):
        raise HTTPException(502, 'Payment status is temporarily unavailable.')
    try:
        # Midtrans uses whole rupiah. IDR must NOT be divided by100.
        correct_amount = Decimal(str(data['gross_amount'])) == Decimal(order['amount_minor'])
    except (KeyError, InvalidOperation):
        correct_amount = False
    if (data.get('order_id') != order['provider_order_id'] or not correct_amount
            or order.get('currency') != 'IDR' or data.get('currency', 'IDR') != 'IDR'):
        raise HTTPException(400, 'Payment details do not match this order.')
    state, fraud = data.get('transaction_status'), data.get('fraud_status', '').lower()
    if str(data.get('status_code')) == '200' and (state == 'settlement' and fraud in ('', 'accept') or state == 'capture' and fraud == 'accept'):
        return 'paid'
    if state in ('refund', 'partial_refund', 'chargeback', 'partial_chargeback'):
        return 'refunded'
    if state in ('cancel', 'deny', 'expire', 'failure'):
        return 'failed'
    return 'pending'


async def stripe_status(order):
    if not order.get('payment_session_id'):
        return 'pending'
    session = await asyncio.to_thread(stripe.checkout.Session.retrieve, order['payment_session_id'], api_key=STRIPE_KEY,
                                      expand=['payment_intent.latest_charge'])
    metadata = dict(session.get('metadata') or {})
    if (session.get('livemode') is not False or session.get('amount_total') != order.get('amount_minor')
            or session.get('currency') != 'usd' or order.get('currency') != 'USD'
            or any(metadata.get(k) != order.get(v) for k, v in
                   [('order_id', 'id'), ('user_id', 'user_id'), ('story_id', 'story_id'), ('kind', 'kind')])):
        raise HTTPException(400, 'Payment details do not match this order.')
    if session.get('payment_status') == 'paid' and session.get('status') == 'complete':
        intent = session.get('payment_intent')
        intent_id = intent.get('id') if isinstance(intent, dict) else intent
        if intent_id:
            await db.orders.update_one({'id': order['id']}, {'$set': {'payment_intent_id': intent_id}})
        charge = intent.get('latest_charge') if isinstance(intent, dict) else None
        if isinstance(charge, dict) and (charge.get('refunded') or charge.get('amount_refunded', 0) > 0):
            return 'refunded'
        return 'paid'
    return 'failed' if session.get('status') == 'expired' else 'pending'


async def reconcile(order, tasks, force=False):
    # Legacy orders have no verifiable snapshot: never grant a new entitlement from them.
    if not order.get('price_snapshot'):
        return order
    if order.get('payment_status') == 'paid' and not force:
        await authorize_paid_story(order, tasks)
        return order
    if order.get('payment_status') == 'refunded':
        return order
    if not force:
        lock = await db.orders.update_one({'id': order['id'], '$or': [
            {'next_check_at': {'$exists': False}}, {'next_check_at': {'$lt': now()}}]},
            {'$set': {'next_check_at': now() + timedelta(seconds=3)}})
        if not lock.modified_count:
            fresh = await db.orders.find_one({'id': order['id']}, {'_id': 0})
            await authorize_paid_story(fresh, tasks)
            return fresh
    try:
        status = await (midtrans_status(order) if order['payment_gateway'] == 'midtrans' else stripe_status(order))
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(502, 'Payment verification is temporarily unavailable. Please check again shortly.')
    if status == 'paid':
        await db.orders.update_one({'id': order['id'], 'payment_status': {'$nin': ['paid', 'refunded']}},
            {'$set': {'payment_status': 'paid', 'paid_at': now().isoformat(), 'status': 'Order received'}})
    elif status == 'refunded':
        await db.orders.update_one({'id': order['id']}, {'$set': {'payment_status': 'refunded', 'status': 'Refunded'}})
    elif status == 'failed':
        await db.orders.update_one({'id': order['id'], 'payment_status': {'$nin': ['paid', 'refunded']}},
                                  {'$set': {'payment_status': 'failed', 'status': 'Payment failed'}})
    fresh = await db.orders.find_one({'id': order['id']}, {'_id': 0})
    await authorize_paid_story(fresh, tasks)
    return fresh


def validate_midtrans_notification(data, order):
    raw = f"{data.get('order_id', '')}{data.get('status_code', '')}{data.get('gross_amount', '')}{MIDTRANS_KEY}"
    signature = hashlib.sha512(raw.encode()).hexdigest()
    supplied = data.get('signature_key', '')
    if not MIDTRANS_KEY or not isinstance(supplied, str) or not re.fullmatch('[a-fA-F0-9]{128}', supplied) or not hmac.compare_digest(signature, supplied.lower()):
        raise HTTPException(403, 'Invalid notification signature')
    if order:
        try:
            if Decimal(str(data.get('gross_amount'))) != Decimal(order['amount_minor']):
                raise HTTPException(400, 'Payment amount mismatch')
        except InvalidOperation:
            raise HTTPException(400, 'Invalid payment amount')