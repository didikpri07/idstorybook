import json
import os
import uuid
from datetime import datetime, timezone
from typing import Literal
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
import stripe
from accounts import get_current_user, get_admin_user, rate_limit
from database import db
from story_access import authorized_story
from story_models import OrderPublic
from pricing import snapshot, verify_quote
from payments import config, start_checkout, reconcile, validate_midtrans_notification

router = APIRouter(prefix='/api')


class PrintOrderInput(BaseModel):
    story_id: str = Field(min_length=1, max_length=80)
    format: Literal['Softcover', 'Hardcover']
    customer_name: str = Field(min_length=1, max_length=100)
    email: EmailStr
    address: str = Field(min_length=1, max_length=300)
    city: str = Field(min_length=1, max_length=100)
    postal_code: str = Field(min_length=1, max_length=30)
    country: str = Field(min_length=2, max_length=80)
    expected_amount: int = Field(ge=1)
    pricing_version: int = Field(ge=1)
    request_id: uuid.UUID


async def owned_order(order_id, user):
    order = await db.orders.find_one({'id': order_id, 'user_id': user['user_id']}, {'_id': 0})
    if not order:
        raise HTTPException(404, 'Order not found')
    return order


@router.get('/payments/config')
async def payment_config():
    return config()


@router.post('/orders', response_model=OrderPublic, status_code=201)
async def print_order(body: PrintOrderInput, request: Request, user=Depends(get_current_user)):
    await rate_limit(request, 'print-order', limit=30)
    story, _ = await authorized_story(body.story_id, request)
    if story.get('user_id') != user['user_id'] or story.get('status', 'completed') not in ('complete', 'completed'):
        raise HTTPException(409, 'Finish and save your story before ordering a printed book.')
    order_id = 'prt_' + uuid.uuid5(uuid.NAMESPACE_URL, user['user_id'] + str(body.request_id)).hex
    existing = await db.orders.find_one({'id': order_id, 'user_id': user['user_id']}, {'_id': 0})
    if existing:
        return OrderPublic(**existing)
    region = 'ID' if body.country.strip().lower() in ('indonesia', 'id') else 'OTHER'
    pages = story.get('page_count') or len(story['pages'])
    quote = await snapshot(region, pages, body.format.lower())
    verify_quote(quote, body.expected_amount, body.pricing_version)
    doc = {**body.model_dump(exclude={'expected_amount', 'pricing_version', 'request_id'}),
           'id': order_id, 'kind': 'print', 'user_id': user['user_id'], 'child_name': story['child_name'],
           'page_count': pages, 'price_snapshot': quote, 'currency': quote['currency'], 'amount_minor': quote['amount_minor'],
           'status': 'Awaiting payment', 'payment_status': 'pending', 'attempt': 1,
           'payment_gateway': 'midtrans' if region == 'ID' else 'stripe', 'created_at': datetime.now(timezone.utc).isoformat()}
    await db.orders.update_one({'id': order_id}, {'$setOnInsert': doc}, upsert=True)
    return OrderPublic(**doc)


@router.get('/orders/{order_id}', response_model=OrderPublic)
async def order_details(order_id: str, user=Depends(get_current_user)):
    return OrderPublic(**await owned_order(order_id, user))


@router.post('/orders/{order_id}/checkout')
async def checkout(order_id: str, request: Request, tasks: BackgroundTasks, user=Depends(get_current_user)):
    await rate_limit(request, 'checkout', limit=40)
    order = await owned_order(order_id, user)
    if order.get('checkout_url'):
        order = await reconcile(order, tasks, force=True)
    return await start_checkout(order)


@router.get('/payments/status/{order_id}', response_model=OrderPublic)
async def payment_status(order_id: str, tasks: BackgroundTasks, user=Depends(get_current_user)):
    return OrderPublic(**await reconcile(await owned_order(order_id, user), tasks))


@router.post('/payments/midtrans/notification')
async def midtrans_notification(request: Request, tasks: BackgroundTasks):
    body = await request.body()
    if len(body) > 64000:
        raise HTTPException(413, 'Notification too large')
    try:
        data = json.loads(body)
        if not isinstance(data, dict) or not isinstance(data.get('order_id'), str) or len(data['order_id']) > 100:
            raise ValueError()
    except ValueError:
        raise HTTPException(400, 'Invalid notification')
    order = await db.orders.find_one({'provider_order_id': data.get('order_id'), 'payment_gateway': 'midtrans'}, {'_id': 0})
    validate_midtrans_notification(data, order)
    if order:
        await reconcile(order, tasks, force=True)
    return {'status': 'ok'}


@router.post('/webhook/stripe')
async def stripe_webhook(request: Request, tasks: BackgroundTasks):
    raw = await request.body()
    if len(raw) > 256000:
        raise HTTPException(413, 'Webhook too large')
    try:
        secret = os.environ.get('STRIPE_WEBHOOK_SECRET')
        event = stripe.Webhook.construct_event(raw, request.headers.get('stripe-signature', ''), secret) if secret else json.loads(raw)
        session_id = event['data']['object']['id']
        if not isinstance(session_id, str) or len(session_id) > 200:
            raise ValueError()
    except Exception:
        raise HTTPException(400, 'Invalid webhook')
    # Without a webhook secret this is only a lookup trigger. No posted status/amount is trusted.
    order = await db.orders.find_one({'payment_session_id': session_id, 'payment_gateway': 'stripe'}, {'_id': 0})
    if not order and event.get('type') in ('charge.refunded', 'charge.dispute.created'):
        intent_id = event['data']['object'].get('payment_intent')
        if isinstance(intent_id, str):
            order = await db.orders.find_one({'payment_intent_id': intent_id, 'payment_gateway': 'stripe'}, {'_id': 0})
    if order:
        await reconcile(order, tasks, force=True)
    return {'status': 'ok'}