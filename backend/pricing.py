"""Versioned price catalog: IDR integers and USD cents, with immutable order snapshots."""
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from pymongo import ReturnDocument
from accounts import get_admin_user, get_current_user
from database import db

router = APIRouter(prefix='/api')
PAGES = (8, 16, 24, 32)


class PriceRow(BaseModel):
    pages: Literal[8, 16, 24, 32]
    digital: int = Field(strict=True, ge=1, le=100000000)
    softcover: int = Field(strict=True, ge=1, le=100000000)
    hardcover: int = Field(strict=True, ge=1, le=100000000)


class PriceRegion(BaseModel):
    currency: Literal['IDR', 'USD']
    prices: list[PriceRow] = Field(min_length=4, max_length=4)

    @model_validator(mode='after')
    def all_lengths(self):
        if sorted(r.pages for r in self.prices) != list(PAGES):
            raise ValueError('Include each of 8, 16, 24 and 32 pages exactly once')
        minimum = 1000 if self.currency == 'IDR' else 50
        if any(getattr(r, k) < minimum for r in self.prices for k in ('digital', 'softcover', 'hardcover')):
            raise ValueError('Minimum price is Rp1,000 or US$0.50')
        return self


class PriceCatalog(BaseModel):
    version: int = Field(ge=1)
    regions: dict[str, PriceRegion]
    updated_at: str = ''
    free_pages: int = 8
    free_books_per_account: int = 1
    pdf_free: bool = True

    @model_validator(mode='after')
    def regions_valid(self):
        if set(self.regions) != {'ID', 'OTHER'}:
            raise ValueError('Both ID and OTHER regions are required')
        if self.regions['ID'].currency != 'IDR' or self.regions['OTHER'].currency != 'USD':
            raise ValueError('Indonesia uses IDR and other countries use USD')
        if self.free_pages != 8 or self.free_books_per_account != 1 or self.pdf_free is not True:
            raise ValueError('The one free 8-page book and free PDF policy must be retained')
        return self


DEFAULT_CATALOG = {
    'version': 1,
    'regions': {
        'ID': {'currency': 'IDR', 'prices': [
            {'pages': 8, 'digital': 15000, 'softcover': 100000, 'hardcover': 150000},
            {'pages': 16, 'digital': 25000, 'softcover': 200000, 'hardcover': 250000},
            {'pages': 24, 'digital': 39000, 'softcover': 340000, 'hardcover': 390000},
            {'pages': 32, 'digital': 49000, 'softcover': 440000, 'hardcover': 490000},
        ]},
        'OTHER': {'currency': 'USD', 'prices': [
            {'pages': 8, 'digital': 100, 'softcover': 1000, 'hardcover': 1500},
            {'pages': 16, 'digital': 195, 'softcover': 1800, 'hardcover': 2500},
            {'pages': 24, 'digital': 295, 'softcover': 2500, 'hardcover': 3900},
            {'pages': 32, 'digital': 395, 'softcover': 3200, 'hardcover': 4900},
        ]},
    },
    'free_pages': 8, 'free_books_per_account': 1, 'pdf_free': True,
}


async def initialize_pricing():
    await db.pricing.update_one({'key': 'current'}, {'$setOnInsert': {
        **DEFAULT_CATALOG, 'updated_at': datetime.now(timezone.utc).isoformat()}}, upsert=True)
    await db.orders.create_index('id', unique=True)
    await db.orders.create_index('provider_order_id', sparse=True)
    await db.orders.create_index('payment_session_id', sparse=True)
    # Count an existing, already-generated free 8-page book; never charge it retroactively.
    async for story in db.stories.find({'user_id': {'$ne': None}, 'page_count': 8,
        'status': {'$in': ['complete', 'completed', 'partial']}, 'billing': {'$exists': False}},
        {'_id': 0, 'id': 1, 'user_id': 1}).sort('created_at', 1):
        await db.users.update_one({'user_id': story['user_id'], 'free_story_id': {'$exists': False}},
                                  {'$set': {'free_story_id': story['id']}})


async def catalog():
    doc = await db.pricing.find_one({'key': 'current'}, {'_id': 0})
    if not doc:
        raise HTTPException(503, 'Prices are temporarily unavailable. Please try again.')
    return PriceCatalog(**doc)


async def snapshot(region, pages, product):
    config = await catalog()
    table = config.regions[region]
    row = next((r for r in table.prices if r.pages == pages), None)
    if not row:
        raise HTTPException(422, 'Unsupported book length')
    return {'region': region, 'currency': table.currency, 'amount_minor': getattr(row, product),
            'page_count': pages, 'product': product, 'pricing_version': config.version}


def verify_quote(quote, amount, version):
    if amount != quote['amount_minor'] or version != quote['pricing_version']:
        raise HTTPException(409, 'The price or free-book eligibility has changed. Please review the current price and try again.')


@router.get('/pricing', response_model=PriceCatalog)
async def get_pricing():
    return await catalog()


@router.get('/billing/allowance')
async def allowance(user=Depends(get_current_user)):
    return {'free_book_available': not bool(user.get('free_story_id')), 'free_pages': 8,
            'free_story_id': user.get('free_story_id')}


@router.put('/admin/pricing', response_model=PriceCatalog)
async def set_pricing(body: PriceCatalog, user=Depends(get_admin_user)):
    stamp = datetime.now(timezone.utc).isoformat()
    before = await db.pricing.find_one_and_update({'key': 'current', 'version': body.version},
        {'$set': {'regions': {k: v.model_dump() for k, v in body.regions.items()}, 'updated_at': stamp,
                  'updated_by': user['user_id']}, '$inc': {'version': 1}},
        return_document=ReturnDocument.BEFORE, projection={'_id': 0})
    if not before:
        raise HTTPException(409, 'Prices were updated elsewhere. Reload before saving again.')
    await db.pricing_audit.insert_one({'previous_version': before['version'], 'new_version': before['version'] + 1,
        'previous_regions': before['regions'], 'new_regions': body.model_dump()['regions'],
        'admin_id': user['user_id'], 'created_at': stamp})
    return await catalog()