import hashlib
import ipaddress
import logging
import os
import re
import time
import httpx
from fastapi import APIRouter, Request

router = APIRouter(prefix='/api')
cache = {}
logging.getLogger('httpx').setLevel(logging.WARNING)


@router.get('/region')
async def detect_region(request: Request):
    # No precise location, stored raw IP, or client-side third-party tracking.
    raw = (request.headers.get('cf-connecting-ip') or request.headers.get('x-forwarded-for') or request.client.host).split(',')[0].strip()
    unknown = {'country': None, 'region': None, 'source': 'unavailable'}
    try:
        address = ipaddress.ip_address(raw)
        if not address.is_global:
            return unknown
    except ValueError:
        return unknown
    key = hashlib.sha256(raw.encode()).hexdigest()
    if key in cache and cache[key][0] > time.monotonic():
        return cache[key][1]
    try:
        async with httpx.AsyncClient(timeout=2.5) as client:
            response = await client.get(f"{os.environ['COUNTRY_API_URL'].rstrip('/')}/{address}")
            response.raise_for_status()
            country = response.json().get('country', '')
        if not re.fullmatch('[A-Z]{2}', country):
            return unknown
        result = {'country': country, 'region': 'ID' if country == 'ID' else 'OTHER', 'source': 'detected'}
        if len(cache) > 1000:
            cache.clear()
        cache[key] = (time.monotonic() + 3600, result)
        return result
    except Exception:
        return unknown